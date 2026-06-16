import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture()
def postgres_url(tmp_path_factory):
    if not shutil.which("initdb") or not shutil.which("postgres") or not shutil.which("createdb"):
        pytest.skip("PostgreSQL binaries unavailable")

    root = tmp_path_factory.mktemp("pg")
    data_dir = root / "data"
    socket_dir = Path(tempfile.mkdtemp(prefix="fmo-pg-", dir="/tmp"))
    port = _free_port()
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"

    initdb = subprocess.run(
        ["initdb", "-D", str(data_dir), "-A", "trust", "-U", "postgres", "--encoding=UTF8", "--locale=C"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if initdb.returncode != 0:
        shutil.rmtree(socket_dir, ignore_errors=True)
        pytest.skip(f"PostgreSQL initdb unavailable: {initdb.stderr.strip().splitlines()[-1]}")
    proc = subprocess.Popen(
        [
            "postgres",
            "-D",
            str(data_dir),
            "-k",
            str(socket_dir),
            "-p",
            str(port),
            "-c",
            "listen_addresses=127.0.0.1",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        env["PGHOST"] = str(socket_dir)
        env["PGPORT"] = str(port)
        for _ in range(100):
            if proc.poll() is not None:
                break
            ready = subprocess.run(["pg_isready", "-q", "-h", "127.0.0.1", "-p", str(port)], env=env)
            if ready.returncode == 0:
                break
            time.sleep(0.05)
        if proc.poll() is not None:
            pytest.skip("PostgreSQL server exited before readiness")
        subprocess.run(
            ["createdb", "-h", "127.0.0.1", "-p", str(port), "-U", "postgres", "fmo_test"],
            check=True,
            env=env,
        )
        yield f"postgresql://postgres@127.0.0.1:{port}/fmo_test"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(socket_dir, ignore_errors=True)
