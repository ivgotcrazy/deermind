#!/usr/bin/env python3
"""替代 kubectl，只允许预检查询并记录调用；绝不连接真实集群。"""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    """按 CASE 返回目标状态；未知命令直接失败，防止只读测试漏掉写操作。"""
    args = sys.argv[1:]
    with Path(os.environ["CALLS"]).open("a", encoding="utf-8") as call_log:
        call_log.write(json.dumps(args) + "\n")

    expected_target = [
        "--kubeconfig=" + os.environ["CONFIG"],
        "--context=test",
        "--namespace=deermind-m1",
        "--request-timeout=10s",
    ]
    assert args[:4] == expected_target, "Missing or changed explicit target"

    mode = os.environ.get("CASE", "")
    command = args[4:]
    if command[:2] == ["config", "view"]:
        if mode == "bad-context":
            return 1
        print("https://127.0.0.1:6443")
    elif command == ["get", "--raw=/readyz"]:
        if mode == "unreachable":
            return 1
        print("ok")
    elif command[:2] == ["get", "namespace"]:
        if mode == "missing-namespace":
            return 1
        print("Terminating" if mode == "terminating" else "Active")
    elif command[:2] == ["get", "nodes"]:
        if mode != "empty-nodes":
            print("node-1\t" + ("False" if mode == "not-ready" else "True"))
    else:
        raise AssertionError("Unexpected or mutating command: " + repr(command))

    return 0


if __name__ == "__main__":
    sys.exit(main())
