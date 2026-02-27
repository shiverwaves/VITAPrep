"""
Child generator — Part 1 of VITA intake.

Generates child household members based on parent demographics and
PUMS distributions.

Reference: HouseholdRNG/generator/child_generator.py — adapted for
VITAPrep's distribution table schemas and incremental pipeline design.

Required distribution tables:
    children_by_parent_age   — number of children by parent age bracket
    child_age_distributions  — child age weights by relationship type

Optional tables:
    stepchild_patterns       — stepchild counts for blended families
    adult_child_ages         — ages of adult children still at home
"""

import logging
import uuid
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .models import Household, Person, RelationshipType, PATTERN_METADATA
from .sampler import match_age_bracket, weighted_sample

logger = logging.getLogger(__name__)


# Patterns that can include children
PATTERNS_WITH_CHILDREN = frozenset({
    'married_couple_with_children',
    'single_parent',
    'blended_family',
    'multigenerational',
    'unmarried_partners',
    'other',
})

# Patterns that MUST have at least one child
PATTERNS_REQUIRING_CHILDREN = frozenset({
    'married_couple_with_children',
    'single_parent',
    'blended_family',
})


class ChildGenerator:
    """Generates child household members with demographics only.

    Required tables:
        children_by_parent_age, child_age_distributions

    Optional tables:
        stepchild_patterns, adult_child_ages
    """

    _REQUIRED_TABLES = [
        'children_by_parent_age',
        'child_age_distributions',
    ]

    _OPTIONAL_TABLES = [
        'stepchild_patterns',
        'adult_child_ages',
    ]

    def __init__(self, distributions: Dict[str, pd.DataFrame]) -> None:
        """Initialize with loaded distribution tables.

        Args:
            distributions: Dictionary of table name -> DataFrame.
        """
        self.distributions = distributions
        self._validate_required_tables()

    def _validate_required_tables(self) -> None:
        """Log warnings for missing distribution tables."""
        missing = [t for t in self._REQUIRED_TABLES
                   if t not in self.distributions]
        if missing:
            logger.warning("Missing required child tables: %s", missing)

        missing_opt = [t for t in self._OPTIONAL_TABLES
                       if t not in self.distributions]
        if missing_opt:
            logger.debug(
                "Missing optional child tables (will use defaults): %s",
                missing_opt,
            )

    # =================================================================
    # Public API
    # =================================================================

    def generate_children(self, household: Household) -> List[Person]:
        """Generate child members based on household pattern and parents.

        Args:
            household: Household with adult members already populated.

        Returns:
            List of child Person objects with demographics populated
            (age, sex, race, hispanic_origin, relationship,
            is_dependent, can_be_claimed, months_in_home).
        """
        pattern = household.pattern

        if pattern not in PATTERNS_WITH_CHILDREN:
            logger.debug("Pattern '%s' does not have children", pattern)
            return []

        adults = household.get_adults()
        if not adults:
            logger.warning("No adults in household; cannot generate children")
            return []

        num_children = self._determine_child_count(household, adults)
        if num_children == 0:
            return []

        relationships = self._assign_child_relationships(
            pattern, num_children, household,
        )

        children: List[Person] = []
        for relationship in relationships:
            child = self._generate_single_child(
                household=household,
                adults=adults,
                relationship=relationship,
                existing_children=children,
            )
            children.append(child)

        logger.debug(
            "Generated %d children for pattern '%s'", len(children), pattern,
        )
        return children

    # =================================================================
    # Child count
    # =================================================================

    def _determine_child_count(
        self, household: Household, adults: List[Person],
    ) -> int:
        """Determine number of children from distributions and pattern.

        Samples from ``children_by_parent_age`` using the youngest adult's
        age bracket, then clamps to the pattern's expected range.
        """
        pattern = household.pattern
        metadata = PATTERN_METADATA.get(pattern, PATTERN_METADATA['other'])
        expected_range = metadata.get('expected_children', (0, 0))

        # Use youngest adult as the reference parent
        parent = min(adults, key=lambda a: a.age)
        parent_bracket = self._get_parent_age_bracket(parent.age)

        children_dist = self.distributions.get('children_by_parent_age')
        if children_dist is not None and len(children_dist) > 0:
            filtered = children_dist[
                children_dist['parent_age_bracket'] == parent_bracket
            ]
            if len(filtered) > 0:
                row = weighted_sample(filtered, 'weight').iloc[0]
                num_children = int(row['num_children'])
            else:
                num_children = int(np.random.randint(
                    expected_range[0], expected_range[1] + 1,
                ))
        else:
            num_children = int(np.random.randint(
                expected_range[0], expected_range[1] + 1,
            ))

        # Clamp to pattern range
        min_c, max_c = expected_range

        if pattern in PATTERNS_REQUIRING_CHILDREN:
            min_c = max(1, min_c)

        return max(min_c, min(max_c, num_children))

    # =================================================================
    # Relationship assignment
    # =================================================================

    def _assign_child_relationships(
        self,
        pattern: str,
        num_children: int,
        household: Household,
    ) -> List[RelationshipType]:
        """Assign relationship types to children based on pattern."""
        if num_children == 0:
            return []

        if pattern == 'blended_family':
            return self._assign_blended_family_relationships(num_children)

        if pattern == 'multigenerational':
            return self._assign_multigenerational_child_relationships(
                num_children, household,
            )

        # Default: all biological children
        return [RelationshipType.BIOLOGICAL_CHILD] * num_children

    def _assign_blended_family_relationships(
        self, num_children: int,
    ) -> List[RelationshipType]:
        """Assign bio/step split for a blended family.

        Uses ``stepchild_patterns`` (which provides ``num_stepchildren``)
        to determine how many stepchildren, with the remainder as
        biological children.  At least one of each type is guaranteed.
        """
        step_df = self.distributions.get('stepchild_patterns')

        if step_df is not None and len(step_df) > 0:
            row = weighted_sample(step_df, 'weight').iloc[0]
            num_step = int(row['num_stepchildren'])
        else:
            # Fallback: half stepchildren
            num_step = max(1, num_children // 2)

        # Guarantee at least 1 bio and 1 step for a true blended family
        num_step = max(1, min(num_children - 1, num_step))
        num_bio = num_children - num_step

        rels: List[RelationshipType] = (
            [RelationshipType.BIOLOGICAL_CHILD] * num_bio
            + [RelationshipType.STEPCHILD] * num_step
        )
        np.random.shuffle(rels)
        return list(rels)

    def _assign_multigenerational_child_relationships(
        self,
        num_children: int,
        household: Household,
    ) -> List[RelationshipType]:
        """Determine child relationships for multigenerational households.

        Infers structure from adult relationships set by demographics.py:
        - If a PARENT exists among adults, the householder is middle
          generation → children are BIOLOGICAL_CHILD.
        - Otherwise the householder is the grandparent generation →
          children are GRANDCHILD.
        """
        has_parent = any(
            m.relationship == RelationshipType.PARENT
            for m in household.members
        )

        if has_parent:
            # Householder is middle gen; children are their biological kids
            return [RelationshipType.BIOLOGICAL_CHILD] * num_children
        else:
            # Householder is grandparent; children are grandchildren
            return [RelationshipType.GRANDCHILD] * num_children

    # =================================================================
    # Single child generation
    # =================================================================

    def _generate_single_child(
        self,
        household: Household,
        adults: List[Person],
        relationship: RelationshipType,
        existing_children: List[Person],
    ) -> Person:
        """Generate a single child with demographic attributes."""
        # Pick reference adult and minimum age gap
        if relationship == RelationshipType.GRANDCHILD:
            reference_adult = max(adults, key=lambda a: a.age)
            min_age_gap = 28
        else:
            reference_adult = min(adults, key=lambda a: a.age)
            min_age_gap = 14

        age = self._sample_child_age(
            reference_adult, min_age_gap, relationship,
        )
        sex = self._sample_sex()
        race = self._determine_child_race(adults)
        hispanic = self._determine_child_hispanic(adults)

        return Person(
            person_id=str(uuid.uuid4()),
            relationship=relationship,
            age=int(age),
            sex=str(sex),
            race=str(race),
            hispanic_origin=bool(hispanic),
            is_dependent=True,
            can_be_claimed=True,
            months_in_home=12,
        )

    # =================================================================
    # Age sampling
    # =================================================================

    def _sample_child_age(
        self,
        reference_adult: Person,
        min_age_gap: int,
        relationship: RelationshipType,
    ) -> int:
        """Sample a child age constrained by parent age and relationship.

        Uses ``child_age_distributions`` filtered by relationship type
        when available, otherwise falls back to uniform sampling.
        """
        max_child_age = min(17, reference_adult.age - min_age_gap)
        if max_child_age < 0:
            return 0

        # Map RelationshipType to the relationship string in the table
        rel_key = self._relationship_to_table_key(relationship)

        child_age_df = self.distributions.get('child_age_distributions')
        if child_age_df is not None and len(child_age_df) > 0 and rel_key:
            filtered = child_age_df[
                (child_age_df['relationship'] == rel_key)
                & (child_age_df['age'] <= max_child_age)
            ]
            if len(filtered) > 0:
                row = weighted_sample(filtered, 'weight').iloc[0]
                return int(row['age'])

        # Fallback: uniform 0..max_child_age
        return int(np.random.randint(0, max_child_age + 1))

    @staticmethod
    def _relationship_to_table_key(
        relationship: RelationshipType,
    ) -> Optional[str]:
        """Map a RelationshipType to the string used in child_age_distributions."""
        mapping = {
            RelationshipType.GRANDCHILD: 'grandchild',
            RelationshipType.STEPCHILD: 'stepchild',
            RelationshipType.BIOLOGICAL_CHILD: 'biological_child',
            RelationshipType.ADOPTED_CHILD: 'adopted_child',
        }
        return mapping.get(relationship)

    # =================================================================
    # Sex, race, ethnicity
    # =================================================================

    @staticmethod
    def _sample_sex() -> str:
        """Sample sex for a child (50/50)."""
        return str(np.random.choice(['M', 'F']))

    @staticmethod
    def _determine_child_race(adults: List[Person]) -> str:
        """Determine child race based on parent races.

        Same-race parents → child inherits that race.
        Mixed-race parents → 70 % two_or_more, 30 % one parent's race.
        """
        parent_races = [a.race for a in adults if a.race]
        if not parent_races:
            return 'two_or_more'

        unique = set(parent_races)
        if len(unique) == 1:
            return parent_races[0]

        if np.random.random() < 0.7:
            return 'two_or_more'
        return str(np.random.choice(parent_races))

    @staticmethod
    def _determine_child_hispanic(adults: List[Person]) -> bool:
        """Determine child Hispanic origin based on parents.

        If either parent is Hispanic, 90 % chance the child is too.
        """
        if any(a.hispanic_origin for a in adults):
            return bool(np.random.random() < 0.9)
        return False

    # =================================================================
    # Helpers
    # =================================================================

    def _get_parent_age_bracket(self, age: int) -> str:
        """Find the matching parent_age_bracket from the distribution table."""
        children_dist = self.distributions.get('children_by_parent_age')
        if children_dist is not None and len(children_dist) > 0:
            brackets = [
                str(b) for b in children_dist['parent_age_bracket'].unique()
            ]
            for bracket in brackets:
                if match_age_bracket(age, bracket):
                    return bracket

        # Fallback bracket lookup
        if age < 25:
            return '18-24'
        if age < 30:
            return '25-29'
        if age < 35:
            return '30-34'
        if age < 40:
            return '35-39'
        if age < 45:
            return '40-44'
        if age < 55:
            return '45-54'
        if age < 65:
            return '55-64'
        return '65+'
