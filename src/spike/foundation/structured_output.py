"""Small structural JSON-schema subset for fixed result envelopes, never semantics."""


def check_schema(schema):
    """Reject unsupported definitions before sending data; this is not general JSON Schema."""
    if not isinstance(schema, dict):
        raise ValueError("InvalidOutputSchema")
    if set(schema) == {"anyOf"}:
        if not isinstance(schema["anyOf"], list) or not schema["anyOf"]:
            raise ValueError("InvalidOutputSchema")
        for branch in schema["anyOf"]:
            check_schema(branch)
        return
    kind = schema.get("type")
    if kind == "object":
        if (set(schema) != {"type", "properties", "required", "additionalProperties"}
                or schema["additionalProperties"] is not False
                or not isinstance(schema["properties"], dict)
                or not isinstance(schema["required"], list)
                or any(not isinstance(k, str) for k in schema["required"])
                or len(schema["required"]) != len(schema["properties"])
                or set(schema["required"]) != set(schema["properties"])):
            raise ValueError("InvalidOutputSchema")
        for value in schema["properties"].values():
            check_schema(value)
    elif kind == "array":
        if set(schema) != {"type", "items"}:
            raise ValueError("InvalidOutputSchema")
        check_schema(schema["items"])
    elif kind in ("string", "null"):
        if set(schema) not in ({"type"}, {"type", "enum"}):
            raise ValueError("InvalidOutputSchema")
        if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]
                or any(not isinstance(x, str) if kind == "string" else x is not None for x in schema["enum"])):
            raise ValueError("InvalidOutputSchema")
    else:
        raise ValueError("InvalidOutputSchema")


def matches_schema(value, schema):
    """Check a previously checked schema; source bindings and judgments stay downstream."""
    if "anyOf" in schema:
        return any(matches_schema(value, branch) for branch in schema["anyOf"])
    kind = schema["type"]
    if kind == "object":
        return (isinstance(value, dict) and set(value) == set(schema["properties"])
                and all(matches_schema(value[k], s) for k, s in schema["properties"].items()))
    if kind == "array":
        return isinstance(value, list) and all(matches_schema(x, schema["items"]) for x in value)
    return ((isinstance(value, str) if kind == "string" else value is None)
            and ("enum" not in schema or value in schema["enum"]))
