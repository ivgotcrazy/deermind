"""按 Operation 固定的身份与版本加载不可变提示词资源。

分层定位：foundation（AI 底座）
对外契约：PromptSource 供装配层登记；PromptLibrary 按引用读取指令片段。
边界约束：只读取包内 prompts 目录下固定版本的 md 文件，不做模板渲染或业务拼装。
"""

from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files

from deermind.abstractions.ai.calls import AIRejected
from deermind.abstractions.events import Ref


@dataclass(frozen=True)
class PromptSource:
    """一个模块登记提示词所在包、默认引用与所需片段。"""

    package: str
    default: Ref
    parts: tuple[str, ...] = ("instructions",)


class PromptLibrary:
    """提示词库：按身份索引已登记来源，并按固定版本读取片段正文。"""

    def __init__(self, sources: Sequence[PromptSource]) -> None:
        """登记各提示词来源；重复身份报错，并在构造时预检默认片段可读。"""
        self._sources: dict[tuple[str, str, str], PromptSource] = {}
        # 逐条登记来源；身份重复报错，构造时即预检默认片段可读。
        for source in sources:
            key = (source.default.owner, source.default.type, source.default.id)
            # 同一身份重复登记会导致提示词定位歧义。
            if key in self._sources:
                raise ValueError(f"Duplicate prompt source: {source.default.id}")
            self._sources[key] = source
            self.read(source.default, source.parts)

    def read(self, reference: Ref, parts: Sequence[str]) -> str:
        """按引用的身份与版本读取指定片段；版本不符、片段未登记或文件缺失均拒绝。"""
        source = self._sources.get((reference.owner, reference.type, reference.id))
        version = reference.version
        # 未登记身份、缺版本、版本不符、片段为空或片段未登记，均拒绝读取。
        if (
            source is None
            or version is None
            or reference.model_copy(update={"version": source.default.version}) != source.default
            or not parts
            or any(part not in source.parts for part in parts)
        ):
            raise AIRejected("configuration_unavailable")
        directory = files(source.package).joinpath("prompts", source.default.id, f"v{version}")
        pieces: list[str] = []
        # 逐条读取所请求片段，拼成完整提示词。
        for part in parts:
            try:
                # 去掉文件末尾的终止换行，各片段之间的空格和换行由正文声明。
                value = directory.joinpath(f"{part}.md").read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                # 文件缺失或编码异常，按配置不可用拒绝。
                raise AIRejected("configuration_unavailable") from error
            value = value.removesuffix("\n")
            # 片段正文为空属资源损坏，拒绝拼接。
            if not value.strip():
                raise AIRejected("configuration_unavailable")
            pieces.append(value)
        return "".join(pieces)
