"""Concept: full_time_student_dependent.

Fires when a scenario contains a dependent aged 19-23 who is a
full-time student, exercising IRC §152(c)(3)(A)(ii) — the age
extension for qualifying children.

Without the student exception, qualifying children must be under 19.
Full-time students extend the age limit to under 24, which is a
common VITA intake question and a frequent source of errors.
"""

from typing import Any

from learn.concepts.base import Concept, GenerationHints


class FullTimeStudentDependentConcept(Concept):
    """Fires when a dependent 19-23 is a full-time student."""
    name = "full_time_student_dependent"

    def generation_hints(self) -> GenerationHints:
        return GenerationHints(
            preferred_patterns=[
                "single_parent",
                "married_couple_with_children",
            ],
            force_full_time_student=True,
        )

    def matches(self, scenario: Any) -> bool:
        hh = scenario.household
        if hh is None:
            return False
        for dep in hh.get_dependents():
            if 19 <= dep.age <= 23 and dep.is_full_time_student:
                return True
        return False
