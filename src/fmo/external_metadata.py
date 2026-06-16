from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalMetadataError(RuntimeError):
    source: str
    reason: str
    status_code: int | None = None

    def __str__(self) -> str:
        if self.status_code is None:
            return f"{self.source}:{self.reason}"
        return f"{self.source}:{self.reason}:http_{self.status_code}"
