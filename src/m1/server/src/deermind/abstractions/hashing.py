"""合同内容摘要；与既有持久化哈希保持相同编码。"""

import hashlib

from deermind.abstractions.encoding import canonical_json


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
