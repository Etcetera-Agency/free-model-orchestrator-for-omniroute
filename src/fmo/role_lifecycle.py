from datetime import datetime, timedelta


def reconcile_roles(roles: dict[str, dict], *, desired_roles: set[str], now: datetime, grace_period: timedelta) -> dict[str, dict]:
    result = {role_id: dict(role) for role_id, role in roles.items()}
    for role_id, role in list(result.items()):
        if role_id in desired_roles:
            role["status"] = "active"
            role["missing_since"] = None
            continue
        if role.get("status") == "retiring" and role.get("missing_since") and now - role["missing_since"] > grace_period and role.get("recent_usage", 0) == 0:
            role["status"] = "retired_pending_delete"
            continue
        role["status"] = "retiring"
        role.setdefault("missing_since", now)
    for role_id in desired_roles - set(result):
        result[role_id] = {
            "status": "bootstrap_pending",
            "missing_since": None,
            "policy_template": "default",
            "cold_start_demand": 1,
            "combo": [],
        }
    return result
