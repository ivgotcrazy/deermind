"""Prompt resources resolve an exact version and preserve explicit part order."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from deermind.abstractions.ai.calls import AIRejected
from deermind.abstractions.events import Ref
from deermind.bootstrap.evaluation_operation import PURPOSE, TEACHING
from deermind.bootstrap.prompts import configure_prompts
from deermind.foundation.ai.prompts import PromptLibrary, PromptSource


class PromptResourceTests(TestCase):
    def test_evaluation_prompt_resources_are_packaged_with_the_operation(self) -> None:
        prompts = configure_prompts()
        self.assertIn("method_source", prompts.read(PURPOSE.prompt_ref, ["instructions"]))
        self.assertIn("教学机会", prompts.read(TEACHING.prompt_ref, ["instructions"]))

    def test_default_version_does_not_replace_an_accepted_version(self) -> None:
        first = Ref(owner="evaluation", type="prompt", id="answer", version=1)
        second = first.model_copy(update={"version": 2})
        with (
            TemporaryDirectory() as directory,
            patch("deermind.foundation.ai.prompts.files", return_value=Path(directory)),
        ):
            for number, text in ((1, "old"), (2, "new")):
                path = Path(directory) / "prompts" / "answer" / f"v{number}"
                path.mkdir(parents=True)
                (path / "instructions.md").write_text(f"{text}\n", encoding="utf-8")
                (path / "follow_up.md").write_text("\nfollow-up\n", encoding="utf-8")
            prompts = PromptLibrary(
                [PromptSource("fixture", second, ("instructions", "follow_up"))]
            )
            self.assertEqual(prompts.read(first, ["instructions", "follow_up"]), "old\nfollow-up")
            self.assertEqual(prompts.read(second, ["instructions"]), "new")
            with self.assertRaisesRegex(AIRejected, "configuration_unavailable"):
                prompts.read(first.model_copy(update={"version": 3}), ["instructions"])
            with self.assertRaisesRegex(AIRejected, "configuration_unavailable"):
                prompts.read(first, ["../instructions"])
