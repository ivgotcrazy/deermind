"""确定性 JSON 编码；不读写数据，也不依赖任何实现。

分层定位：abstractions（跨层合同/纯函数）
边界约束：只做编码；键排序、固定分隔符与拒绝非有限数，保证同一内容在各层得到同一字符串。
"""

import json


def canonical_json(value: object) -> str:
    """固定 UTF-8 JSON 编码：键排序、无空白、拒绝非有限数；不改变数组顺序。"""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
