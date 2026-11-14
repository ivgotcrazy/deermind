"""Schema, content invariants and bounded author-fixture checks. No AI calls."""
import copy
import hashlib
import json
import re
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
PLAN = json.loads((ROOT / "review-plan.json").read_text(encoding="utf-8"))


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def blocks(case):
    return [b for doc in case["documents"] for b in doc["blocks"]]


def scalar(cell):
    if cell["state"] != "provided":
        raise ValueError("unknown/blank cells cannot become chart numbers")
    if len(cell["content"]) != 1 or cell["content"][0]["type"] != "text":
        raise ValueError("this chart draft requires scalar cells")
    return cell["content"][0]["text"]


def validate(case, source_files=True, inventory=False):
    errors = ["schema: " + "/".join(map(str, e.absolute_path)) + " " + e.message
              for e in VALIDATOR.iter_errors(case)]
    if errors:
        return errors
    source_ids = {s["id"] for s in case["sources"]}
    identifiers = [n["id"] for n in walk(case) if "id" in n]
    if len(identifiers) != len(set(identifiers)):
        errors.append("duplicate content/source identifier")
    for node in walk(case):
        if "source_refs" in node and not set(node["source_refs"]).issubset(source_ids):
            errors.append("unknown source reference")
    for source in case["sources"]:
        x0, y0, x1, y1 = source["pixel_box"]
        width, height = source["original_size"]
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            errors.append("source region outside original page")
        if source_files:
            for field, digest in [("file", "sha256"), ("original_file", "original_sha256")]:
                path = (ROOT / source[field]).resolve()
                if not path.is_relative_to(ROOT.parent):
                    errors.append("source path outside content experiment")
                elif not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source[digest]:
                    errors.append("source file/hash mismatch: " + source[field])
    tables = {t["id"]: t for t in case["data_tables"]}
    for table in tables.values():
        cols = table["columns"]
        if len({c["key"] for c in cols}) != len(cols):
            errors.append("duplicate column")
        for row in table["rows"]:
            if len(row) != len(cols):
                errors.append("table row/column count mismatch")
                continue
            for column, cell in zip(cols, row):
                if column["value_type"] == "decimal" and cell["state"] == "provided":
                    try:
                        if not re.fullmatch(r"-?\d+(\.\d+)?", scalar(cell)):
                            errors.append("invalid decimal cell")
                    except ValueError as error:
                        errors.append(str(error))
    if sum(d["role"] == "statement" for d in case["documents"]) != 1:
        errors.append("expected one question statement document")
    for doc in case["documents"]:
        for b in doc["blocks"]:
            if b["type"] == "math_sequence":
                if doc["role"] == "statement" and b["purpose"] == "reference_work":
                    errors.append("reference solution leaked into question")
                if b["lines"][0]["relation"] or any(line["relation"] != "=" for line in b["lines"][1:]):
                    errors.append("invalid sequence relation placement")
            if doc["role"] == "derived_view" and b["provenance"]["transformation"] != "derived":
                errors.append("derived view mislabeled as extracted")
            if doc["role"] == "statement" and b["provenance"]["transformation"] == "derived":
                errors.append("derived material leaked into source question")
            if b["type"] in ("table", "chart") and b["data_ref"] not in tables:
                errors.append("missing table/chart data reference")
                continue
            if b["type"] == "chart":
                table = tables[b["data_ref"]]
                columns = {c["key"]: i for i, c in enumerate(table["columns"])}
                keys = [b["category_column"]] + [s["column"] for s in b["series"]]
                if any(k not in columns for k in keys):
                    errors.append("unknown chart column")
                    continue
                if any(len(row) != len(table["columns"]) for row in table["rows"]):
                    continue
                try:
                    values = [[Decimal(scalar(row[columns[s["column"]]])) for row in table["rows"]] for s in b["series"]]
                    for s in b["series"]:
                        column = table["columns"][columns[s["column"]]]
                        if column["value_type"] != "decimal" or column["unit"] != b["unit"]:
                            errors.append("chart data type/unit mismatch")
                    if b["kind"] == "pie":
                        if (len(values) != 1 or b["axis"] is not None or b["unit"] != "%" or b["stacked"] or
                            b["relationship"] != "disjoint_parts" or len(b["slice_colors"]) != len(table["rows"])):
                            errors.append("invalid pie configuration")
                        if any(v < 0 for v in values[0]) or sum(values[0]) != Decimal(100):
                            errors.append("pie labels in this fixture must sum to 100")
                    else:
                        axis = b["axis"]
                        if axis is None or axis["max"] <= axis["min"]:
                            errors.append("invalid chart axis")
                        elif any(v < Decimal(str(axis["min"])) or v > Decimal(str(axis["max"])) for series in values for v in series):
                            errors.append("chart axis would clip data")
                        if b["relationship"] == "overlapping_populations" and b["stacked"]:
                            errors.append("overlapping populations cannot be stacked as additive totals")
                except (ValueError, ArithmeticError) as error:
                    errors.append("unavailable chart values: " + str(error))
            if b["type"] == "diagram":
                vx, vy, vw, vh = b["view_box"]
                shapes = {o["id"]: o for o in b["objects"]}
                marks = {o["mark"]["id"]: o for o in b["objects"]}
                if vw <= 0 or vh <= 0:
                    errors.append("invalid view box")
                for o in shapes.values():
                    x, y, w, h = o["layout_box"]
                    px, py = o["mark"]["position"]
                    if not (w > 0 and h > 0 and vx <= x and vy <= y and x + w <= vx + vw and y + h <= vy + vh):
                        errors.append("shape outside view box")
                    if not (x <= px <= x + w and y <= py <= y + h):
                        errors.append("point outside shape layout")
                    if o["shape"] in ("square", "circle") and w != h:
                        errors.append("square/circle layout distorted")
                for relation in b["relations"]:
                    if relation["subject"] not in marks or relation["object"] not in shapes:
                        errors.append("unknown diagram relation reference")
                    elif marks[relation["subject"]]["id"] != relation["object"]:
                        errors.append("point associated with wrong shape")
    if inventory:
        actual = {"documents": len(case["documents"]), "blocks": len(blocks(case)),
                  "references": sum(d["role"] == "reference" for d in case["documents"]),
                  "charts": sum(b["type"] == "chart" for b in blocks(case)),
                  "blank": sum(n.get("type") == "response_blank" for n in walk(case)),
                  "cancel_chains": sum(len(n.get("cancel_to", [])) for n in walk(case))}
        if actual != PLAN["expected"][case["case_id"]]:
            errors.append("author inventory mismatch: " + json.dumps(actual))
        for doc in case["documents"]:
            for b in doc["blocks"]:
                expected = PLAN["expected_roles"].get(b["id"])
                if expected and expected != doc["role"]:
                    errors.append("author source-purpose mismatch: " + b["id"])
    return errors


def arithmetic(e):
    if e["op"] == "number":
        return Fraction(e["value"])
    values = [arithmetic(a) for a in e["args"]]
    if e["op"] == "group":
        return values[0]
    a, b = values
    return {"fraction": lambda: a / b, "divide": lambda: a / b, "multiply": lambda: a * b,
            "add": lambda: a + b, "subtract": lambda: a - b, "equal": lambda: a == b}[e["op"]]()


def main():
    Draft202012Validator.check_schema(SCHEMA)
    cases = {cid: json.loads((ROOT / f"cases/{cid}.json").read_text(encoding="utf-8")) for cid in PLAN["case_ids"]}
    positives = []
    for cid, case in cases.items():
        errors = validate(case, inventory=True)
        if errors:
            raise AssertionError(cid + ": " + "\n".join(errors))
        positives.append({"case_id": cid, "schema": "passed", "invariants": "passed", "sources": "hashes_verified", "author_inventory": "passed"})
    negatives = []

    def reject(name, cid, mutate, inventory=False, schema_should_pass=False):
        changed = copy.deepcopy(cases[cid])
        mutate(changed)
        if schema_should_pass:
            assert not list(VALIDATOR.iter_errors(changed)), name + " should demonstrate schema alone is insufficient"
        errors = validate(changed, source_files=False, inventory=inventory)
        assert errors, name + " was not rejected"
        negatives.append({"name": name, "rejected": True, "reason": errors[0]})

    reject("wrong formula arity", "C03", lambda c: c["documents"][0]["blocks"][1]["lines"][0]["expression"]["args"].append({"op": "number", "value": "3"}))
    reject("unknown content type", "C03", lambda c: c["documents"][0]["blocks"][0].update(type="html"))
    reject("blank cannot carry an answer", "C02", lambda c: c["documents"][0]["blocks"][3]["content"][1].update(value="3"))
    reject("dangling source", "C02", lambda c: c["documents"][0]["blocks"][0]["provenance"].update(source_refs=["missing"]), schema_should_pass=True)
    def leak_reference(c):
        copied = copy.deepcopy(c["documents"][1]["blocks"][1])
        copied["id"] = "C02-leaked-work"
        c["documents"][0]["blocks"].append(copied)

    def swap_hint(c):
        question, aid = c["documents"][0]["blocks"], c["documents"][-1]["blocks"]
        question[-1], aid[0] = aid[0], question[-1]

    reject("reference leaked into question", "C02", leak_reference, schema_should_pass=True)
    reject("hint swapped into question with valid counts", "C02", swap_hint, inventory=True, schema_should_pass=True)
    reject("unknown table reference", "C05", lambda c: c["documents"][0]["blocks"][1].update(data_ref="missing"), schema_should_pass=True)
    reject("table row lost a cell", "C05", lambda c: c["data_tables"][0]["rows"][0].pop(), schema_should_pass=True)
    reject("unit mismatch", "C05", lambda c: c["documents"][0]["blocks"][1].update(unit="人"), schema_should_pass=True)
    reject("overlapping cohorts stacked", "C05", lambda c: c["documents"][0]["blocks"][1].update(stacked=True), schema_should_pass=True)
    reject("axis clips value", "C05", lambda c: c["documents"][0]["blocks"][1]["axis"].update(max=2), schema_should_pass=True)
    reject("derived table falsely labeled source", "C05", lambda c: c["documents"][2]["blocks"][0]["provenance"].update(transformation="extracted"), schema_should_pass=True)
    reject("all charts omitted despite valid schema", "C05", lambda c: c["documents"][0].update(blocks=c["documents"][0]["blocks"][:1]), inventory=True, schema_should_pass=True)
    reject("square rendered as rectangle", "C06", lambda c: c["documents"][0]["blocks"][1]["objects"][3]["layout_box"].__setitem__(2, 60), schema_should_pass=True)
    reject("display point claimed as center", "C06", lambda c: c["documents"][0]["blocks"][1]["objects"][0]["mark"].update(meaning="center"))
    reject("missing geometry point reference", "C06", lambda c: c["documents"][0]["blocks"][1]["relations"][0].update(subject="missing"), schema_should_pass=True)
    reject("invalid crop", "C03", lambda c: c["sources"][0].update(pixel_box=[0, 0, 9999, 9999]), schema_should_pass=True)
    # State variants are exercised on the same C05 table, without inventing a
    # new textbook sample. The chart may not silently treat them as zero.
    for state in ["response_blank", "source_missing", "unreadable"]:
        reject(f"{state} is not zero", "C05", lambda c, s=state: c["data_tables"][0]["rows"][0].__setitem__(1, {"state": s, "reason": "负例：不得默认为零"}), schema_should_pass=True)
    # The error exercise must remain structurally valid while numerically false.
    lines = cases["C03"]["documents"][0]["blocks"][1]["lines"]
    values = [str(arithmetic(line["expression"])) for line in lines]
    assert values == ["63/32", "7/32", "7/32"]
    assert lines[0]["expression"]["op"] == "divide" and lines[0]["expression"]["args"][0]["op"] == "multiply"
    for doc in cases["C02"]["documents"]:
        if doc["role"] == "reference":
            assert all(arithmetic(line["expression"]) == 3 for line in doc["blocks"][1]["lines"])
    report = {"version": "0.1", "status": "passed", "cases": positives, "negative_cases": negatives,
              "original_error_preserved": {"C03_line_values": values, "changes_to_source": False},
              "boundaries": PLAN["limits"], "model_calls": 0,
              "interpretation": "Program checks and a fixed author inventory passed. This does not prove autonomous extraction or general semantic completeness."}
    (ROOT / "checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "cases": len(cases), "negative_checks": len(negatives), "model_calls": 0}))


if __name__ == "__main__":
    main()
