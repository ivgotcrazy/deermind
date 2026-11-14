"""Author-reviewed structural drafts from exactly the existing four source crops.

This does not call an LLM. Historical model outputs and reviewed copies stay intact.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROUND2 = ROOT.parent / "round2"
RUN = ROUND2 / "runs/20261105T024756Z"


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(name, value):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def txt(text):
    return {"type": "text", "text": text}


def num(value, cancel_to=None):
    out = {"op": "number", "value": str(value)}
    if cancel_to:
        out["cancel_to"] = [str(n) for n in cancel_to]
    return out


def exp(op, *args):
    return {"op": op, "args": list(args)}


def frac(a, b):
    return exp("fraction", num(a), num(b))


def math(expression):
    return {"type": "math", "expression": expression}


def provenance(source, transformation="extracted", note="按原图内容整理；不表示已自动识别正确。"):
    return {"source_refs": source if isinstance(source, list) else [source],
            "transformation": transformation, "note": note}


def block(identifier, block_type, source, **fields):
    return {"id": identifier, "type": block_type, "provenance": provenance(source), **fields}


def paragraph(identifier, source, *items):
    return block(identifier, "paragraph", source, content=[txt(i) if isinstance(i, str) else i for i in items])


def document(identifier, role, title, blocks):
    return {"id": identifier, "role": role, "title": title, "blocks": blocks}


def sequence(identifier, source, expressions, purpose, unit=False):
    return block(identifier, "math_sequence", source, purpose=purpose, lines=[
        {"relation": "=" if i else "", "expression": e,
         "suffix": "（人）" if unit and i == len(expressions) - 1 else ""}
        for i, e in enumerate(expressions)])


def base(case):
    cid = case["id"]
    return {"schema_version": "0.1", "case_id": cid, "title": case["title"],
            "content_revision": 1, "binding_status": "pending_domain_match",
            "sources": [{"id": f"{cid}-source-{r['index']}", "page": r["page"],
                "file": "../round2/" + r["file"], "sha256": r["sha256"],
                "original_file": "../source/" + Path(r["original"]).name,
                "original_sha256": r["originalSha256"], "original_size": r["originalSize"],
                "pixel_box": r["pixelBox"]} for r in case["regions"]],
            "documents": [], "data_tables": [], "notes": []}


def c02(case):
    c = base(case)
    s0, s1 = [s["id"] for s in c["sources"]]
    question = [paragraph("C02-background", s0, "气象小组有12人。摄影小组的人数是气象小组的",
                          math(frac(1, 3)), "。航模小组的人数是摄影小组的", math(frac(3, 4)), "。"),
                paragraph("C02-request", s0, "航模小组有多少人？说一说你是如何思考的。"),
                paragraph("C02-calculate", s1, "请列式解决问题。"),
                paragraph("C02-answer", s1, "答：", {"type": "response_blank", "label": "答句"}, "。")]
    question[0]["provenance"] = provenance(s0, "normalized", "将三处对话框条件串为一段；人物插画不是人数统计依据。")
    a1 = exp("multiply", exp("multiply", num(12), frac(1, 3)), frac(3, 4))
    a2 = exp("multiply", exp("multiply", num(12, [4, 1]), exp("fraction", num(1), num(3, [1]))),
             exp("fraction", num(3), num(4, [1])))
    b1 = exp("multiply", num(12), exp("group", exp("multiply", frac(1, 3), frac(3, 4))))
    b2 = exp("multiply", num(12, [3]), exp("fraction", num(1), num(4, [1])))
    c["documents"] = [document("C02-question", "statement", "原题", question),
        document("C02-reference-a", "reference", "教材解法 A：先求中间人数", [
            paragraph("C02-a-text", s1, "先求摄影小组有多少人，再……"),
            sequence("C02-a-work", s1, [a1, a2, num(3)], "reference_work", True)]),
        document("C02-reference-b", "reference", "教材解法 B：先合并比例", [
            paragraph("C02-b-text", s1, "先求航模小组的人数是气象小组的几分之几。"),
            sequence("C02-b-work", s1, [b1, b2, num(3)], "reference_work", True)]),
        document("C02-aid", "teaching_aid", "教材旁注", [paragraph("C02-aid-text", s1, "你能看懂笑笑的方法吗？")])]
    c["notes"] = ["沿用原四例的裁剪范围；未提取裁剪范围外的线段图或其他练习。",
        "两份解法是题内参考内容，未创建独立 SolutionInstance，也未假定已匹配领域 Solution。",
        "补回原图约分：左式12→4→1、分母3→1和4→1；右式12→3、分母4→1。保留被划去的原数；不改变运算树的操作数。",
        "约分标记保存含义及先后，不复刻笔迹像素；答句是填写空白，不是教材表格。"]
    return c


def c03(case):
    c = base(case)
    s0, s1 = [s["id"] for s in c["sources"]]
    first = exp("divide", exp("multiply", frac(7, 8), frac(3, 4)), frac(1, 3))
    second = exp("multiply", exp("multiply", frac(7, 8), exp("fraction", num(3, [1]), num(4))),
                 exp("fraction", num(1), num(3, [1])))
    c["documents"] = [document("C03-question", "statement", "原题待辨析演算", [
        paragraph("C03-request", s0, "下面几道题算得对吗？计算时有什么好办法可以减少错误？"),
        sequence("C03-given-work", s1, [first, second, frac(7, 32)], "given_work")])]
    c["notes"] = ["只检查原范围内的一列演算；保留÷1/3、下一行×1/3及结果7/32。",
        "表达式按从左到右结合；两处3→1的原有约分标记补回。",
        "given_work表示学生要分析的材料，不是正确性标签。格式校验不能因为原题等式不成立而拒收，也不能将答案改成63/32。"]
    return c


def provided(value):
    return {"state": "provided", "content": [txt(str(value))]}


def c05(case):
    c = base(case)
    src = c["sources"][0]["id"]
    old = load(RUN / "C05/reviewed-content.json")["tasks"][0]
    charts = [b for p in old["question"] for b in p["blocks"] if b["type"] == "chart"]
    c["data_tables"] = [
        {"id": "C05-population", "provenance": provenance(src, "normalized", "按原图数值标签整理；保留1.30等原显示精度。柱图与折线图核对后共用数据。"),
         "columns": [{"key": "census", "label": "人口普查", "value_type": "text", "unit": ""},
                     {"key": "age60", "label": "60岁及以上", "value_type": "decimal", "unit": "亿人"},
                     {"key": "age65", "label": "65岁及以上", "value_type": "decimal", "unit": "亿人"}],
         "rows": [[provided(label), provided(f"{charts[0]['series'][0]['values'][i]:.2f}"),
                   provided(f"{charts[0]['series'][1]['values'][i]:.2f}")]
                  for i, label in enumerate(charts[0]["categories"])]},
        {"id": "C05-ages", "provenance": provenance(src, "normalized", "按原扇形图的类别和百分比整理，不推导其他人口数。"),
         "columns": [{"key": "group", "label": "年龄段", "value_type": "text", "unit": ""},
                     {"key": "share", "label": "占比", "value_type": "decimal", "unit": "%"}],
         "rows": [[provided(label), provided(f"{charts[2]['series'][0]['values'][i]:.2f}")]
                  for i, label in enumerate(charts[2]["categories"])]}]
    blocks = [paragraph("C05-request", src,
        "同学们根据整理的我国人口老龄化的数据绘制下面的统计图，从统计图中你能获得哪些信息？与同伴交流。")]
    for i, chart in enumerate(charts):
        pie = chart["chartType"] == "pie"
        b = block(f"C05-chart-{i}", "chart", src, kind=chart["chartType"],
                  title=["第五～七次人口普查中老年人口数量统计图", "第五～七次人口普查中老年人口数量变化情况", "第七次人口普查年龄分布图"][i],
                  data_ref="C05-ages" if pie else "C05-population", category_column="group" if pie else "census",
                  series=[{"column": "share", "label": "占比", "color": "#4f81bd"}] if pie else [
                      {"column": "age60", "label": "60岁及以上", "color": "#4f81bd"},
                      {"column": "age65", "label": "65岁及以上", "color": "#e28036"}],
                  unit="%" if pie else "亿人", axis=None if pie else {"min": 0, "max": 3, "step": .5, "label": "人口数/亿"},
                  relationship="disjoint_parts" if pie else "overlapping_populations", stacked=False,
                  slice_colors=["#4f81bd", "#e28036", "#a5a5a5", "#ffc000"] if pie else [])
        b["provenance"] = provenance(src, "normalized", "保留图类、数值标签、轴与图例；用固定近似颜色重绘。亿人是人口数/亿的单位规范化。")
        blocks.append(b)
    aids = [paragraph(f"C05-aid-{i}", src, b["text"]) for i, b in enumerate(old["teachingAids"][0]["blocks"])]
    tables = []
    for key, caption in [("C05-population", "柱图和折线图的数据"), ("C05-ages", "扇形图的数据")]:
        b = block(key + "-view", "table", src, data_ref=key, caption=caption)
        b["provenance"] = provenance(src, "derived", "同一批图中数据的表格视图；原书此处没有这张表，不自动放进学生题面。")
        tables.append(b)
    c["documents"] = [document("C05-question", "statement", "原题及三幅图", blocks),
        document("C05-aid", "teaching_aid", "教材教学提示", aids),
        document("C05-data-view", "derived_view", "结构数据表（非教材原表）", tables)]
    c["notes"] = ["复用原C05第93页裁剪，不引入第91页表格；此处表格用于验证同一数据的另一种展示。",
        "65岁及以上属于60岁及以上，柱图不得改成相加堆叠。百分比原标签总和为100%。",
        "三个图和旁注由作者对照原图整理；没有新增模型调用，不把本次结构稿当成Agent自动提取成功。"]
    return c


def c06(case):
    c = base(case)
    src = c["sources"][0]["id"]
    kinds = ["circle", "ellipse", "triangle", "square", "pentagon", "hexagon"]
    objects, relations = [], []
    for i, kind in enumerate(kinds):
        x = 18 + 110 * i
        o = {"id": f"C06-shape-{i}", "shape": kind, "classification_basis": "visual_recognition",
             "layout_box": [x, 20, 78, 78 if kind != "ellipse" else 56],
             "mark": {"id": f"C06-point-{i}", "position": [x + 39, 48 if kind == "ellipse" else (69 if kind == "triangle" else 59)], "meaning": "unspecified"}}
        objects.append(o)
        relations.append({"kind": "inside", "subject": o["mark"]["id"], "object": o["id"],
                          "basis": "visual_recognition", "source_refs": [src]})
    diagram = block("C06-shapes", "diagram", src, title="六种图形及可见标记", layout_role="display_only",
                    view_box=[0, 0, 680, 120], objects=objects, relations=relations)
    diagram["provenance"] = provenance(src, "normalized", "形状类别与标记来自原图；显示坐标只供重绘。三角形、五边形和六边形的规则排版不构成等边条件。")
    c["documents"] = [document("C06-question", "statement", "比较图形", [
        paragraph("C06-request", src, "从附页1中的图1剪出下面的图形，想办法说明圆和其他图形的不同。"), diagram])]
    c["notes"] = ["六个图形和六个点均保留；没有center_of、等边、等角或相等长度断言。",
        "附页1图1不在既定四例材料内；不能据本例宣称剪图操作材料齐备或完整活动可以实施。",
        "本例只检验有限形状及点标记，不代表一般几何关系、立体、方向图均已验证。"]
    return c


if __name__ == "__main__":
    cases = load(ROUND2 / "cases.json")
    for case in cases:
        save(f"cases/{case['id']}.json", {"C02": c02, "C03": c03, "C05": c05, "C06": c06}[case["id"]](case))
    # Independent author inventory: removing a valid block must not silently pass
    # the four-case completeness review. This is not an automated vision result.
    save("review-plan.json", {
        "origin": "author_inventory_from_existing_four_crops", "case_ids": [c["id"] for c in cases],
        "expected": {
            "C02": {"documents": 4, "blocks": 9, "references": 2, "charts": 0, "blank": 1, "cancel_chains": 6},
            "C03": {"documents": 1, "blocks": 2, "references": 0, "charts": 0, "blank": 0, "cancel_chains": 2},
            "C05": {"documents": 3, "blocks": 9, "references": 0, "charts": 3, "blank": 0, "cancel_chains": 0},
            "C06": {"documents": 1, "blocks": 2, "references": 0, "charts": 0, "blank": 0, "cancel_chains": 0}},
        "expected_roles": {"C02-answer": "statement", "C02-aid-text": "teaching_aid",
            "C02-a-work": "reference", "C02-b-work": "reference", "C03-given-work": "statement",
            "C05-chart-0": "statement", "C05-chart-1": "statement", "C05-chart-2": "statement",
            "C05-aid-0": "teaching_aid", "C05-aid-1": "teaching_aid", "C05-aid-2": "teaching_aid",
            "C05-population-view": "derived_view", "C05-ages-view": "derived_view"},
        "limits": ["无本轮LLM提取测量", "没有新原页或新案例", "表格来自C05同数据重排，不是新识别的原表", "无独立KC定义样例", "未验证合并表格、未知数值图、通用几何或全册覆盖"]})
