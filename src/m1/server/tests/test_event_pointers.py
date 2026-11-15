"""事实引用只接受 JSON Pointer；不得把地址解释成文件路径或表达式。"""

import unittest

from deermind.foundation.system.events.reading import fragment, pointer_parts
from pydantic import JsonValue


class EventPointerTests(unittest.TestCase):
    def test_escaped_keys_arrays_and_root(self) -> None:
        value: JsonValue = {"a/b": {"~": [None, "原文"]}}
        self.assertEqual(fragment(value, pointer_parts("/a~1b/~0/1")), "原文")
        self.assertEqual(fragment(value, pointer_parts("")), value)

    def test_invalid_paths_and_indices_are_rejected(self) -> None:
        for path in ("https://example.com", "file:///tmp/fact", "#pointer", "/bad~", "/bad~2"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                pointer_parts(path)
        for index in ("01", "-1", "+1", "-", "１"):
            with self.subTest(index=index), self.assertRaises(ValueError):
                fragment(["body"], [index])

    def test_missing_field_is_distinct_from_invalid_structure(self) -> None:
        with self.assertRaises(KeyError):
            fragment({}, ["missing"])
        with self.assertRaises(IndexError):
            fragment([], ["0"])
        with self.assertRaises(ValueError):
            fragment("body", ["child"])
