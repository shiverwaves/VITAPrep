"""
Scenario store — SQLite persistence for generated scenarios, submissions, and grades.

Database: data/scenarios.sqlite (created at runtime, gitignored)
"""

import logging
from typing import Optional, List

from generator.models import Scenario, GradingResult

logger = logging.getLogger(__name__)


class ScenarioStore:
    """CRUD for scenarios, submissions, and grades."""

    def __init__(self, db_path: str = "data/scenarios.sqlite"):
        # TODO: Initialize SQLite, create tables if not exist
        pass

    def save_scenario(self, scenario: Scenario) -> str:
        """Save a generated scenario. Returns scenario_id."""
        pass

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """Retrieve a scenario by ID."""
        pass

    def save_grade(self, scenario_id: str, result: GradingResult) -> None:
        """Save grading result for a scenario."""
        pass

    def get_progress(self) -> List[dict]:
        """Get student progress history."""
        pass
