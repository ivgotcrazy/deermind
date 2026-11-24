"""Load immutable prompt resources by the operation's fixed identity and version."""

from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files

from deermind.abstractions.ai.calls import AIRejected
from deermind.abstractions.events import Ref


@dataclass(frozen=True)
class PromptSource:
    """A module declares the package and required parts of its current prompt."""

    package: str
    default: Ref
    parts: tuple[str, ...] = ("instructions",)


class PromptLibrary:
    def __init__(self, sources: Sequence[PromptSource]) -> None:
        self._sources: dict[tuple[str, str, str], PromptSource] = {}
        for source in sources:
            key = (source.default.owner, source.default.type, source.default.id)
            if key in self._sources:
                raise ValueError(f"Duplicate prompt source: {source.default.id}")
            self._sources[key] = source
            self.read(source.default, source.parts)

    def read(self, reference: Ref, parts: Sequence[str]) -> str:
        source = self._sources.get((reference.owner, reference.type, reference.id))
        version = reference.version
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
        for part in parts:
            try:
                # 去掉文件末尾的终止换行，各片段之间的空格和换行由正文声明。
                value = directory.joinpath(f"{part}.md").read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                raise AIRejected("configuration_unavailable") from error
            value = value.removesuffix("\n")
            if not value.strip():
                raise AIRejected("configuration_unavailable")
            pieces.append(value)
        return "".join(pieces)
