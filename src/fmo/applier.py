import hashlib
import json


class ComboConflict(RuntimeError):
    pass


class ComboApplier:
    def __init__(self, current: dict[str, list[str]]):
        self.current = current
        self.snapshots: dict[str, list[str]] = {}
        self.run_status = "pending"

    def managed_names(self) -> list[str]:
        return sorted(name for name in self.current if name.startswith("fmo-"))

    def state_hash(self, name: str) -> str:
        payload = json.dumps(self.current.get(name, []), separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def apply(self, name: str, desired: list[str], *, expected_hash: str, smoke_ok: bool) -> None:
        if not name.startswith("fmo-"):
            return
        if name not in self.current:
            raise ComboConflict("combo is not managed")
        if self.state_hash(name) != expected_hash:
            raise ComboConflict("combo drift detected")
        snapshot = list(self.current.get(name, []))
        self.snapshots[name] = snapshot
        self.current[name] = list(desired)
        if not smoke_ok:
            self.current[name] = snapshot
            self.run_status = "failed"
            return
        self.run_status = "committed"
