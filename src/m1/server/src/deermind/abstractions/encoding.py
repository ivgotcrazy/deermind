"""确定性JSON编码；不读写数据，也不依赖任何实现。"""

import json


def canonical_json(value: object) -> str:
    """固定UTF-8 JSON编码：键排序、无空白、拒绝非有限数；不改变数组顺序。"""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
