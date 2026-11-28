"""有序正文、固定来源及文字、公式、图表的结构约束。"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, localcontext
from re import fullmatch
from typing import Annotated, Literal, LiteralString, NoReturn, Self
from uuid import UUID

from pydantic import Field, FiniteFloat, ValidationError, model_validator
from pydantic_core import PydanticCustomError

from deermind.abstractions.events import FactModel, NonEmpty

_DECIMAL_PATTERN = r"^[+-]?[0-9]+(?:\.[0-9]+)?$"

type Location = tuple[str | int, ...]
type DecimalText = Annotated[str, Field(pattern=_DECIMAL_PATTERN)]
type Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
type Position = Annotated[list[FiniteFloat], Field(min_length=2, max_length=2)]
type Rectangle = Annotated[list[FiniteFloat], Field(min_length=4, max_length=4)]
type JsonUuid = Annotated[UUID, Field(strict=False)]
type Shape = Literal["circle", "ellipse", "triangle", "square", "pentagon", "hexagon", "point"]


def invalid(title: str, path: Location, message: LiteralString) -> NoReturn:
    """将规则错误定位到字段，避免在错误中回显请求正文。"""
    raise ValidationError.from_exception_data(
        title,
        [
            {
                "type": PydanticCustomError("invalid_content", message),
                "loc": path,
                "input": None,
            }
        ],
    )


def identifiers(values: Iterable[str], path: Location, field: str) -> set[str]:
    seen: set[str] = set()
    for index, value in enumerate(values):
        if value in seen:
            # 编号重复，定位到具体条目报错。
            invalid("RichContent", (*path, index, field), "同一内容内的编号必须唯一。")
        seen.add(value)
    return seen


class FileSource(FactModel):
    type: Literal["file"]
    file_id: JsonUuid
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class EventPartSource(FactModel):
    type: Literal["event_part"]
    event_id: JsonUuid
    record_id: NonEmpty | None = None
    path: Annotated[str, Field(pattern=r"^(?:/(?:[^/~]|~[01])*)*$")]


class SourceRef(FactModel):
    """来源固定到文件与校验值，或固定事件中的一个片段。"""

    source_id: NonEmpty
    owner: NonEmpty
    ref: Annotated[FileSource | EventPartSource, Field(discriminator="type")]
    file_page: Annotated[int, Field(ge=1)] | None = None
    printed_page: NonEmpty | None = None
    region: Rectangle | None = None

    @model_validator(mode="after")
    def validate_region(self) -> Self:
        if self.region is not None:
            left, top, right, bottom = self.region
            if left < 0 or top < 0 or left >= right or top >= bottom:
                # 区域坐标须非负且右/下大于左/上。
                invalid("SourceRef", ("region",), "来源区域必须按左、上、右、下记录。")
        return self


class Provenance(FactModel):
    source_refs: list[NonEmpty]
    transformation: Literal["extracted", "normalized", "derived", "generated"]
    note: str = ""


class MathNumber(FactModel):
    op: Literal["number"]
    value: DecimalText
    cancel_to: list[DecimalText] = Field(default_factory=list[DecimalText])


class MathSymbol(FactModel):
    op: Literal["symbol"]
    name: NonEmpty


class MathGroup(FactModel):
    op: Literal["group"]
    args: Annotated[list[MathExpression], Field(min_length=1, max_length=1)]


class MathBinary(FactModel):
    op: Literal["add", "subtract", "multiply", "divide", "fraction", "equal"]
    args: Annotated[list[MathExpression], Field(min_length=2, max_length=2)]


type MathExpression = Annotated[
    MathNumber | MathSymbol | MathGroup | MathBinary, Field(discriminator="op")
]


class TextSpan(FactModel):
    type: Literal["text"]
    text: str


class MathSpan(FactModel):
    type: Literal["math"]
    expression: MathExpression


class BlankSpan(FactModel):
    type: Literal["response_blank"]
    label: NonEmpty


class Paragraph(FactModel):
    spans: list[Annotated[TextSpan | MathSpan | BlankSpan, Field(discriminator="type")]]


class MathLine(FactModel):
    expression: MathExpression
    relation: Literal["", "=", "≈", "→"] = ""
    suffix: str = ""


class MathSequence(FactModel):
    purpose: Literal["given_work", "reference_work"]
    lines: Annotated[list[MathLine], Field(min_length=1)]


class ProvidedCell(FactModel):
    state: Literal["provided"]
    value: str


class MissingCell(FactModel):
    state: Literal["response_blank", "source_missing", "unreadable"]


type DataCell = Annotated[ProvidedCell | MissingCell, Field(discriminator="state")]


class DataColumn(FactModel):
    key: NonEmpty
    label: NonEmpty
    value_type: Literal["text", "decimal"]
    unit: str


class DataRow(FactModel):
    row_id: NonEmpty
    cells: dict[NonEmpty, DataCell]


class DataTable(FactModel):
    data_id: NonEmpty
    columns: Annotated[list[DataColumn], Field(min_length=1)]
    rows: list[DataRow]
    provenance: Provenance

    @model_validator(mode="after")
    def validate_rows(self) -> Self:
        columns = identifiers((column.key for column in self.columns), ("columns",), "key")
        identifiers((row.row_id for row in self.rows), ("rows",), "row_id")
        for index, row in enumerate(self.rows):
            if row.cells.keys() != columns:
                # 行单元格集合须与列定义完全一致。
                invalid(
                    "DataTable",
                    ("rows", index, "cells"),
                    "单元格必须与列定义一一对应。",
                )
            for column in self.columns:
                cell = row.cells[column.key]
                if isinstance(cell, ProvidedCell) and column.value_type == "decimal":
                    # 已提供的数值列须通过十进制格式校验。
                    check_decimal_cell(cell.value, ("rows", index, "cells", column.key, "value"))
        return self


def check_decimal_cell(value: str, path: Location) -> None:
    if fullmatch(_DECIMAL_PATTERN, value) is None:
        invalid("DataTable", path, "数值单元格必须使用十进制字符串。")


class Table(FactModel):
    data_ref: NonEmpty
    caption: str


class ChartAxis(FactModel):
    min: DecimalText
    max: DecimalText
    step: DecimalText
    label: str

    @model_validator(mode="after")
    def validate_scale(self) -> Self:
        if Decimal(self.min) >= Decimal(self.max):
            invalid("ChartAxis", ("max",), "坐标轴上限必须大于下限。")
        if Decimal(self.step) <= 0:
            invalid("ChartAxis", ("step",), "坐标轴刻度间隔必须大于零。")
        return self


class ChartSeries(FactModel):
    column: NonEmpty
    label: NonEmpty
    color: Color


class Chart(FactModel):
    kind: Literal["bar", "line", "pie"]
    caption: str
    data_ref: NonEmpty
    category_column: NonEmpty
    series: Annotated[list[ChartSeries], Field(min_length=1)]
    axis: ChartAxis | None
    legend: bool
    unit: str
    relationship: Literal["independent", "overlapping_populations", "disjoint_parts"]
    stacked: Literal[False] = False
    slice_colors: list[Color] = Field(default_factory=list[Color])

    @model_validator(mode="after")
    def validate_axes(self) -> Self:
        identifiers((series.column for series in self.series), ("series",), "column")
        if self.kind == "pie":
            # 扇形图：无坐标轴、单列、百分比、互不重叠组成。
            if self.axis is not None:
                invalid("Chart", ("axis",), "扇形图不使用坐标轴。")
            if len(self.series) != 1:
                invalid("Chart", ("series",), "扇形图只使用一列数值。")
            if self.unit != "%":
                invalid("Chart", ("unit",), "首批扇形图使用百分比。")
            if self.relationship != "disjoint_parts":
                invalid("Chart", ("relationship",), "扇形图需要互不重叠的组成部分。")
        else:
            # 柱/折线图：必须有坐标轴，且不挂扇区颜色。
            if self.axis is None:
                invalid("Chart", ("axis",), "柱状图和折线图需要坐标轴。")
            if self.slice_colors:
                invalid("Chart", ("slice_colors",), "扇区颜色只用于扇形图。")
        return self


class DiagramObject(FactModel):
    object_id: NonEmpty
    shape: Shape
    label: str = ""


class DiagramRelation(FactModel):
    predicate: Literal["inside"]
    subject: NonEmpty
    object: NonEmpty
    basis: Literal["source_text", "source_mark", "visual_observation"]
    source_refs: list[NonEmpty]


class DiagramBox(FactModel):
    object_ref: NonEmpty
    box: Rectangle


class DiagramPoint(FactModel):
    object_ref: NonEmpty
    position: Position


class DiagramLayout(FactModel):
    view_box: Rectangle
    boxes: list[DiagramBox]
    points: list[DiagramPoint]


class Diagram(FactModel):
    caption: str
    objects: Annotated[list[DiagramObject], Field(min_length=1)]
    relations: list[DiagramRelation]
    layout: DiagramLayout

    @model_validator(mode="after")
    def validate_refs(self) -> Self:
        """验证图形关系和显示引用，布局坐标不参与关系推断。"""
        identifiers((item.object_id for item in self.objects), ("objects",), "object_id")
        points = {item.object_id for item in self.objects if item.shape == "point"}
        shapes = {item.object_id for item in self.objects if item.shape != "point"}
        for index, relation in enumerate(self.relations):
            if relation.subject not in points:
                # 起点须是图中的点对象。
                invalid(
                    "Diagram",
                    ("relations", index, "subject"),
                    "关系起点必须引用图中的点。",
                )
            if relation.object not in shapes:
                # 目标须是图中的形状对象。
                invalid(
                    "Diagram",
                    ("relations", index, "object"),
                    "关系目标必须引用图中的形状。",
                )
        if min(self.layout.view_box[2:]) <= 0:
            invalid("Diagram", ("layout", "view_box"), "图形视区宽高必须为正。")
        boxes = identifiers(
            (box.object_ref for box in self.layout.boxes),
            ("layout", "boxes"),
            "object_ref",
        )
        marks = identifiers(
            (point.object_ref for point in self.layout.points),
            ("layout", "points"),
            "object_ref",
        )
        if boxes != shapes:
            # 矩形排布与形状对象一一对应。
            invalid("Diagram", ("layout", "boxes"), "每个形状需要一份对应的排布。")
        if marks != points:
            # 点排布与点对象一一对应。
            invalid("Diagram", ("layout", "points"), "每个点需要一份对应的排布。")
        for index, box in enumerate(self.layout.boxes):
            if min(box.box[2:]) <= 0:
                invalid(
                    "Diagram",
                    ("layout", "boxes", index, "box"),
                    "形状排布宽高必须为正。",
                )
        return self


class _Block(FactModel):
    block_id: NonEmpty
    provenance: Provenance


class ParagraphBlock(_Block):
    type: Literal["paragraph"]
    payload: Paragraph


class MathSequenceBlock(_Block):
    type: Literal["math_sequence"]
    payload: MathSequence


class TableBlock(_Block):
    type: Literal["table"]
    payload: Table


class ChartBlock(_Block):
    type: Literal["chart"]
    payload: Chart


class DiagramBlock(_Block):
    type: Literal["diagram"]
    payload: Diagram


type ContentBlock = Annotated[
    ParagraphBlock | MathSequenceBlock | TableBlock | ChartBlock | DiagramBlock,
    Field(discriminator="type"),
]


def check_sources(refs: list[str], known: set[str], path: Location) -> None:
    for index, reference in enumerate(refs):
        if reference not in known:
            invalid("RichContent", (*path, index), "来源未在当前正文中登记。")


def check_chart_data(chart: Chart, table: DataTable, path: Location) -> None:
    columns = {column.key: column for column in table.columns}
    category = columns.get(chart.category_column)
    if category is None or category.value_type != "text":
        # 分类列必须存在且为文字列。
        invalid("RichContent", (*path, "category_column"), "图表分类必须引用文字列。")
    if chart.slice_colors and len(chart.slice_colors) != len(table.rows):
        invalid("RichContent", (*path, "slice_colors"), "每个类别需要一份对应的扇区颜色。")
    scale = (Decimal(chart.axis.min), Decimal(chart.axis.max)) if chart.axis else None
    for index, series in enumerate(chart.series):
        column_path = (*path, "series", index, "column")
        column = columns.get(series.column)
        if column is None or column.value_type != "decimal":
            # 数值列必须存在且为十进制类型。
            invalid("RichContent", column_path, "图表数列必须引用数值列。")
        if column.unit != chart.unit:
            invalid("RichContent", column_path, "数列单位与图表单位不一致。")
        samples: list[Decimal] = []
        for row in table.rows:
            cell = row.cells[series.column]
            if isinstance(cell, ProvidedCell):
                samples.append(Decimal(cell.value))
        if scale is not None and any(not scale[0] <= value <= scale[1] for value in samples):
            invalid("RichContent", column_path, "坐标轴范围会裁掉数列中的数据。")
        if chart.kind == "pie":
            if any(not 0 <= value <= 100 for value in samples):
                invalid("RichContent", column_path, "扇区比例须在 0 至 100 之间。")
            if samples and len(samples) == len(table.rows):
                # 每行都有值时，校验完整扇形比例和为 100。
                # 按源值小数位求和，避免先四舍五入后把不完整扇形误判为整圆。
                with localcontext() as arithmetic:
                    decimal_places = max(-int(value.as_tuple().exponent) for value in samples)
                    arithmetic.prec = 4 + decimal_places + len(str(len(samples)))
                    if sum(samples, Decimal(0)) != 100:
                        invalid("RichContent", column_path, "完整扇形图的比例总和须为 100。")


class RichContent(FactModel):
    """业务对象中按用途存放的一份正文，图表按局部数据编号引用。"""

    schema_version: Literal["1"]
    role: Literal["definition", "statement", "reference", "teaching_aid", "derived_view"]
    blocks: list[ContentBlock]
    data_tables: list[DataTable]
    source_refs: list[SourceRef]

    @model_validator(mode="after")
    def validate_refs(self) -> Self:
        known = identifiers(
            (source.source_id for source in self.source_refs),
            ("source_refs",),
            "source_id",
        )
        identifiers((block.block_id for block in self.blocks), ("blocks",), "block_id")
        identifiers((table.data_id for table in self.data_tables), ("data_tables",), "data_id")
        tables = {table.data_id: table for table in self.data_tables}

        for index, table in enumerate(self.data_tables):
            check_sources(
                table.provenance.source_refs,
                known,
                ("data_tables", index, "provenance", "source_refs"),
            )
        for index, block in enumerate(self.blocks):
            path = ("blocks", index)
            check_sources(
                block.provenance.source_refs,
                known,
                (*path, "provenance", "source_refs"),
            )
            if isinstance(block, MathSequenceBlock):
                if self.role == "statement" and block.payload.purpose == "reference_work":
                    # 题面正文不得夹带参考解法。
                    invalid(
                        "RichContent",
                        (*path, "payload", "purpose"),
                        "题面不能包含参考解法。",
                    )
            elif isinstance(block, (ChartBlock, TableBlock)):
                table = tables.get(block.payload.data_ref)
                if table is None:
                    # 块引用的数据表未在正文登记。
                    invalid(
                        "RichContent",
                        (*path, "payload", "data_ref"),
                        "图表引用了不存在的数据表。",
                    )
                if isinstance(block, ChartBlock):
                    check_chart_data(block.payload, table, (*path, "payload"))
            elif isinstance(block, DiagramBlock):
                # 图形关系逐条核对来源引用。
                for relation_index, relation in enumerate(block.payload.relations):
                    check_sources(
                        relation.source_refs,
                        known,
                        (*path, "payload", "relations", relation_index, "source_refs"),
                    )
        return self


def paragraph(text: str, role: Literal["statement", "reference", "definition"]) -> RichContent:
    return RichContent.model_validate(
        {
            "schema_version": "1",
            "role": role,
            "source_refs": [],
            "data_tables": [],
            "blocks": [
                {
                    "block_id": "p",
                    "type": "paragraph",
                    "provenance": {"source_refs": [], "transformation": "generated"},
                    "payload": {"spans": [{"type": "text", "text": text}]},
                }
            ],
        }
    )
