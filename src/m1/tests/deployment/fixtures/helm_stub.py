#!/usr/bin/env python3
"""记录部署入口交给 Helm 的参数；可模拟 lint 失败，不创建任何资源。"""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    """只有指定 lint 失败时返回非零；真实参数由调用方测试断言。"""
    args = sys.argv[1:]
    with Path(os.environ["HELM_CALLS"]).open("a", encoding="utf-8") as call_log:
        call_log.write(json.dumps(args) + "\n")

    return int("lint" in args and os.environ.get("FAIL_LINT") == "1")


if __name__ == "__main__":
    sys.exit(main())
