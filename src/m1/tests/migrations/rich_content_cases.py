"""将既有四例草稿转换为正式线形，仅供测试进程读取。"""

import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

# 历史夹具只在这里按动态 JSON 读取。输出交由正式 RichContent 模型校验。
type Draft = dict[str, Any]

CASE_IDS = ("C02", "C03", "C05", "C06")


def read_cases() -> list[Draft]:
    """Pod 使用注入的四例，直接执行时使用工作区原文件。"""
    directory = Path(__file__).resolve().parent
    if not (directory / "C02.json").exists():
        directory = (
            directory.parents[2]
            / "mvp_foundation/m1/content-representation/structure-draft-v0.1/cases"
        )
    return [json.loads((directory / f"{case_id}.json").read_text("utf-8")) for case_id in CASE_IDS]


def source_ref(source: Draft) -> Draft:
    """保留原页哈希、印刷页码和区域，测试编号不参与生产文件索引。"""
    original_hash = source["original_sha256"]
    file_identity = uuid5(NAMESPACE_URL, f"urn:deermind:rich-test-source:{original_hash}")
    return {
        "source_id": source["id"],
        "owner": "product",
        "ref": {"type": "file", "file_id": str(file_identity), "sha256": original_hash},
        "printed_page": str(source["page"]),
        "region": source["pixel_box"],
    }


def data_table(table: Draft) -> Draft:
    """按表头键记录单元格并保留十进制字符串。"""
    columns = table["columns"]
    rows: list[Draft] = []
    for index, row in enumerate(table["rows"], start=1):
        cells: dict[str, Draft] = {}
        for column, cell in zip(columns, row, strict=True):
            entry = {"state": cell["state"]}
            if cell["state"] == "provided":
                (span,) = cell["content"]
                if span["type"] != "text":
                    raise ValueError("Fixture value requires a text span")
                entry["value"] = span["text"]
            cells[column["key"]] = entry
        rows.append({"row_id": f"{table['id']}-{index}", "cells": cells})
    return {
        "data_id": table["id"],
        "columns": columns,
        "rows": rows,
        "provenance": table["provenance"],
    }


def diagram_payload(block: Draft) -> Draft:
    """保留可见对象与关系，坐标只写入布局。"""
    objects: list[Draft] = []
    boxes: list[Draft] = []
    points: list[Draft] = []
    for shape in block["objects"]:
        objects.append({"object_id": shape["id"], "shape": shape["shape"]})
        boxes.append({"object_ref": shape["id"], "box": shape["layout_box"]})
        if mark := shape.get("mark"):
            objects.append({"object_id": mark["id"], "shape": "point"})
            points.append({"object_ref": mark["id"], "position": mark["position"]})
    relations = [
        {
            "predicate": relation["kind"],
            "subject": relation["subject"],
            "object": relation["object"],
            "basis": "visual_observation",
            "source_refs": relation["source_refs"],
        }
        for relation in block["relations"]
    ]
    return {
        "caption": block["title"],
        "objects": objects,
        "relations": relations,
        "layout": {"view_box": block["view_box"], "boxes": boxes, "points": points},
    }


def content_block(block: Draft) -> Draft:
    """转换块外壳，公式树和原有变形行保持同一顺序。"""
    kind = block["type"]
    payload = {
        key: value for key, value in block.items() if key not in {"id", "type", "provenance"}
    }
    if kind == "paragraph":
        payload = {"spans": block["content"]}
    elif kind == "chart":
        payload["caption"] = payload.pop("title")
        payload["legend"] = True
        if axis := block["axis"]:
            payload["axis"] = {**axis, **{key: str(axis[key]) for key in ("min", "max", "step")}}
    elif kind == "diagram":
        payload = diagram_payload(block)
    return {
        "block_id": block["id"],
        "type": kind,
        "provenance": block["provenance"],
        "payload": payload,
    }


def case_documents(case: Draft) -> list[Draft]:
    """按原始用途分别生成正文，引用同一来源的表图读取同一组数据。"""
    sources = [source_ref(source) for source in case["sources"]]
    tables = {table["id"]: data_table(table) for table in case["data_tables"]}
    documents: list[Draft] = []
    for document in case["documents"]:
        blocks = [content_block(block) for block in document["blocks"]]
        if document["id"] == "C06-question":
            # 既有审阅记录明确材料缺口，将该条原文随图形回读展示。
            diagram = next(block for block in blocks if block["type"] == "diagram")
            missing_page = next(note for note in case["notes"] if note.startswith("附页1图1不在"))
            provenance = diagram["provenance"]
            diagram["provenance"] = {
                **provenance,
                "note": f"{provenance['note']} {missing_page}",
            }
        used_tables = {
            block["payload"]["data_ref"] for block in blocks if block["type"] in {"table", "chart"}
        }
        documents.append(
            {
                "id": document["id"],
                "title": document["title"],
                "content": {
                    "schema_version": "1",
                    "role": document["role"],
                    "blocks": blocks,
                    "data_tables": [table for key, table in tables.items() if key in used_tables],
                    "source_refs": sources,
                },
            }
        )
    return documents
