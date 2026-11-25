"""通过现有共享文件区外置完整 Temporal Payload。"""

import asyncio
import logging
from collections.abc import Sequence
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID

from deermind.abstractions.files import PayloadStorage
from google.protobuf.message import DecodeError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from temporalio.api.common.v1 import Payload, Payloads
from temporalio.converter import PayloadCodec

INLINE_LIMIT = 128 * 1024
RESTORED_LIMIT = 64 * 1024 * 1024
WIRE_LIMIT = 1024 * 1024
ENCODING_PREFIX = b"binary/deermind-runtime-payload"
ENCODING = ENCODING_PREFIX + b"/v1"
LOGGER = logging.getLogger("runtime")


class PayloadReference(BaseModel):
    """只接受本版本的固定字段与不透明文件身份。"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    format_version: Annotated[int, Field(ge=1, le=1)]
    storage_ref: UUID
    byte_size: Annotated[int, Field(gt=0)]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]

    def to_payload(self) -> Payload:
        return Payload(metadata={"encoding": ENCODING}, data=self.model_dump_json().encode())


class RuntimePayloadError(ValueError):
    """错误消息只包含稳定技术码，避免把原始内容写入诊断或历史。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _fault(
    stage: Literal["encode", "decode"], code: str, reference: PayloadReference | None = None
) -> RuntimePayloadError:
    details = {"action": f"payload_codec_{stage}", "outcome": "failed", "error_code": code}
    if reference is None:
        # 编码阶段失败，无文件引用可记录。
        LOGGER.error("Temporal 载荷处理失败", extra=details)
    else:
        # 解码阶段失败，附带存储引用便于定位，不回显载荷内容。
        LOGGER.error("Temporal 载荷恢复失败，文件引用 %s", reference.storage_ref, extra=details)
    return RuntimePayloadError(code)


def _serialize(payload: Payload) -> tuple[bytes, str]:
    content = payload.SerializeToString(deterministic=True)
    return content, sha256(content).hexdigest()


def _restore(content: bytes, reference: PayloadReference) -> Payload:
    if len(content) != reference.byte_size or sha256(content).hexdigest() != reference.sha256:
        # 长度或摘要与引用不符，判定外置文件被篡改或损坏。
        raise _fault("decode", "PAYLOAD_INTEGRITY_FAILED", reference)
    try:
        payload = Payload.FromString(content)
    except DecodeError:
        # 字节无法还原为 protobuf Payload。
        raise _fault("decode", "PAYLOAD_FORMAT_INVALID", reference) from None
    if payload.metadata.get("encoding", b"").startswith(ENCODING_PREFIX):
        # 恢复出的载荷不得再是外置引用，避免嵌套外置。
        raise _fault("decode", "PAYLOAD_FORMAT_INVALID", reference)
    return payload


class RuntimePayloadCodec(PayloadCodec):
    """按完整 protobuf 字节实行批次限额，历史中只记录就绪的外置引用。"""

    def __init__(self, storage: PayloadStorage) -> None:
        self._storage = storage

    async def encode(self, payloads: Sequence[Payload]) -> list[Payload]:
        # 先核对全部预算再写文件。UUID 和摘要固定宽度，预检占位与实际引用等长。
        sizes: list[int] = []
        restored_size = 0
        wire_size = 0
        for payload in payloads:
            if payload.metadata.get("encoding", b"").startswith(ENCODING_PREFIX):
                # 待编码载荷不应已是外置引用，拒绝嵌套。
                raise _fault("encode", "PAYLOAD_FORMAT_INVALID")
            size = payload.ByteSize()
            sizes.append(size)
            restored_size += size
            if restored_size > RESTORED_LIMIT:
                # 还原后批次总量超限，先于写文件拦截。
                raise _fault("encode", "PAYLOAD_BATCH_LIMIT")
            wire_payload = payload
            if size > INLINE_LIMIT:
                # 超内联阈值的元素先占位为等长引用，用于预检线上字节预算。
                wire_payload = PayloadReference(
                    format_version=1, storage_ref=UUID(int=0), byte_size=size, sha256="0" * 64
                ).to_payload()
            # 每个元素的外层字段长度也计入预算，包括长度前缀。
            wire_size += Payloads(payloads=[wire_payload]).ByteSize()
            if wire_size > WIRE_LIMIT:
                # 线上传输字节超限，拒绝编码。
                raise _fault("encode", "PAYLOAD_WIRE_LIMIT")

        encoded: list[Payload] = []
        for payload, size in zip(payloads, sizes, strict=True):
            if size <= INLINE_LIMIT:
                # 小载荷随历史内联保存。
                encoded.append(payload)
                continue
            content, digest = await asyncio.to_thread(_serialize, payload)
            if len(content) != size:
                # 序列化结果与预检大小不符，拒绝落盘。
                raise _fault("encode", "PAYLOAD_FORMAT_INVALID")
            try:
                file_id = await self._storage.save_payload(content, digest)
            except Exception:
                # 外置存储写入失败，统一收敛为稳定错误码。
                raise _fault("encode", "PAYLOAD_STORAGE_WRITE_FAILED") from None
            encoded.append(
                PayloadReference(
                    format_version=1, storage_ref=file_id, byte_size=size, sha256=digest
                ).to_payload()
            )
        return encoded

    async def decode(self, payloads: Sequence[Payload]) -> list[Payload]:
        # 先累计内联实际长度及外置声明长度，超限批次一律不发起文件读取。
        references: list[PayloadReference | None] = []
        restored_size = 0
        for payload in payloads:
            encoding = payload.metadata.get("encoding", b"")
            reference = None
            if encoding.startswith(ENCODING_PREFIX):
                if encoding != ENCODING or len(payload.metadata) != 1:
                    # 编码版本不符或携带多余元数据，拒绝恢复。
                    raise _fault("decode", "PAYLOAD_FORMAT_INVALID")
                try:
                    reference = PayloadReference.model_validate_json(payload.data)
                except ValidationError:
                    # 引用字段不符合固定合同。
                    raise _fault("decode", "PAYLOAD_FORMAT_INVALID") from None
            references.append(reference)
            restored_size += payload.ByteSize() if reference is None else reference.byte_size
            if restored_size > RESTORED_LIMIT:
                # 还原批次总量超限，不发起后续文件读取。
                raise _fault("decode", "PAYLOAD_BATCH_LIMIT", reference)

        decoded: list[Payload] = []
        for payload, reference in zip(payloads, references, strict=True):
            if reference is None:
                # 内联载荷直接还原。
                decoded.append(payload)
                continue
            try:
                content = await self._storage.read_payload(
                    reference.storage_ref, byte_size=reference.byte_size, sha256=reference.sha256
                )
            except Exception:
                # 外置文件读取或校验失败，收敛为稳定错误码。
                raise _fault("decode", "PAYLOAD_STORAGE_READ_FAILED", reference) from None
            decoded.append(await asyncio.to_thread(_restore, content, reference))
        return decoded
