"""Check direct Python imports; runtime data access still needs review and tests."""

import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "server/src"
BUSINESS = ("deermind.product", "deermind.spaces.")


def owner(module: str) -> str:
    parts = module.split(".")
    return ".".join(parts[:3] if module.startswith("deermind.spaces.") else parts[:2])


def violation(source: str, target: str) -> str | None:
    if source.startswith("deermind.abstractions"):
        if target.startswith("deermind.") and not target.startswith("deermind.abstractions."):
            return "独立抽象不能导入项目实现"
        if target.split(".")[0] not in sys.stdlib_module_names | {"deermind", "pydantic"}:
            return "独立抽象只允许标准库、Pydantic及本层合同"
    if (
        source == "deermind.foundation" or source.startswith("deermind.foundation.")
    ) and target.startswith("deermind.infrastructure"):
        return "foundation只能通过独立抽象使用技术适配"
    if (
        source == "deermind.infrastructure" or source.startswith("deermind.infrastructure.")
    ) and target.startswith("deermind.foundation"):
        return "infrastructure只能通过独立抽象调用底座服务"
    if source.startswith(("deermind.foundation.", "deermind.infrastructure.")):
        if target.startswith(("deermind.bootstrap", "deermind.entrypoints")):
            return "底座与技术适配不能反向导入装配或入口"
    if source.startswith(BUSINESS):
        if target.startswith(("deermind.bootstrap", "deermind.entrypoints")):
            return "业务模块不能反向导入装配或入口"
    if source.startswith("deermind.entrypoints.") and target.startswith(BUSINESS):
        if ".public." not in target and not target.endswith(".public"):
            return "入口只能通过业务公开合同访问业务模块"
    if source.startswith("deermind.infrastructure.") and target.startswith(BUSINESS):
        return "技术适配通过独立抽象接线，不能导入业务模块"
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
    tree = ast.parse(code)
    dynamic_names = {"__import__", "importlib.import_module"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            dynamic_names.update(
                n.asname or n.name for n in node.names if n.name == "import_module"
            )
        if isinstance(node, ast.Import):
            dynamic_names.update(
                (n.asname or n.name) + ".import_module" for n in node.names if n.name == "importlib"
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func) in dynamic_names:
            if any(
                module == root or module.startswith(root + ".")
                for root in (
                    "deermind.abstractions",
                    "deermind.foundation",
                    "deermind.infrastructure",
                )
            ):
                problems.append(f"{module}:{node.lineno}: 跨层模块禁止动态导入绕过静态依赖")
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


def abstraction_cycles(files: list[Path]) -> list[str]:
    """检查独立合同内部的循环引用；包括类型注解和相对导入。"""
    graph: dict[str, set[str]] = {}
    for path in files:
        if "abstractions" not in path.relative_to(SOURCE).parts:
            continue
        module = ".".join(path.relative_to(SOURCE).with_suffix("").parts).removesuffix(".__init__")
        graph[module] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                graph[module].update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parent = module if path.name == "__init__.py" else module.rpartition(".")[0]
                    base = importlib.util.resolve_name("." * node.level + base, parent)
                graph[module].add(base)
                graph[module].update(base + "." + alias.name for alias in node.names)
    done: set[str] = set()
    active: list[str] = []
    problems: list[str] = []

    def visit(module: str) -> None:
        if module in active:
            problems.append(
                "抽象循环依赖: " + " -> ".join(active[active.index(module) :] + [module])
            )
            return
        if module in done:
            return
        active.append(module)
        for target in sorted(graph[module] & graph.keys()):
            visit(target)
        active.pop()
        done.add(module)

    for module in sorted(graph):
        visit(module)
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
    problems.extend(abstraction_cycles(files))
    for problem in problems:
        print(problem)
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
