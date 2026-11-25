"""检查方面规则支持的 JSON Schema 子集，并解析目标条件。"""

from math import isfinite

from deermind.abstractions.encoding import canonical_json
from pydantic import JsonValue

SCALARS = {"string", "boolean", "integer", "number", "null"}
FORBIDDEN = {"threshold", "probability_threshold", "required_correct_count", "permanent_veto"}


def _number(value: JsonValue) -> bool:
    # 数值取整数（排除布尔）或有限浮点；布尔不算数值。
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, float) and isfinite(value)
    )


def _types(schema: dict[str, JsonValue]) -> set[str]:
    declared = schema.get("type")
    # type 可为单值或列表，统一拆成待校验序列。
    values = declared if isinstance(declared, list) else [declared]
    types = {item for item in values if isinstance(item, str)}
    # 类型须非空、无重复且都在允许的标量/对象集合内。
    if not types or len(types) != len(values) or types - (SCALARS | {"object"}):
        raise ValueError("条件类型无效。")
    # 对象类型不能与标量类型混用声明。
    if "object" in types and types != {"object"}:
        raise ValueError("对象条件必须单独声明。")
    return types


def _scalar(schema: dict[str, JsonValue], value: JsonValue, types: set[str]) -> bool:
    actual: dict[type, str] = {
        str: "string",
        bool: "boolean",
        int: "integer",
        float: "number",
        type(None): "null",
    }
    kind = actual.get(type(value))
    # 实际类型须在声明集合内；整数可兼容声明为 number。
    if kind not in types and not (kind == "integer" and "number" in types):
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum, maximum = schema.get("minimum"), schema.get("maximum")
        # 数值还须落在声明的最小/最大范围内。
        return (
            _number(value)
            and (not isinstance(minimum, (int, float)) or value >= minimum)
            and (not isinstance(maximum, (int, float)) or value <= maximum)
        )
    return True


def _schema(schema: dict[str, JsonValue], depth: int = 0) -> None:
    # 限制对象嵌套深度，避免深层递归失控。
    if depth > 4:
        raise ValueError("条件嵌套过深。")
    types = _types(schema)
    if types == {"object"}:
        properties, required = schema.get("properties", {}), schema.get("required", [])
        # 对象只允许 type/properties/required/additionalProperties，字段与必填项须合法且封闭。
        if (
            set(schema) - {"type", "properties", "required", "additionalProperties"}
            or not isinstance(properties, dict)
            or not isinstance(required, list)
            or schema.get("additionalProperties", False) is not False
            or any(not isinstance(name, str) or name not in properties for name in required)
        ):
            raise ValueError("对象条件只可声明已知字段和必填项。")
        # 逐个字段递归校验子 Schema。
        for key, child in properties.items():
            # 字段名命中禁止配置，或子结构不是对象，判无效。
            if key.casefold() in FORBIDDEN or not isinstance(child, dict):
                raise ValueError("包含禁止配置或无效的条件字段。")
            _schema(child, depth + 1)
        return
    # 标量条件只允许 type/enum/minimum/maximum 约束。
    if set(schema) - {"type", "enum", "minimum", "maximum"}:
        raise ValueError("不支持该条件约束。")
    lower, upper = schema.get("minimum"), schema.get("maximum")
    # 范围约束只能出现在数值类型上，且取值须为数值。
    for key in ("minimum", "maximum"):
        if key in schema and (types - {"integer", "number", "null"} or not _number(schema[key])):
            raise ValueError("范围只能约束数值条件。")
    # 上下界同时存在时，下界不得大于上界。
    if isinstance(lower, (int, float)) and isinstance(upper, (int, float)) and lower > upper:
        raise ValueError("条件最小值大于最大值。")
    if "enum" in schema:
        enum = schema["enum"]
        if (
            not isinstance(enum, list)
            or not enum
            or any(not _scalar(schema, v, types) for v in enum)
        ):
            raise ValueError("条件枚举项不符合类型或范围。")


def _value(schema: dict[str, JsonValue], value: JsonValue, *, partial: bool = False) -> None:
    types = _types(schema)
    if types == {"object"} and isinstance(value, dict):
        properties, required = schema.get("properties", {}), schema.get("required", [])
        assert isinstance(properties, dict) and isinstance(required, list)
        # 不得出现未知字段；非 partial 模式下必填项不得缺省。
        if not value.keys() <= properties.keys() or (
            not partial and any(k not in value for k in required)
        ):
            raise ValueError("条件包含未知字段或缺少必填项。")
        # 逐字段递归校验取值。
        for key, item in value.items():
            child = properties[key]
            assert isinstance(child, dict)
            _value(child, item, partial=partial)
        return
    enum = schema.get("enum")
    # 标量取值须过类型/范围校验；声明了枚举时还须命中枚举项。
    if not _scalar(schema, value, types) or (
        isinstance(enum, list) and canonical_json(value) not in {canonical_json(v) for v in enum}
    ):
        raise ValueError("条件值不符合声明的类型、范围或枚举。")


def verify_schema(schema: dict[str, JsonValue], defaults: dict[str, JsonValue]) -> None:
    _schema(schema)
    _value(schema, defaults, partial=True)


def resolve_conditions(
    schema: dict[str, JsonValue],
    defaults: dict[str, JsonValue],
    supplied: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """已知规则默认值只补未填写字段，显式的 null 照常校验。"""
    values = {**defaults, **supplied}
    _value(schema, values)
    return values
