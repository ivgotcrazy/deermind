"""文件适配的真实字节往返、发布中断与路径防护；仅使用临时目录。"""

import io
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from deermind.infrastructure.files.local import LocalFiles


class FileTests(unittest.TestCase):
    def test_round_trip_and_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = LocalFiles(Path(directory), backend="local")
            content = "公式：d=v×t\n".encode() + bytes(range(256))
            saved = files.save(io.BytesIO(content), max_bytes=len(content))
            self.assertEqual(files.read(saved, max_bytes=len(content)), content)
            with self.assertRaises(ValueError):
                files.save(io.BytesIO(content), max_bytes=len(content) - 1)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)
            self.assertEqual((Path(directory) / saved.storage_key).stat().st_mode & 0o222, 0)

    def test_interrupted_write_and_full_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = LocalFiles(Path(directory), backend="local")
            with patch("os.fsync", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    files.save(io.BytesIO(b"partial"), max_bytes=7)
            self.assertEqual(list(Path(directory).iterdir()), [])
            with patch("os.link", side_effect=OSError("publish interrupted")):
                with self.assertRaises(OSError):
                    files.save(io.BytesIO(b"complete"), max_bytes=8)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_missing_corrupt_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = LocalFiles(Path(directory), backend="local")
            saved = files.save(io.BytesIO(b"abc"), max_bytes=3)
            path = Path(directory) / saved.storage_key
            path.chmod(0o600)
            path.write_bytes(b"abd")
            with self.assertRaises(OSError):
                files.read(saved, max_bytes=3)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                files.read(saved, max_bytes=3)
            path.symlink_to("/etc/passwd")
            with self.assertRaises(OSError):
                files.read(saved, max_bytes=3)
            with self.assertRaises(ValueError):
                files.read(replace(saved, storage_key="../../etc/passwd"), max_bytes=3)

    def test_wrong_mount_and_replaced_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "files"
            root.mkdir()
            with self.assertRaises(OSError):
                LocalFiles(root, backend="pvc")
            files = LocalFiles(root, backend="local")
            root.rename(Path(directory) / "old")
            root.mkdir()
            with self.assertRaises(OSError):
                files.save(io.BytesIO(b"x"), max_bytes=1)
            root.rmdir()
            root.symlink_to(Path(directory) / "old", target_is_directory=True)
            with self.assertRaises(ValueError):
                LocalFiles(root, backend="local")

    def test_publish_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = LocalFiles(Path(directory), backend="local")
            first = files.save(io.BytesIO(b"old"), max_bytes=3)
            with patch("deermind.infrastructure.files.local.uuid4", return_value=first.file_id):
                with self.assertRaises(FileExistsError):
                    files.save(io.BytesIO(b"new"), max_bytes=3)
            self.assertEqual(files.read(first, max_bytes=3), b"old")


if __name__ == "__main__":
    unittest.main()
