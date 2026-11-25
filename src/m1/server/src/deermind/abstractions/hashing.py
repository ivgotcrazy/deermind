"""合同内容摘要；与既有持久化哈希保持相同编码。

分层定位：abstractions（跨层合同/纯函数）
边界约束：摘要基于 canonical_json 编码，保证同一内容在各层得到同一哈希。
"""

import hashlib

from deermind.abstractions.encoding import canonical_json


def digest(value: object) -> str:
    """计算内容的 SHA-256 十六进制摘要；输入先经确定性 JSON 编码。"""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
