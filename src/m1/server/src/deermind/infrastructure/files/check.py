"""Check mounted storage using an isolated temporary file, never user content."""

from pathlib import Path
from tempfile import NamedTemporaryFile

from deermind.infrastructure.files.local import LocalFiles


def check_storage(root: Path, *, require_mount: bool = True) -> None:
    """Fail on unavailable storage; remove the probe file even after an error."""
    LocalFiles(root, backend="pvc" if require_mount else "local")
    with NamedTemporaryFile(prefix=".deermind-check-", dir=root) as probe:
        probe.write(b"deermind")
        probe.flush()
        if Path(probe.name).read_bytes() != b"deermind":
            # 临时文件回读内容不一致，判定挂载存储不可靠。
            raise OSError("Storage probe did not round-trip")
