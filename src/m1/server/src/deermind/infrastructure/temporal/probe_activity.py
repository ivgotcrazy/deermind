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
            # 令牌必须是规范 UUID 十六进制，拒绝拼接出任意路径。
            raise ValueError("Probe token must be a canonical UUID hex string")
        if (self.root / f".probe-{token}.request").read_text() != token:
            # 共享卷上的请求令牌与活动入参不一致，判定链路异常。
            raise ValueError("Shared storage request mismatch")
        (self.root / f".probe-{token}.reply").write_text(token, encoding="utf-8")
        return token
