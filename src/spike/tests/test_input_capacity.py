import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure, load_config


def transport():
    return Mock(return_value={'choices': [{'finish_reason': 'stop',
                 'message': {'content': '{"ok":true}'}}]})


class InputCapacityTests(unittest.TestCase):
    def test_default_sends_messages_above_previous_limit_intact(self):
        messages = [{'role': 'user', 'content': '\u4e2d' * 24000}]
        wire = transport()
        adapter = DeepSeekAdapter(LLMConfig('test-key'), wire)
        adapter.complete(messages, 'capacity')
        self.assertEqual(adapter.config.public()['max_input_chars'], 64000)
        self.assertEqual(wire.call_args.args[2]['messages'], messages)
        self.assertEqual(adapter.records[0]['input_chars'],
                         len(json.dumps(messages, ensure_ascii=False)))

    def test_exact_limit_allowed_and_one_character_over_rejected_without_call(self):
        messages = [{'role': 'user', 'content': '\u4e2d'}]
        size = len(json.dumps(messages, ensure_ascii=False))
        wire = transport()
        adapter = DeepSeekAdapter(LLMConfig('test-key', max_input_chars=size), wire)
        adapter.complete(messages, 'at-limit')
        with self.assertRaisesRegex(ModelFailure, '^InputLimitExceeded$'):
            adapter.complete([{'role': 'user', 'content': '\u4e2d\u4e2d'}], 'over-limit')
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(len(adapter.records), 1)
        self.assertEqual(wire.call_count, 1)
        self.assertEqual(adapter.input_rejections, [{'purpose': 'over-limit',
                         'input_chars': size + 1, 'max_input_chars': size}])

    def test_old_limit_can_be_selected_for_historical_replay(self):
        wire = transport()
        adapter = DeepSeekAdapter(LLMConfig('test-key', max_input_chars=16000), wire)
        with self.assertRaisesRegex(ModelFailure, 'InputLimitExceeded'):
            adapter.complete([{'role': 'user', 'content': 'x' * 20000}], 'old-cap')
        wire.assert_not_called()
        self.assertEqual(adapter.calls, 0)

    def test_env_file_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('DEERMIND_LLM_MAX_INPUT_CHARS=80000\n', encoding='utf-8')
            self.assertEqual(load_config(root, {}).max_input_chars, 80000)
            self.assertEqual(load_config(root, {'DEERMIND_LLM_MAX_INPUT_CHARS': '96000'}).max_input_chars, 96000)

    def test_invalid_limits_and_sanitized_config_errors(self):
        for value in (0, -1, True, 1.5, '64000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                LLMConfig('test-key', max_input_chars=value)
        with tempfile.TemporaryDirectory() as directory:
            for value in ('0', '-1', 'secret-invalid-value'):
                with self.subTest(value=value), self.assertRaises(ValueError) as caught:
                    load_config(Path(directory), {'DEERMIND_LLM_MAX_INPUT_CHARS': value})
                self.assertNotIn(value, str(caught.exception))


if __name__ == '__main__':
    unittest.main()
