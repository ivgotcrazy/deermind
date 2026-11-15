"""Check mounted storage using an isolated temporary file, never user content."""

from pathlib import Path
from tempfile import NamedTemporaryFile


def check_storage(root: Path) -> None:
    """Fail on unavailable storage; remove the probe file even after an error."""
    with NamedTemporaryFile(prefix=".deermind-check-", dir=root) as probe:
        probe.write(b"deermind")
        probe.flush()
        if Path(probe.name).read_bytes() != b"deermind":
            raise OSError("Storage probe did not round-trip")
