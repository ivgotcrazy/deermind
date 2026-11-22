"""E01-16 编解码边界测试，使用合成字节和内存文件替身。"""

import unittest
from hashlib import sha256
from unittest.mock import patch
from uuid import UUID, uuid4

from deermind.infrastructure.files import payload_codec
from deermind.infrastructure.files.payload_codec import (
    ENCODING,
    INLINE_LIMIT,
    RESTORED_LIMIT,
    WIRE_LIMIT,
    PayloadReference,
    RuntimePayloadCodec,
    RuntimePayloadError,
)
from temporalio.api.common.v1 import Payload, Payloads


class MemoryStorage:
    def __init__(self) -> None:
        self.files: dict[UUID, bytes] = {}
        self.by_hash: dict[str, UUID] = {}
        self.writes = 0
        self.reads = 0

    async def save_payload(self, content: bytes, sha256: str) -> UUID:
        self.writes += 1
        file_id = self.by_hash.setdefault(sha256, uuid4())
        self.files.setdefault(file_id, content)
        return file_id

    async def read_payload(self, file_id: UUID, *, byte_size: int, sha256: str) -> bytes:
        self.reads += 1
        return self.files[file_id]


def original(size: int) -> Payload:
    payload = Payload(metadata={"encoding": b"binary/plain", "info": b"\x00\xca"}, data=b"a" * size)
    overhead = payload.ByteSize() - size
    payload.data = payload.data[:-overhead]
    assert payload.ByteSize() == size
    return payload


class RuntimePayloadCodecTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.storage = MemoryStorage()
        self.codec = RuntimePayloadCodec(self.storage)

    async def test_threshold_and_full_payload_round_trip(self) -> None:
        originals = [original(size) for size in (INLINE_LIMIT - 1, INLINE_LIMIT, INLINE_LIMIT + 1)]

        encoded = await self.codec.encode(originals)
        self.assertEqual(encoded[:2], originals[:2])
        self.assertEqual(encoded[2].metadata["encoding"], ENCODING)
        reference = PayloadReference.model_validate_json(encoded[2].data)
        self.assertEqual(
            self.storage.files[reference.storage_ref],
            originals[2].SerializeToString(deterministic=True),
        )
        self.assertEqual(reference.byte_size, INLINE_LIMIT + 1)
        self.assertEqual(await self.codec.decode(encoded), originals)
        self.assertEqual(await self.codec.encode(originals), encoded)
        self.assertEqual(len(self.storage.files), 1)

    async def test_budget_is_symmetric_and_checked_before_file_io(self) -> None:
        large, small = original(INLINE_LIMIT + 1), original(2048)
        limit = large.ByteSize() + small.ByteSize()
        with patch.object(payload_codec, "RESTORED_LIMIT", limit):
            mixed = await self.codec.encode([large, small])
            self.assertEqual(await self.codec.decode(mixed), [large, small])
            read_count, write_count = self.storage.reads, self.storage.writes
            over = original(small.ByteSize() + 1)
            with self.assertLogs("runtime", level="ERROR") as logged:
                with self.assertRaisesRegex(RuntimePayloadError, "^PAYLOAD_BATCH_LIMIT$"):
                    await self.codec.encode([large, over])
                with self.assertRaisesRegex(RuntimePayloadError, "^PAYLOAD_BATCH_LIMIT$"):
                    await self.codec.decode([mixed[0], over])
            self.assertEqual(self.storage.writes, write_count)
            self.assertEqual(self.storage.reads, read_count)
            self.assertEqual(
                [getattr(record, "action", None) for record in logged.records],
                ["payload_codec_encode", "payload_codec_decode"],
            )

    async def test_at_most_wire_limit_with_reference_and_protobuf_framing(self) -> None:
        large = original(INLINE_LIMIT + 1)
        inline = [original(INLINE_LIMIT)] * 7
        reference = (await self.codec.encode([large]))[0]
        remaining = WIRE_LIMIT - Payloads(payloads=[reference, *inline]).ByteSize()
        # 预算余量在同一长度前缀区间。通过真实封装计算末项的外层开销。
        last = original(remaining)
        overhead = Payloads(payloads=[last]).ByteSize() - last.ByteSize()
        exact = original(remaining - overhead)
        accepted = await self.codec.encode([large, *inline, exact])
        self.assertEqual(Payloads(payloads=accepted).ByteSize(), WIRE_LIMIT)
        write_count = self.storage.writes
        with self.assertLogs("runtime", level="ERROR"):
            with self.assertRaisesRegex(RuntimePayloadError, "^PAYLOAD_WIRE_LIMIT$"):
                await self.codec.encode([large, *inline, original(exact.ByteSize() + 1)])
        self.assertEqual(self.storage.writes, write_count)

    async def test_old_inline_remains_readable(self) -> None:
        old = original(WIRE_LIMIT + 1)
        self.assertEqual(await self.codec.decode([old]), [old])
        self.assertEqual(self.storage.reads, 0)

    async def test_large_reference_rejected_before_read(self) -> None:
        forged = PayloadReference(
            format_version=1, storage_ref=uuid4(), byte_size=RESTORED_LIMIT + 1, sha256="a" * 64
        )
        with self.assertLogs("runtime", level="ERROR"):
            with self.assertRaisesRegex(RuntimePayloadError, "^PAYLOAD_BATCH_LIMIT$"):
                await self.codec.decode([forged.to_payload()])
        self.assertEqual(self.storage.reads, 0)

    async def test_decode_rejects_bad_formats_without_opening_files(self) -> None:
        encoded = (await self.codec.encode([original(INLINE_LIMIT + 1)]))[0]
        bad_references = [
            Payload(metadata={"encoding": ENCODING + b"-unknown"}, data=encoded.data),
            Payload(metadata={"encoding": ENCODING, "extra": b"secret"}, data=encoded.data),
            Payload(
                metadata={"encoding": ENCODING},
                data=encoded.data.replace(b'"format_version":1', b'"format_version":true'),
            ),
            Payload(metadata={"encoding": ENCODING}, data=b'{"extra":"secret"}'),
        ]
        for invalid in bad_references:
            with (
                self.subTest(encoding=invalid.metadata["encoding"]),
                self.assertLogs("runtime", level="ERROR") as logged,
            ):
                with self.assertRaisesRegex(RuntimePayloadError, "^PAYLOAD_FORMAT_INVALID$"):
                    await self.codec.decode([encoded, invalid])
                self.assertNotIn("secret", str(logged.output))
        self.assertEqual(self.storage.reads, 0)

    async def test_missing_corrupt_or_invalid_protobuf_is_a_fault(self) -> None:
        encoded = (await self.codec.encode([original(INLINE_LIMIT + 1)]))[0]
        reference = PayloadReference.model_validate_json(encoded.data)
        intact = self.storage.files.pop(reference.storage_ref)
        with self.assertLogs("runtime", level="ERROR"):
            with self.assertRaisesRegex(RuntimePayloadError, "^PAYLOAD_STORAGE_READ_FAILED$"):
                await self.codec.decode([encoded])
            for corrupt in (intact[:-1], intact[:-1] + b"\x00"):
                self.storage.files[reference.storage_ref] = corrupt
                with self.assertRaisesRegex(RuntimePayloadError, "^PAYLOAD_INTEGRITY_FAILED$"):
                    await self.codec.decode([encoded])

            malformed = b"\x0a"
            self.storage.files[reference.storage_ref] = malformed
            matching = PayloadReference(
                format_version=1,
                storage_ref=reference.storage_ref,
                byte_size=len(malformed),
                sha256=sha256(malformed).hexdigest(),
            )
            with self.assertRaisesRegex(RuntimePayloadError, "^PAYLOAD_FORMAT_INVALID$"):
                await self.codec.decode([matching.to_payload()])


if __name__ == "__main__":
    unittest.main()
