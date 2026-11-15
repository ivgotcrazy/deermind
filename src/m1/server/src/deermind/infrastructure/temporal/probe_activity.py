"""Local file I/O for the deployment probe, isolated from workflow replay."""

from pathlib import Path
from uuid import UUID

from temporalio import activity


class ProbeActivity:
    """Only UUID-named test files are accessed; arbitrary paths are rejected."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @activity.defn(name="runtime.storage_probe_reply")
    def reply(self, token: str) -> str:
        if UUID(token).hex != token:
            raise ValueError("Probe token must be a canonical UUID hex string")
        if (self.root / f".probe-{token}.request").read_text() != token:
            raise ValueError("Shared storage request mismatch")
        (self.root / f".probe-{token}.reply").write_text(token, encoding="utf-8")
        return token
