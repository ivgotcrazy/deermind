"""Check direct Python imports; runtime data access still needs review and tests."""

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "server/src"
BUSINESS = ("deermind.product", "deermind.spaces.")


def owner(module: str) -> str:
    parts = module.split(".")
    return ".".join(parts[:3] if module.startswith("deermind.spaces.") else parts[:2])


def violation(source: str, target: str) -> str | None:
    if source.startswith("deermind.foundation.") and target.startswith(BUSINESS):
        return "foundation不能导入业务模块"
    if source.startswith(BUSINESS) and target.startswith(BUSINESS):
        if (
            owner(source) != owner(target)
            and ".public." not in target
            and not target.endswith(".public")
        ):
            return "跨业务模块只能导入公开合同"
    if ".public." in source or source.endswith(".public"):
        if ".persistence" in target or target.startswith(
            ("sqlalchemy", "fastapi", "temporalio", "pydantic_ai")
        ):
            return "公开合同不能加载存储、执行或AI实现"
    if source.startswith("deermind.spaces.evaluation.belief."):
        if target.startswith(
            ("sqlalchemy", "fastapi", "temporalio", "pydantic_ai", "openai", "httpx")
        ):
            return "概率纯函数不能依赖外部执行组件"
    return None


def inspect_imports(module: str, code: str, *, package: bool = False) -> list[str]:
    problems: list[str] = []
    for node in ast.walk(ast.parse(code)):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        targets: list[str] = []
        if isinstance(node, ast.Import):
            targets = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = module if package else module.rpartition(".")[0]
                base = importlib.util.resolve_name("." * node.level + base, parent)
            targets = [base + "." + item.name for item in node.names]
        for target in targets:
            reason = violation(module, target)
            if reason:
                problems.append(f"{module}:{node.lineno}: {target}: {reason}")
    return problems


def main() -> int:
    files = sorted((SOURCE / "deermind").rglob("*.py"))
    if not files:
        print("PENDING: 正式后端源码未建立；模块边界规则由正反样例检验。")
        return 0
    problems: list[str] = []
    for path in files:
        relative = path.relative_to(SOURCE).with_suffix("")
        module = ".".join(relative.parts)
        package = path.name == "__init__.py"
        if package:
            module = module.removesuffix(".__init__")
        problems.extend(inspect_imports(module, path.read_text(encoding="utf-8"), package=package))
    for problem in problems:
        print(problem)
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
