"""Ingest real Hermes source shapes into the inventory.

Every fixture mirrors NousResearch/hermes-agent @ tag v2026.6.5 exactly:
  - ``cron_jobs.json``             -> ``cron/jobs.py`` ``{"jobs": [...]}``
  - ``webhook_subscriptions.json`` -> ``hermes_cli/webhook.py`` route records
  - ``profiles.json``              -> ``hermes_cli/profiles.py`` ProfileInfo
  - ``state_schema.sql`` + ``state_sessions.json`` -> ``hermes_state.py`` sessions

The parsers under test consume those real shapes rather than a hand-invented
``{"roles": [...]}`` payload, so schema drift in Hermes is caught here.
"""

import json
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
import yaml

from fmo.hermes_inventory import (
    BOOTSTRAP_CALLS_PER_RUN,
    HermesInventoryError,
    build_hermes_inventory,
    enumerate_live_profiles,
    observe_session_demand,
    parse_gateway_services,
    parse_cron_jobs,
    parse_profiles,
    parse_webhook_subscriptions,
    read_hermes_command_sources,
    read_hermes_home,
    read_hermes_http_sources,
)

from _fixtures import hermes_fixture_path, load_hermes_fixture


def _build_state_db(path):
    """Create a real-schema state.db and seed it from the recorded session rows."""
    schema = hermes_fixture_path("state_schema.sql").read_text()
    rows = load_hermes_fixture("state_sessions.json")["sessions"]
    conn = sqlite3.connect(path)
    conn.executescript(schema)
    conn.executemany(
        "INSERT INTO sessions (id, source, model, started_at, ended_at, api_call_count, input_tokens, output_tokens) "
        "VALUES (:id, :source, :model, :started_at, :ended_at, :api_call_count, :input_tokens, :output_tokens)",
        rows,
    )
    conn.commit()
    return conn


@pytest.mark.spec("hermes-inventory::Real cron job schedule mapped")
def test_parse_cron_jobs_maps_real_jobs_json_and_skips_disabled():
    payload = load_hermes_fixture("cron_jobs.json")

    consumers = parse_cron_jobs(payload)

    # The disabled "Disabled weekly digest" job is excluded.
    by_consumer = {c.consumer: c for c in consumers}
    assert set(by_consumer) == {"a1b2c3d4e5f6", "0f1e2d3c4b5a", "9988776655aa"}

    cron = by_consumer["a1b2c3d4e5f6"]
    assert cron.consumer_type == "cron_job"
    # job["model"] is the OmniRoute combo the routine routes to (1 combo per role).
    assert cron.role_id == "coding-combo"
    assert cron.cadence == "0 2 * * *"  # cron expr
    assert cron.calls_per_run == BOOTSTRAP_CALLS_PER_RUN  # no observed demand injected

    assert by_consumer["0f1e2d3c4b5a"].cadence == "every 360m"  # interval display
    # Job with no combo (model=null) routes to the default combo's role.
    assert by_consumer["9988776655aa"].role_id == "default"


@pytest.mark.spec("hermes-inventory::Event-driven consumer cadence")
def test_parse_webhook_subscriptions_maps_real_routes():
    payload = load_hermes_fixture("webhook_subscriptions.json")

    consumers = parse_webhook_subscriptions(payload)

    by_consumer = {c.consumer: c for c in consumers}
    assert set(by_consumer) == {"pr-review", "alert-triage"}
    assert by_consumer["pr-review"].consumer_type == "webhook"
    assert by_consumer["pr-review"].role_id == "default"
    assert by_consumer["pr-review"].cadence == "event:pull_request"  # GitHub event trigger
    assert by_consumer["alert-triage"].cadence == "event-driven"  # API trigger, no events


@pytest.mark.spec("hermes-inventory::Profile gateway state selects consumer type")
def test_parse_profiles_distinguishes_service_from_agent_profile():
    payload = load_hermes_fixture("profiles.json")

    consumers = parse_profiles(payload)

    by_consumer = {c.consumer: c for c in consumers}
    # gateway_running True -> long-running service; otherwise interactive profile.
    assert by_consumer["default"].consumer_type == "service"
    assert by_consumer["default"].cadence == "continuous"
    assert by_consumer["default"].role_id == "chat-combo"
    assert by_consumer["research"].consumer_type == "agent_profile"
    assert by_consumer["research"].cadence == "manual"


@pytest.mark.spec("hermes-inventory::Observed calls_per_run from state.db")
def test_observe_session_demand_reads_real_state_db_schema(tmp_path):
    conn = _build_state_db(tmp_path / "state.db")
    try:
        demand = observe_session_demand(conn)
    finally:
        conn.close()

    # coding-combo: avg api_call_count of (6, 4) = 5.0
    assert demand["coding-combo"] == 5.0
    assert demand["research-combo"] == 3.0
    assert demand["chat-combo"] == pytest.approx((2 + 5) / 2)


@pytest.mark.spec("hermes-inventory::Mixed consumers recorded")
def test_build_hermes_inventory_records_all_four_consumer_types_with_observed_demand(tmp_path):
    conn = _build_state_db(tmp_path / "state.db")
    try:
        inventory = build_hermes_inventory(
            cron_jobs=load_hermes_fixture("cron_jobs.json"),
            webhook_subscriptions=load_hermes_fixture("webhook_subscriptions.json"),
            profiles=load_hermes_fixture("profiles.json"),
            session_connection=conn,
        )
    finally:
        conn.close()

    types = {c.consumer_type for c in inventory.consumers}
    assert types == {"cron_job", "webhook", "agent_profile", "service"}

    # The coding-combo cron job now carries observed calls_per_run from state.db.
    coding = next(c for c in inventory.consumers if c.consumer == "a1b2c3d4e5f6")
    assert coding.calls_per_run == 5.0


@pytest.mark.spec("hermes-inventory::Mixed consumers recorded")
def test_read_hermes_home_reads_real_directory_layout(tmp_path):
    home = tmp_path / "hermes"
    (home / "cron").mkdir(parents=True)
    (home / "cron" / "jobs.json").write_text(hermes_fixture_path("cron_jobs.json").read_text())
    (home / "webhook_subscriptions.json").write_text(hermes_fixture_path("webhook_subscriptions.json").read_text())
    (home / "config.yaml").write_text(hermes_fixture_path("gateway_config.yaml").read_text())
    research_profile = home / "profiles" / "research"
    research_profile.mkdir(parents=True)
    (research_profile / "config.yaml").write_text("model: research-combo\nprovider: omniroute\n")
    _build_state_db(home / "state.db").close()

    inventory = read_hermes_home(home)

    types = {c.consumer_type for c in inventory.consumers}
    assert types == {"cron_job", "webhook", "agent_profile", "service"}
    research_cron = next(c for c in inventory.consumers if c.consumer == "0f1e2d3c4b5a")
    assert research_cron.calls_per_run == 3.0  # research-combo observed avg
    assert any(c.consumer == "gateway:github" and c.role_id == "coding-combo" for c in inventory.consumers)


@pytest.mark.spec("hermes-inventory::Command adapter returns real shapes")
def test_command_adapter_returns_real_source_shapes_and_structured_errors(tmp_path):
    payload = {
        "cron_jobs": load_hermes_fixture("cron_jobs.json"),
        "webhook_subscriptions": load_hermes_fixture("webhook_subscriptions.json"),
        "profiles": load_hermes_fixture("profiles.json"),
    }
    source_file = tmp_path / "inventory_sources.json"
    source_file.write_text(json.dumps(payload), encoding="utf-8")

    sources = read_hermes_command_sources(
        [
            sys.executable,
            "-c",
            "import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text())",
            str(source_file),
        ]
    )

    assert sources["cron_jobs"]["jobs"][0]["id"] == "a1b2c3d4e5f6"
    assert sources["profiles"]["profiles"][0]["model"] == "chat-combo"

    with pytest.raises(HermesInventoryError) as exc:
        read_hermes_command_sources([sys.executable, "-c", "import sys; sys.exit(7)"])
    assert exc.value.source == "command"
    assert exc.value.reason == "nonzero_exit"


@pytest.mark.spec("hermes-inventory::Command adapter returns real shapes")
def test_http_adapter_returns_real_source_shapes_and_structured_errors():
    payload = {
        "cron_jobs": load_hermes_fixture("cron_jobs.json"),
        "webhook_subscriptions": load_hermes_fixture("webhook_subscriptions.json"),
        "profiles": load_hermes_fixture("profiles.json"),
    }
    server = _start_fixture_server(payload)
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        sources = read_hermes_http_sources(f"{base_url}/inventory")

        assert sources["webhook_subscriptions"]["pr-review"]["events"] == ["pull_request"]

        with pytest.raises(HermesInventoryError) as exc:
            read_hermes_http_sources(f"{base_url}/missing")
        assert exc.value.source == "http"
        assert exc.value.reason == "http_error"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.spec("hermes-inventory::Live profile enumeration")
def test_live_profile_enumeration_scans_profile_dirs_and_config_models(tmp_path):
    home = tmp_path / "hermes"
    (home / "profiles" / "research").mkdir(parents=True)
    (home / "profiles" / "ops").mkdir(parents=True)
    (home / "config.yaml").write_text("model: chat-combo\nprovider: omniroute\n")
    (home / "profiles" / "research" / "config.yaml").write_text("model: research-combo\nprovider: omniroute\n")
    (home / "profiles" / "ops" / "config.yaml").write_text("model: ops-combo\nprovider: omniroute\n")

    profiles = enumerate_live_profiles(home)
    consumers = parse_profiles(profiles)

    by_consumer = {consumer.consumer: consumer for consumer in consumers}
    assert set(by_consumer) == {"default", "ops", "research"}
    assert by_consumer["default"].role_id == "chat-combo"
    assert by_consumer["research"].role_id == "research-combo"
    assert by_consumer["ops"].role_id == "ops-combo"


@pytest.mark.spec("hermes-inventory::Service from gateway config")
def test_gateway_platform_config_derives_enabled_service_consumers():
    config_text = hermes_fixture_path("gateway_config.yaml").read_text()
    config = yaml.safe_load(config_text)

    consumers = parse_gateway_services(config)

    by_consumer = {consumer.consumer: consumer for consumer in consumers}
    assert set(by_consumer) == {"gateway:github", "gateway:telegram"}
    assert by_consumer["gateway:github"].role_id == "coding-combo"
    assert by_consumer["gateway:telegram"].consumer_type == "service"


def _start_fixture_server(payload):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/inventory":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server
