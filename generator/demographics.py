"""
Demographics generator — Part 1 of VITA intake.

Generates adult household members with demographic attributes:
age, sex, race, hispanic origin, and household relationships.

Does NOT handle employment, education, occupation, or disability.
Those move to employment.py for Part 2.

Reference: HouseholdRNG/generator/adult_generator.py
Port the demographic-related functions, leave employment-related ones for employment.py.
"""

import logging
import uuid
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .models import Household, Person, RelationshipType, PATTERN_METADATA
from .sampler import (
    weighted_sample, sample_age_from_bracket, get_age_bracket,
    match_age_bracket, set_random_seed,
)

logger = logging.getLogger(__name__)


class DemographicsGenerator:
    """Generates adult household members with demographics only.

    Required distribution tables:
        race_by_age, race_distribution, hispanic_origin_by_age,
        spousal_age_gaps, couple_sex_patterns

    Optional tables (used for multigenerational patterns):
        multigenerational_patterns
    """

    # Tables we must have for core sampling
    _REQUIRED_TABLES = [
        'race_by_age',
        'race_distribution',
        'hispanic_origin_by_age',
    ]

    # Tables used when available, with fallback behaviour
    _OPTIONAL_TABLES = [
        'spousal_age_gaps',
        'couple_sex_patterns',
        'multigenerational_patterns',
    ]

    def __init__(self, distributions: Dict[str, pd.DataFrame]) -> None:
        """Initialize with loaded distribution tables.

        Args:
            distributions: Dictionary of table name → DataFrame from
                DistributionLoader.
        """
        self.distributions = distributions
        self._validate_required_tables()
        # Cache the age bracket distribution derived from race_by_age
        self._age_bracket_weights: Optional[pd.Series] = None

    def _validate_required_tables(self) -> None:
        """Log warnings for missing distribution tables."""
        missing = [t for t in self._REQUIRED_TABLES
                   if t not in self.distributions]
        if missing:
            logger.warning("Missing required demographics tables: %s", missing)

        missing_opt = [t for t in self._OPTIONAL_TABLES
                       if t not in self.distributions]
        if missing_opt:
            logger.debug(
                "Missing optional demographics tables (will use defaults): %s",
                missing_opt,
            )

    # =================================================================
    # Public API
    # =================================================================

    def generate_adults(self, household: Household) -> List[Person]:
        """Generate adult members for a household based on its pattern.

        Args:
            household: Household with pattern set (from pipeline pattern
                selection).

        Returns:
            List of Person objects with demographics populated
            (age, sex, race, hispanic_origin, relationship).
        """
        pattern = household.pattern
        metadata = PATTERN_METADATA.get(pattern, PATTERN_METADATA['other'])

        num_adults = self._determine_adult_count(pattern, metadata)
        relationships = self._assign_relationships(
            pattern, num_adults, household,
        )

        adults: List[Person] = []
        for relationship in relationships:
            adult = self._generate_single_adult(
                relationship=relationship,
                pattern=pattern,
                existing_adults=adults,
                household=household,
            )
            adults.append(adult)

        logger.debug(
            "Generated %d adults for pattern '%s'", len(adults), pattern,
        )
        return adults

    # =================================================================
    # Adult count & relationships
    # =================================================================

    def _determine_adult_count(
        self, pattern: str, metadata: dict,
    ) -> int:
        """Determine number of adults based on pattern metadata."""
        expected = metadata.get('expected_adults', 1)
        if isinstance(expected, tuple):
            return int(np.random.randint(expected[0], expected[1] + 1))
        return int(expected)

    def _assign_relationships(
        self,
        pattern: str,
        num_adults: int,
        household: Household,
    ) -> List[RelationshipType]:
        """Assign relationship types to adults based on pattern."""
        if pattern in ('single_adult', 'single_parent'):
            return [RelationshipType.HOUSEHOLDER]

        if pattern in (
            'married_couple_no_children',
            'married_couple_with_children',
            'blended_family',
        ):
            return [RelationshipType.HOUSEHOLDER, RelationshipType.SPOUSE]

        if pattern == 'unmarried_partners':
            return [
                RelationshipType.HOUSEHOLDER,
                RelationshipType.UNMARRIED_PARTNER,
            ]

        if pattern == 'multigenerational':
            return self._assign_multigenerational_relationships(
                num_adults, household,
            )

        # 'other' and anything unrecognized
        rels: List[RelationshipType] = [RelationshipType.HOUSEHOLDER]
        for _ in range(num_adults - 1):
            rels.append(RelationshipType.OTHER_RELATIVE)
        return rels

    def _assign_multigenerational_relationships(
        self,
        num_adults: int,
        household: Household,
    ) -> List[RelationshipType]:
        """Determine relationships for a multigenerational household.

        Samples from the multigenerational_patterns table when available
        to choose between structures like 'children+grandchild' (grandparent
        households) vs multi-generation families with a PARENT relationship.
        """
        rels: List[RelationshipType] = [RelationshipType.HOUSEHOLDER]

        multi_df = self.distributions.get('multigenerational_patterns')
        has_parent = False

        if multi_df is not None and len(multi_df) > 0:
            row = weighted_sample(multi_df, 'weight').iloc[0]
            num_gen = int(row.get('num_generations', 2))

            # 3+ generations implies a PARENT living with the householder
            if num_gen >= 3:
                has_parent = True
        else:
            # Default: assume 3-generation household
            has_parent = True

        if has_parent and num_adults >= 2:
            rels.append(RelationshipType.PARENT)
            # Remaining adults are spouses of householder
            if num_adults >= 3:
                rels.append(RelationshipType.SPOUSE)
            for _ in range(num_adults - len(rels)):
                rels.append(RelationshipType.OTHER_RELATIVE)
        else:
            # 2-generation: householder + spouse (grandparent raising grandkids)
            if num_adults >= 2:
                rels.append(RelationshipType.SPOUSE)
            for _ in range(num_adults - len(rels)):
                rels.append(RelationshipType.OTHER_RELATIVE)

        return rels[:num_adults]

    # =================================================================
    # Single adult generation
    # =================================================================

    def _generate_single_adult(
        self,
        relationship: RelationshipType,
        pattern: str,
        existing_adults: List[Person],
        household: Household,
    ) -> Person:
        """Generate a single adult with demographic attributes only."""
        age = self._sample_age(relationship, pattern, existing_adults)
        sex = self._sample_sex(relationship, pattern, existing_adults)
        race = self._sample_race(age)
        hispanic = self._sample_hispanic_origin(age)

        return Person(
            person_id=str(uuid.uuid4()),
            relationship=relationship,
            age=int(age),
            sex=str(sex),
            race=str(race),
            hispanic_origin=bool(hispanic),
        )

    # =================================================================
    # Age sampling
    # =================================================================

    def _sample_age(
        self,
        relationship: RelationshipType,
        pattern: str,
        existing_adults: List[Person],
    ) -> int:
        """Dispatch age sampling to relationship-specific methods."""
        householder = next(
            (a for a in existing_adults
             if a.relationship == RelationshipType.HOUSEHOLDER),
            None,
        )

        if relationship == RelationshipType.HOUSEHOLDER:
            return self._sample_householder_age(pattern)
        if relationship == RelationshipType.SPOUSE:
            return self._sample_spouse_age(householder)
        if relationship == RelationshipType.UNMARRIED_PARTNER:
            return self._sample_partner_age(householder)
        if relationship == RelationshipType.PARENT:
            return self._sample_parent_age(householder)
        return self._sample_general_adult_age()

    def _get_age_bracket_weights(self) -> Optional[pd.Series]:
        """Derive an age-bracket weight distribution from race_by_age.

        Part 1 does not have an employment_by_age table, so we sum weights
        across all races within each age bracket to get a general adult age
        distribution.

        Returns:
            Series indexed by age bracket with summed weights, or None.
        """
        if self._age_bracket_weights is not None:
            return self._age_bracket_weights

        race_by_age = self.distributions.get('race_by_age')
        if race_by_age is None or len(race_by_age) == 0:
            return None

        self._age_bracket_weights = (
            race_by_age.groupby('age_bracket', observed=True)['weight'].sum()
        )
        return self._age_bracket_weights

    def _sample_householder_age(self, pattern: str) -> int:
        """Sample householder age with pattern-specific constraints."""
        # Age constraints by pattern
        constraints = {
            'single_parent': (20, 65),
            'married_couple_with_children': (22, 55),
            'blended_family': (22, 55),
            'multigenerational': (30, 75),
        }
        min_age, max_age = constraints.get(pattern, (18, 85))

        bracket_weights = self._get_age_bracket_weights()
        if bracket_weights is not None and len(bracket_weights) > 0:
            # Keep only brackets overlapping the valid range
            valid = [
                b for b in bracket_weights.index
                if self._bracket_overlaps_range(str(b), min_age, max_age)
            ]
            if valid:
                filtered = bracket_weights[valid]
                probs = filtered / filtered.sum()
                chosen = np.random.choice(filtered.index, p=probs.values)
                age = sample_age_from_bracket(str(chosen))
                return max(min_age, min(max_age, age))

        # Fallback: uniform within range
        return int(np.random.randint(min_age, max_age + 1))

    def _sample_spouse_age(self, householder: Optional[Person]) -> int:
        """Sample spouse age based on spousal age gap distribution."""
        if householder is None:
            return self._sample_general_adult_age()

        gaps_df = self.distributions.get('spousal_age_gaps')
        if gaps_df is not None and len(gaps_df) > 0:
            row = weighted_sample(gaps_df, 'weight').iloc[0]
            # age_gap = householder_age - spouse_age (positive = householder older)
            gap = int(row['age_gap'])
            spouse_age = householder.age - gap
        else:
            gap = int(np.random.randint(-5, 6))
            spouse_age = householder.age - gap

        return max(18, min(85, spouse_age))

    def _sample_partner_age(self, householder: Optional[Person]) -> int:
        """Sample unmarried partner age (wider variance than spouse)."""
        if householder is None:
            return self._sample_general_adult_age()

        gaps_df = self.distributions.get('spousal_age_gaps')
        if gaps_df is not None and len(gaps_df) > 0:
            row = weighted_sample(gaps_df, 'weight').iloc[0]
            # age_gap = householder_age - partner_age (positive = householder older)
            gap = int(row['age_gap'])
            partner_age = householder.age - gap
        else:
            gap = int(np.random.randint(-8, 9))
            partner_age = householder.age - gap

        return max(18, min(85, partner_age))

    def _sample_parent_age(self, householder: Optional[Person]) -> int:
        """Sample parent age (18–40 years older than householder)."""
        if householder is None:
            return int(np.random.randint(55, 86))

        age_diff = int(np.random.randint(18, 41))
        return min(95, householder.age + age_diff)

    def _sample_general_adult_age(self) -> int:
        """Sample from the general adult age distribution."""
        bracket_weights = self._get_age_bracket_weights()
        if bracket_weights is not None and len(bracket_weights) > 0:
            probs = bracket_weights / bracket_weights.sum()
            chosen = np.random.choice(bracket_weights.index, p=probs.values)
            return sample_age_from_bracket(str(chosen))

        return int(np.random.randint(18, 70))

    # =================================================================
    # Sex sampling
    # =================================================================

    def _sample_sex(
        self,
        relationship: RelationshipType,
        pattern: str,
        existing_adults: List[Person],
    ) -> str:
        """Sample sex based on relationship and couple patterns."""
        householder = next(
            (a for a in existing_adults
             if a.relationship == RelationshipType.HOUSEHOLDER),
            None,
        )

        couple_df = self.distributions.get('couple_sex_patterns')

        if relationship == RelationshipType.HOUSEHOLDER:
            return self._sample_householder_sex(pattern, couple_df)

        if relationship in (
            RelationshipType.SPOUSE, RelationshipType.UNMARRIED_PARTNER,
        ):
            return self._sample_partner_sex(
                relationship, householder, couple_df,
            )

        # Other relationships: 50/50
        return str(np.random.choice(['M', 'F']))

    def _sample_householder_sex(
        self,
        pattern: str,
        couple_df: Optional[pd.DataFrame],
    ) -> str:
        """Sample sex for the householder using couple_sex_patterns."""
        if couple_df is None or len(couple_df) == 0:
            return str(np.random.choice(['M', 'F']))

        # Only use couple patterns for couple-type households
        couple_patterns = (
            'married_couple_no_children',
            'married_couple_with_children',
            'blended_family',
            'unmarried_partners',
        )
        if pattern not in couple_patterns:
            return str(np.random.choice(['M', 'F']))

        # Filter by relationship type
        if pattern == 'unmarried_partners':
            filtered = couple_df[
                couple_df['relationship'] == 'unmarried_partner'
            ]
        else:
            filtered = couple_df[couple_df['relationship'] == 'spouse']

        if len(filtered) > 0:
            row = weighted_sample(filtered, 'weight').iloc[0]
            return str(row['householder_sex'])

        return str(np.random.choice(['M', 'F']))

    def _sample_partner_sex(
        self,
        relationship: RelationshipType,
        householder: Optional[Person],
        couple_df: Optional[pd.DataFrame],
    ) -> str:
        """Sample sex for a spouse or unmarried partner."""
        if couple_df is not None and householder is not None and len(couple_df) > 0:
            rel_value = (
                'spouse'
                if relationship == RelationshipType.SPOUSE
                else 'unmarried_partner'
            )
            filtered = couple_df[
                (couple_df['relationship'] == rel_value)
                & (couple_df['householder_sex'] == householder.sex)
            ]
            if len(filtered) > 0:
                row = weighted_sample(filtered, 'weight').iloc[0]
                return str(row['partner_sex'])

        # Fallback: opposite sex
        if householder is not None:
            return 'F' if householder.sex == 'M' else 'M'
        return str(np.random.choice(['M', 'F']))

    # =================================================================
    # Race & ethnicity
    # =================================================================

    def _sample_race(self, age: int) -> str:
        """Sample race from the age-stratified distribution."""
        race_by_age = self.distributions.get('race_by_age')
        if race_by_age is not None and len(race_by_age) > 0:
            brackets = [str(b) for b in race_by_age['age_bracket'].unique()]
            bracket = get_age_bracket(age, brackets)
            if bracket is not None:
                filtered = race_by_age[race_by_age['age_bracket'] == bracket]
                if len(filtered) > 0:
                    row = weighted_sample(filtered, 'weight').iloc[0]
                    return str(row['race'])

        # Fallback: overall race distribution
        race_dist = self.distributions.get('race_distribution')
        if race_dist is not None and len(race_dist) > 0:
            row = weighted_sample(race_dist, 'weight').iloc[0]
            return str(row['race'])

        return 'white'

    def _sample_hispanic_origin(self, age: int) -> bool:
        """Sample Hispanic origin from the age-stratified distribution."""
        hisp_df = self.distributions.get('hispanic_origin_by_age')
        if hisp_df is not None and len(hisp_df) > 0:
            brackets = [str(b) for b in hisp_df['age_bracket'].unique()]
            bracket = get_age_bracket(age, brackets)
            if bracket is not None:
                filtered = hisp_df[hisp_df['age_bracket'] == bracket]
                if len(filtered) > 0:
                    row = weighted_sample(filtered, 'weight').iloc[0]
                    return bool(row['is_hispanic'])

        # Fallback: ~18% Hispanic (US average)
        return bool(np.random.random() < 0.18)

    # =================================================================
    # Helpers
    # =================================================================

    @staticmethod
    def _bracket_overlaps_range(
        bracket: str, min_val: int, max_val: int,
    ) -> bool:
        """Check if an age bracket overlaps with [min_val, max_val]."""
        b = bracket.strip()
        try:
            if '+' in b:
                b_min = int(b.replace('+', '').strip())
                return b_min <= max_val
            if '-' in b:
                parts = b.split('-')
                b_min = int(parts[0])
                b_max = int(parts[1])
                return b_min <= max_val and b_max >= min_val
            val = int(b)
            return min_val <= val <= max_val
        except (ValueError, IndexError):
            return True  # Include if unparseable
