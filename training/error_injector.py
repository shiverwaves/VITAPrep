"""
Error injector — seeds deliberate discrepancies for verification exercises.

Takes a Household with PII and introduces errors between documents and/or
the intake form. Returns the modified data plus a manifest of injected errors
(used as the answer key).

Error categories: name, ssn, address, dob, filing_status, dependent, expiration, income
~15% of scenarios should be error-free to test student confidence.

See docs/VITA_FORM_FIELDS.md for field-level error examples.
"""

import copy
import logging
import random
import string
import uuid
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from generator.models import Household, InjectedError, Person, RelationshipType

logger = logging.getLogger(__name__)

# Type alias for an error-producing function
_ErrorFn = Callable[
    [Household, str],  # (household, difficulty)
    Optional[InjectedError],
]


# =========================================================================
# Individual error generators
# =========================================================================

def _name_misspelling(person: Person, difficulty: str) -> InjectedError:
    """Misspell a person's first name on the intake form."""
    original = person.legal_first_name
    if len(original) <= 1:
        # Fallback: swap last name
        original = person.legal_last_name
        field = "last_name"
    else:
        field = "first_name"

    if difficulty == "easy":
        # Obvious: swap two adjacent chars
        i = random.randint(0, len(original) - 2)
        chars = list(original)
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
        mutated = "".join(chars)
    elif difficulty == "medium":
        # Add a letter
        i = random.randint(1, len(original) - 1)
        mutated = original[:i] + random.choice("aeiouy") + original[i:]
    else:
        # Hard: change one letter to a similar-sounding one
        subs = {"a": "e", "e": "a", "i": "y", "y": "i", "o": "u",
                "u": "o", "c": "k", "k": "c", "s": "z", "z": "s"}
        chars = list(original.lower())
        changed = False
        for i, ch in enumerate(chars):
            if ch in subs:
                chars[i] = subs[ch]
                changed = True
                break
        if not changed and len(chars) > 2:
            chars[-1] = random.choice(string.ascii_lowercase)
        mutated = "".join(chars).capitalize()

    if mutated == original:
        mutated = original + "e"

    return InjectedError(
        error_id=_gen_id(),
        category="name",
        field=field,
        person_id=person.person_id,
        document="intake_form",
        correct_value=original,
        erroneous_value=mutated,
        explanation=f"Name misspelled on intake form: '{original}' → '{mutated}'",
        difficulty=difficulty,
    )


def _ssn_transposition(person: Person, difficulty: str) -> InjectedError:
    """Transpose or alter digits in a person's SSN."""
    original = person.ssn
    digits = list(original.replace("-", ""))

    if difficulty == "easy":
        # Swap two adjacent digits
        i = random.randint(0, len(digits) - 2)
        digits[i], digits[i + 1] = digits[i + 1], digits[i]
        # Make sure it's actually different
        if digits == list(original.replace("-", "")):
            digits[-1] = str((int(digits[-1]) + 1) % 10)
    elif difficulty == "medium":
        # Change one digit
        i = random.randint(3, 8)  # Avoid 9XX prefix
        digits[i] = str((int(digits[i]) + random.randint(1, 9)) % 10)
    else:
        # Hard: swap digits that are far apart
        i, j = 3, 7
        digits[i], digits[j] = digits[j], digits[i]
        if digits == list(original.replace("-", "")):
            digits[-1] = str((int(digits[-1]) + 1) % 10)

    mutated = f"{digits[0]}{digits[1]}{digits[2]}-{digits[3]}{digits[4]}-{digits[5]}{digits[6]}{digits[7]}{digits[8]}"
    if mutated == original:
        digits[-1] = str((int(digits[-1]) + 1) % 10)
        mutated = f"{digits[0]}{digits[1]}{digits[2]}-{digits[3]}{digits[4]}-{digits[5]}{digits[6]}{digits[7]}{digits[8]}"

    return InjectedError(
        error_id=_gen_id(),
        category="ssn",
        field="ssn",
        person_id=person.person_id,
        document="intake_form",
        correct_value=original,
        erroneous_value=mutated,
        explanation=f"SSN digits altered: '{original}' → '{mutated}'",
        difficulty=difficulty,
    )


def _address_mismatch(
    household: Household, person: Person, difficulty: str,
) -> InjectedError:
    """Create a mismatch between household address and a document."""
    addr = household.address
    if not addr:
        # Fallback: use generic address error
        return InjectedError(
            error_id=_gen_id(),
            category="address",
            field="street_address",
            person_id=person.person_id,
            document="drivers_license",
            correct_value="(no address)",
            erroneous_value="123 Unknown St",
            explanation="Address mismatch — DL shows old address",
            difficulty=difficulty,
        )

    if difficulty == "easy":
        # Missing apartment number or different street number
        original = addr.street
        parts = original.split(" ", 1)
        if parts[0].isdigit():
            new_num = str(int(parts[0]) + random.randint(1, 20))
            mutated = f"{new_num} {parts[1]}" if len(parts) > 1 else new_num
        else:
            mutated = original + " Apt B"
        field = "street_address"
    elif difficulty == "medium":
        # Abbreviation mismatch: "Street" vs "St"
        original = addr.street
        if " St" in original and "Street" not in original:
            mutated = original.replace(" St", " Street")
        elif "Street" in original:
            mutated = original.replace("Street", "St")
        elif " Dr" in original:
            mutated = original.replace(" Dr", " Drive")
        else:
            mutated = original.replace(original.split()[-1], "Ave")
        field = "street_address"
    else:
        # Hard: different zip code
        original = addr.zip_code
        new_last = str((int(original[-1]) + random.randint(1, 9)) % 10)
        mutated = original[:-1] + new_last
        field = "zip_code"

    if mutated == original:
        mutated = original + " (old)"

    return InjectedError(
        error_id=_gen_id(),
        category="address",
        field=field,
        person_id=person.person_id,
        document="drivers_license",
        correct_value=original,
        erroneous_value=mutated,
        explanation=f"Address mismatch — DL shows '{mutated}' instead of '{original}'",
        difficulty=difficulty,
    )


def _dob_error(person: Person, difficulty: str) -> InjectedError:
    """Alter the DOB on the intake form."""
    if person.dob is None:
        person_dob = date(1990, 1, 1)
    else:
        person_dob = person.dob

    original = person_dob.strftime("%m/%d/%Y")

    if difficulty == "easy":
        # Swap month and day
        mutated = person_dob.strftime("%d/%m/%Y")
        if mutated == original:
            mutated = (person_dob + timedelta(days=30)).strftime("%m/%d/%Y")
    elif difficulty == "medium":
        # Year off by 1
        new_year = person_dob.year + random.choice([-1, 1])
        try:
            mutated_date = person_dob.replace(year=new_year)
        except ValueError:
            mutated_date = person_dob.replace(year=new_year, day=28)
        mutated = mutated_date.strftime("%m/%d/%Y")
    else:
        # Hard: day off by 1
        mutated_date = person_dob + timedelta(days=random.choice([-1, 1]))
        mutated = mutated_date.strftime("%m/%d/%Y")

    if mutated == original:
        mutated = (person_dob + timedelta(days=10)).strftime("%m/%d/%Y")

    return InjectedError(
        error_id=_gen_id(),
        category="dob",
        field="dob",
        person_id=person.person_id,
        document="intake_form",
        correct_value=original,
        erroneous_value=mutated,
        explanation=f"DOB incorrect on intake form: '{original}' → '{mutated}'",
        difficulty=difficulty,
    )


def _filing_status_error(
    household: Household, difficulty: str,
) -> Optional[InjectedError]:
    """Select the wrong filing status on the intake form."""
    from generator.models import FilingStatus

    correct = household.derive_filing_status()
    correct_val = correct.value

    # Choose a plausible wrong status
    all_statuses = [s.value for s in FilingStatus]
    wrong_choices = [s for s in all_statuses if s != correct_val]
    if not wrong_choices:
        return None

    if difficulty == "easy":
        # Obvious: single ↔ married
        if correct == FilingStatus.SINGLE:
            mutated = FilingStatus.MARRIED_FILING_JOINTLY.value
        elif correct == FilingStatus.MARRIED_FILING_JOINTLY:
            mutated = FilingStatus.SINGLE.value
        else:
            mutated = random.choice(wrong_choices)
    elif difficulty == "medium":
        # MFJ vs MFS confusion, or HOH when single
        if correct == FilingStatus.MARRIED_FILING_JOINTLY:
            mutated = FilingStatus.MARRIED_FILING_SEPARATELY.value
        elif correct == FilingStatus.HEAD_OF_HOUSEHOLD:
            mutated = FilingStatus.SINGLE.value
        else:
            mutated = random.choice(wrong_choices)
    else:
        # Hard: subtler — HOH vs QSS, or MFS vs single
        if correct == FilingStatus.HEAD_OF_HOUSEHOLD:
            mutated = FilingStatus.QUALIFYING_SURVIVING_SPOUSE.value
        else:
            mutated = random.choice(wrong_choices)

    householder = household.get_householder()
    person_id = householder.person_id if householder else ""

    return InjectedError(
        error_id=_gen_id(),
        category="filing_status",
        field="filing_status",
        person_id=person_id,
        document="intake_form",
        correct_value=correct_val,
        erroneous_value=mutated,
        explanation=f"Wrong filing status: '{correct_val}' → '{mutated}'",
        difficulty=difficulty,
    )


def _dependent_error(
    dependent: Person, difficulty: str,
) -> InjectedError:
    """Alter a dependent's info (months, relationship, or name)."""
    if difficulty == "easy":
        # Wrong name
        original = dependent.legal_first_name
        mutated = original[0] + "." if len(original) > 1 else "X."
        if mutated == original:
            mutated = original + "a"
        return InjectedError(
            error_id=_gen_id(),
            category="dependent",
            field="dependent_name",
            person_id=dependent.person_id,
            document="intake_form",
            correct_value=original,
            erroneous_value=mutated,
            explanation=f"Dependent name abbreviated: '{original}' → '{mutated}'",
            difficulty=difficulty,
        )

    if difficulty == "medium":
        # Months too low (fails residency test)
        original = str(dependent.months_in_home)
        mutated = str(max(0, dependent.months_in_home - 7))
        if mutated == original:
            mutated = "3"
        return InjectedError(
            error_id=_gen_id(),
            category="dependent",
            field="dependent_months",
            person_id=dependent.person_id,
            document="intake_form",
            correct_value=original,
            erroneous_value=mutated,
            explanation=f"Dependent months wrong: {original} → {mutated}",
            difficulty=difficulty,
        )

    # Hard: wrong relationship
    original = (
        dependent.relationship.value
        if isinstance(dependent.relationship, RelationshipType)
        else str(dependent.relationship)
    )
    wrong_rels = ["stepchild", "grandchild", "other_relative", "roommate"]
    mutated = random.choice([r for r in wrong_rels if r != original] or ["other_relative"])
    return InjectedError(
        error_id=_gen_id(),
        category="dependent",
        field="dependent_relationship",
        person_id=dependent.person_id,
        document="intake_form",
        correct_value=original,
        erroneous_value=mutated,
        explanation=f"Dependent relationship wrong: '{original}' → '{mutated}'",
        difficulty=difficulty,
    )


def _expiration_error(person: Person, difficulty: str) -> Optional[InjectedError]:
    """Make the driver's license expired."""
    if not person.id_expiry:
        return None

    original = person.id_expiry.isoformat()
    # Set expiry to a past date
    if difficulty == "easy":
        expired = date(2020, 1, 1)
    elif difficulty == "medium":
        expired = date(2023, 6, 15)
    else:
        # Hard: just barely expired (last month)
        expired = date(2024, 11, 30)

    return InjectedError(
        error_id=_gen_id(),
        category="expiration",
        field="id_expiry",
        person_id=person.person_id,
        document="drivers_license",
        correct_value=original,
        erroneous_value=expired.isoformat(),
        explanation=f"Driver's license expired: {expired.isoformat()}",
        difficulty=difficulty,
    )


def _wage_amount_mismatch(
    person: Person, difficulty: str,
) -> Optional[InjectedError]:
    """Make the intake form's wage total not match the W-2(s)."""
    if person.wage_income <= 0:
        return None

    original = str(person.wage_income)

    if difficulty == "easy":
        mutated = str(person.wage_income + random.choice([1000, 2000, 5000]))
    elif difficulty == "medium":
        digits = list(original)
        if len(digits) >= 4:
            i = random.randint(1, len(digits) - 2)
            digits[i], digits[i + 1] = digits[i + 1], digits[i]
            mutated = "".join(digits)
        else:
            mutated = str(person.wage_income + 500)
    else:
        mutated = str(person.wage_income + random.choice([-100, 100]))

    if mutated == original:
        mutated = str(person.wage_income + 1)

    return InjectedError(
        error_id=_gen_id(),
        category="income",
        field="income.wages.amount",
        person_id=person.person_id,
        document="intake_form",
        correct_value=original,
        erroneous_value=mutated,
        explanation=f"Wage amount on intake doesn't match W-2: ${original} → ${mutated}",
        difficulty=difficulty,
    )


def _missing_income_source(
    person: Person, difficulty: str,
) -> Optional[InjectedError]:
    """Omit an income source from the intake form (student forgets a 1099)."""
    sources = []
    if person.interest_income > 0:
        sources.append(("income.interest", "1099-INT", str(person.interest_income)))
    if person.dividend_income > 0:
        sources.append(("income.dividends", "1099-DIV", str(person.dividend_income)))
    if person.retirement_income > 0:
        sources.append(("income.retirement", "1099-R", str(person.retirement_income)))
    if person.self_employment_income > 0:
        sources.append(("income.self_employment", "1099-NEC", str(person.self_employment_income)))

    if not sources:
        return None

    field, doc, amount = random.choice(sources)

    return InjectedError(
        error_id=_gen_id(),
        category="income",
        field=field,
        person_id=person.person_id,
        document="intake_form",
        correct_value=f"Yes (${amount})",
        erroneous_value="(omitted)",
        explanation=f"Income from {doc} not reported on intake form",
        difficulty=difficulty,
    )


def _income_amount_transposition(
    person: Person, difficulty: str,
) -> Optional[InjectedError]:
    """Transpose digits in an income amount on the intake form."""
    candidates = []
    if person.social_security_income > 0:
        candidates.append(("income.social_security.amount", person.social_security_income))
    if person.retirement_income > 0:
        candidates.append(("income.retirement.amount", person.retirement_income))
    if person.interest_income > 0:
        candidates.append(("income.interest.amount", person.interest_income))

    if not candidates:
        return None

    field, amount = random.choice(candidates)
    original = str(amount)
    digits = list(original)

    if len(digits) >= 2:
        i = random.randint(0, len(digits) - 2)
        digits[i], digits[i + 1] = digits[i + 1], digits[i]
        mutated = "".join(digits)
    else:
        mutated = str(amount + 1)

    if mutated == original:
        mutated = str(amount + 1)

    return InjectedError(
        error_id=_gen_id(),
        category="income",
        field=field,
        person_id=person.person_id,
        document="intake_form",
        correct_value=original,
        erroneous_value=mutated,
        explanation=f"Income amount digits transposed: ${original} → ${mutated}",
        difficulty=difficulty,
    )


def _w2_ssn_mismatch(
    person: Person, difficulty: str,
) -> Optional[InjectedError]:
    """SSN on W-2 doesn't match the SSN card."""
    if not person.ssn or not person.w2s:
        return None

    original = person.ssn
    digits = list(original.replace("-", ""))

    if difficulty == "easy":
        i = random.randint(3, 7)
        digits[i], digits[i + 1] = digits[i + 1], digits[i]
    elif difficulty == "medium":
        i = random.randint(3, 8)
        digits[i] = str((int(digits[i]) + random.randint(1, 9)) % 10)
    else:
        i, j = 4, 7
        digits[i], digits[j] = digits[j], digits[i]

    mutated = f"{digits[0]}{digits[1]}{digits[2]}-{digits[3]}{digits[4]}-{digits[5]}{digits[6]}{digits[7]}{digits[8]}"
    if mutated == original:
        digits[-1] = str((int(digits[-1]) + 1) % 10)
        mutated = f"{digits[0]}{digits[1]}{digits[2]}-{digits[3]}{digits[4]}-{digits[5]}{digits[6]}{digits[7]}{digits[8]}"

    return InjectedError(
        error_id=_gen_id(),
        category="income",
        field="w2_ssn",
        person_id=person.person_id,
        document="w2",
        correct_value=original,
        erroneous_value=mutated,
        explanation=f"SSN on W-2 doesn't match SSN card: '{original}' → '{mutated}'",
        difficulty=difficulty,
    )


# =========================================================================
# Error target collection
# =========================================================================

def _collect_targets(
    household: Household, difficulty: str,
) -> List[Tuple[str, _ErrorFn]]:
    """Collect all possible error targets for a household.

    Returns a list of (unique_key, generator_function) pairs.
    The unique_key prevents duplicate (person_id, field) mutations.
    """
    targets: List[Tuple[str, Callable]] = []
    adults = household.get_adults()
    dependents = household.get_dependents()
    householder = household.get_householder()

    for person in adults:
        pid = person.person_id
        # Name errors
        if person.legal_first_name:
            targets.append(
                (f"{pid}:first_name",
                 lambda hh, d, p=person: _name_misspelling(p, d)),
            )
        # SSN errors
        if person.ssn:
            targets.append(
                (f"{pid}:ssn",
                 lambda hh, d, p=person: _ssn_transposition(p, d)),
            )
        # DOB errors
        if person.dob:
            targets.append(
                (f"{pid}:dob",
                 lambda hh, d, p=person: _dob_error(p, d)),
            )
        # Address errors
        if household.address:
            targets.append(
                (f"{pid}:address",
                 lambda hh, d, p=person: _address_mismatch(hh, p, d)),
            )
        # Expiration errors
        if person.id_expiry:
            targets.append(
                (f"{pid}:id_expiry",
                 lambda hh, d, p=person: _expiration_error(p, d)),
            )

    # Filing status (household-level, keyed to householder)
    if householder:
        targets.append(
            (f"{householder.person_id}:filing_status",
             lambda hh, d: _filing_status_error(hh, d)),
        )

    # Dependent errors
    for dep in dependents:
        dpid = dep.person_id
        if dep.legal_first_name:
            targets.append(
                (f"{dpid}:dependent_name",
                 lambda hh, d, p=dep: _dependent_error(p, d)),
            )

    # Income errors (filers only)
    for person in adults:
        pid = person.person_id
        if person.wage_income > 0:
            targets.append(
                (f"{pid}:wage_amount",
                 lambda hh, d, p=person: _wage_amount_mismatch(p, d)),
            )
        if person.w2s and person.ssn:
            targets.append(
                (f"{pid}:w2_ssn",
                 lambda hh, d, p=person: _w2_ssn_mismatch(p, d)),
            )
        non_wage_income = (
            person.interest_income + person.dividend_income
            + person.retirement_income + person.self_employment_income
        )
        if non_wage_income > 0:
            targets.append(
                (f"{pid}:missing_income",
                 lambda hh, d, p=person: _missing_income_source(p, d)),
            )
        benefit_income = (
            person.social_security_income + person.retirement_income
            + person.interest_income
        )
        if benefit_income > 0:
            targets.append(
                (f"{pid}:income_transposition",
                 lambda hh, d, p=person: _income_amount_transposition(p, d)),
            )

    return targets


# =========================================================================
# Helper
# =========================================================================

def _gen_id() -> str:
    """Generate a short unique error ID."""
    return f"err-{uuid.uuid4().hex[:8]}"


# =========================================================================
# ErrorInjector
# =========================================================================

class ErrorInjector:
    """Seeds discrepancies between documents for verification exercises."""

    def inject(
        self,
        household: Household,
        difficulty: str = "medium",
        error_count: int = 3,
    ) -> Tuple[Household, List[InjectedError]]:
        """Inject errors into a household's PII/documents.

        Creates a deep copy of the household before mutating so the
        original is preserved.

        Args:
            household: Household with PII populated.
            difficulty: "easy", "medium", or "hard".
            error_count: Target number of errors to inject.
                Pass 0 for an explicitly error-free scenario.

        Returns:
            Tuple of (modified household copy, list of injected errors).
        """
        modified = copy.deepcopy(household)

        if error_count == 0:
            logger.info(
                "Error-free scenario for household %s",
                household.household_id,
            )
            return modified, []

        targets = _collect_targets(modified, difficulty)
        random.shuffle(targets)

        # Pick up to error_count unique targets
        selected = targets[:error_count]
        errors: List[InjectedError] = []

        for _key, gen_fn in selected:
            err = gen_fn(modified, difficulty)
            if err is not None:
                errors.append(err)

        logger.info(
            "Injected %d error(s) into household %s (requested %d, difficulty=%s)",
            len(errors), household.household_id, error_count, difficulty,
        )
        return modified, errors
