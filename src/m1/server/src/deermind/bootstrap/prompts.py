"""Link each operation's prompt reference to its own packaged resources."""

from deermind.bootstrap.book_operation import OUTLINE
from deermind.bootstrap.book_operation import TEACHING as BOOK_TEACHING
from deermind.bootstrap.domain_operation import PURPOSE as ANALYSIS
from deermind.bootstrap.evaluation_operation import PURPOSE as SUBMISSION
from deermind.bootstrap.evaluation_operation import TEACHING
from deermind.bootstrap.material_operation import PURPOSE as EXTRACTION
from deermind.bootstrap.student_operation import PURPOSE as CONVERSATION
from deermind.bootstrap.supply_operation import CHECK, GENERATE
from deermind.foundation.ai.prompts import PromptLibrary, PromptSource


def configure_prompts() -> PromptLibrary:
    return PromptLibrary(
        [
            PromptSource("deermind.product.materials", EXTRACTION.prompt_ref),
            PromptSource("deermind.product.materials", OUTLINE.prompt_ref),
            PromptSource("deermind.product.materials", BOOK_TEACHING.prompt_ref),
            PromptSource(
                "deermind.spaces.domain",
                ANALYSIS.prompt_ref,
                ("instructions", "extract", "compare"),
            ),
            PromptSource("deermind.spaces.domain", GENERATE.prompt_ref),
            PromptSource("deermind.spaces.domain", CHECK.prompt_ref),
            PromptSource(
                "deermind.spaces.interaction",
                CONVERSATION.prompt_ref,
                ("instructions", "after_round", "after_evaluation", "summary", "check_teaching"),
            ),
            PromptSource("deermind.spaces.evaluation", SUBMISSION.prompt_ref),
            PromptSource("deermind.spaces.evaluation", TEACHING.prompt_ref),
        ]
    )
