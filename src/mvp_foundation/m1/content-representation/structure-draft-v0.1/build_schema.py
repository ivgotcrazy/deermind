"""Build the bounded four-case content contract; no production schema changes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


def array(items, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum}


def enum(*values):
    return {"enum": list(values)}


def ref(name):
    return {"$ref": f"#/$defs/{name}"}


TEXT = {"type": "string", "minLength": 1}
NUMBER = {"type": "number"}
INTEGER = {"type": "integer", "minimum": 0}
DECIMAL = {"type": "string", "pattern": r"^-?\d+(\.\d+)?$"}
ID = {"type": "string", "pattern": r"^[A-Za-z][A-Za-z0-9_-]*$"}
PAIR = {"type": "array", "items": NUMBER, "minItems": 2, "maxItems": 2}
BOX = {"type": "array", "items": INTEGER, "minItems": 4, "maxItems": 4}
PROVENANCE = obj({"source_refs": array(ID, 1),
                  "transformation": enum("extracted", "normalized", "derived"),
                  "note": TEXT})


def block(kind, fields):
    return obj({"id": ID, "type": {"const": kind}, "provenance": PROVENANCE, **fields})


def build():
    # A single expression tree is authoritative. Cancellation annotations do not
    # replace operands or assert that the original working is mathematically true.
    expression = {"oneOf": [
        obj({"op": {"const": "number"}, "value": DECIMAL,
             "cancel_to": array(DECIMAL, 1)}, ["op", "value"]),
        obj({"op": {"const": "symbol"}, "name": TEXT}),
        obj({"op": {"const": "group"}, "args": {
            "type": "array", "items": ref("expression"), "minItems": 1, "maxItems": 1}}),
        obj({"op": enum("fraction", "multiply", "divide", "add", "subtract", "equal"),
             "args": {"type": "array", "items": ref("expression"), "minItems": 2, "maxItems": 2}})
    ]}
    inline = {"oneOf": [obj({"type": {"const": "text"}, "text": TEXT}),
                          obj({"type": {"const": "math"}, "expression": ref("expression")}),
                          obj({"type": {"const": "response_blank"}, "label": TEXT})]}
    cell = {"oneOf": [
        obj({"state": {"const": "provided"}, "content": array(ref("inline"), 1)}),
        obj({"state": enum("response_blank", "source_missing", "unreadable"), "reason": TEXT})
    ]}
    column = obj({"key": ID, "label": TEXT, "value_type": enum("text", "decimal"),
                  "unit": {"type": "string"}})
    table = obj({"id": ID, "provenance": PROVENANCE,
                 "columns": array(column, 1), "rows": array(array(ref("cell"), 1), 1)})
    chart = block("chart", {
        "kind": enum("bar", "line", "pie"), "title": TEXT, "data_ref": ID,
        "category_column": ID, "series": array(obj({"column": ID, "label": TEXT,
            "color": {"type": "string", "pattern": r"^#[0-9a-fA-F]{6}$"}}), 1),
        "unit": TEXT, "axis": {"oneOf": [{"type": "null"}, obj({"min": NUMBER,
            "max": NUMBER, "step": {"type": "number", "exclusiveMinimum": 0}, "label": TEXT})]},
        "relationship": enum("overlapping_populations", "disjoint_parts"),
        "stacked": {"type": "boolean"},
        "slice_colors": array({"type": "string", "pattern": r"^#[0-9a-fA-F]{6}$"})})
    shape = obj({"id": ID, "shape": enum("circle", "ellipse", "triangle", "square", "pentagon", "hexagon"),
                 "classification_basis": enum("visual_recognition", "explicit_text"),
                 "layout_box": {"type": "array", "items": NUMBER, "minItems": 4, "maxItems": 4},
                 "mark": obj({"id": ID, "position": PAIR,
                              "meaning": {"const": "unspecified"}})})
    # Only the observed point-inside-shape relation is exercised by C06. No
    # center/equal-length/perpendicular assertions may be inferred from layout.
    relation = obj({"kind": {"const": "inside"}, "subject": ID, "object": ID,
                    "basis": {"const": "visual_recognition"}, "source_refs": array(ID, 1)})
    blocks = {"oneOf": [
        block("paragraph", {"content": array(ref("inline"), 1)}),
        block("math_sequence", {"purpose": enum("given_work", "reference_work"),
             "lines": array(obj({"relation": enum("", "="), "expression": ref("expression"),
                                 "suffix": {"type": "string"}}), 1)}),
        block("table", {"data_ref": ID, "caption": TEXT}),
        chart,
        block("diagram", {"title": TEXT, "layout_role": {"const": "display_only"},
             "view_box": BOX, "objects": array(shape, 1), "relations": array(relation)})
    ]}
    document = obj({"id": ID, "role": enum("statement", "reference", "teaching_aid", "derived_view"),
                    "title": TEXT, "blocks": array(ref("block"), 1)})
    source = obj({"id": ID, "page": {"type": "integer", "minimum": 1},
                  "file": TEXT, "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                  "original_file": TEXT, "original_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                  "original_size": {"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 2, "maxItems": 2},
                  "pixel_box": BOX})
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
              "$id": "urn:deermind:content-structure:four-cases:0.1",
              "title": "Four-case content structure draft, not a production contract",
              **obj({"schema_version": {"const": "0.1"}, "case_id": enum("C02", "C03", "C05", "C06"),
                     "title": TEXT, "content_revision": {"type": "integer", "minimum": 1},
                     "binding_status": {"const": "pending_domain_match"},
                     "sources": array(source, 1), "documents": array(ref("document"), 1),
                     "data_tables": array(ref("data_table")), "notes": array(TEXT)}),
              "$defs": {"expression": expression, "inline": inline, "cell": cell,
                        "data_table": table, "block": blocks, "document": document}}
    return schema


if __name__ == "__main__":
    (ROOT / "schema.json").write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
