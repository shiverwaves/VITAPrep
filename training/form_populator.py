"""
Form populator — fills the blank 13614-C Part I PDF with household data.

Takes a ``Household`` (with PII populated) and the blank template PDF,
clones it via pypdf, and writes the correct values into every AcroForm field.

Two uses:
1. **Answer key** — the ground-truth filled form used by the grader.
2. **Review mode handout** — given to the student (may later have errors
   injected by ``error_injector.py``).

The field name constants from ``training.form_fields`` are the shared
contract between this module, the template builder, and the grader.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from pypdf import PdfReader, PdfWriter

from generator.models import (
    FilingStatus,
    Household,
    Person,
    RelationshipType,
)
from training.form_fields import (
    ADDR_APT,
    ADDR_CITY,
    ADDR_STATE,
    ADDR_STREET,
    ADDR_ZIP,
    CLAIMED_AS_DEPENDENT,
    DEP_DOB,
    DEP_FIRST_NAME,
    DEP_LAST_NAME,
    DEP_MONTHS,
    DEP_RELATIONSHIP,
    DEP_SINGLE_OR_MARRIED,
    DEP_STUDENT,
    DEP_US_CITIZEN,
    DEP_DISABLED,
    FILING_STATUS,
    FS_HOH,
    FS_MFJ,
    FS_MFS,
    FS_QSS,
    FS_SINGLE,
    MAX_DEPENDENTS,
    NOT_CLAIMED_AS_DEPENDENT,
    NOT_PRIOR_YEAR_DEPENDENT,
    PRIOR_YEAR_DEPENDENT,
    SPOUSE_DOB,
    SPOUSE_FIRST_NAME,
    SPOUSE_JOB_TITLE,
    SPOUSE_LAST_NAME,
    SPOUSE_MIDDLE_INITIAL,
    SPOUSE_SSN,
    YOU_DOB,
    YOU_EMAIL,
    YOU_FIRST_NAME,
    YOU_JOB_TITLE,
    YOU_LAST_NAME,
    YOU_MIDDLE_INITIAL,
    YOU_NOT_US_CITIZEN,
    YOU_PHONE,
    YOU_SSN,
    YOU_US_CITIZEN,
    dep_field,
)

logger = logging.getLogger(__name__)

# Default template location (committed artifact from build_form_template.py)
_DEFAULT_TEMPLATE = (
    Path(__file__).resolve().parent / "templates" / "form_13614c_p1.pdf"
)

# Mapping from FilingStatus enum to PDF radio button export values
_FILING_STATUS_MAP: Dict[FilingStatus, str] = {
    FilingStatus.SINGLE: FS_SINGLE,
    FilingStatus.MARRIED_FILING_JOINTLY: FS_MFJ,
    FilingStatus.MARRIED_FILING_SEPARATELY: FS_MFS,
    FilingStatus.HEAD_OF_HOUSEHOLD: FS_HOH,
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: FS_QSS,
}

# Relationship types that qualify as VITA dependents
_DEPENDENT_RELATIONSHIPS: Dict[RelationshipType, str] = {
    RelationshipType.BIOLOGICAL_CHILD: "Son/Daughter",
    RelationshipType.ADOPTED_CHILD: "Son/Daughter",
    RelationshipType.STEPCHILD: "Stepchild",
    RelationshipType.GRANDCHILD: "Grandchild",
    RelationshipType.SIBLING: "Sibling",
    RelationshipType.PARENT: "Parent",
    RelationshipType.OTHER_RELATIVE: "Other",
}


def _format_date(d: Optional[date]) -> str:
    """Format a date as MM/DD/YYYY for the intake form, or empty string."""
    if d is None:
        return ""
    return d.strftime("%m/%d/%Y")


def _middle_initial(name: str) -> str:
    """Extract just the first letter of a middle name, or empty string."""
    if not name:
        return ""
    return name[0].upper()


def _relationship_label(person: Person) -> str:
    """Human-readable relationship label for the dependent section."""
    rel = person.relationship
    if isinstance(rel, str):
        try:
            rel = RelationshipType(rel)
        except ValueError:
            return rel
    return _DEPENDENT_RELATIONSHIPS.get(rel, "Other")


def _get_dependents(household: Household) -> List[Person]:
    """Return dependents sorted by age descending (oldest first), capped at 4."""
    deps = [
        p for p in household.members
        if p.is_dependent or p.can_be_claimed
    ]
    deps.sort(key=lambda p: p.age, reverse=True)
    return deps[:MAX_DEPENDENTS]


def build_field_values(household: Household) -> Dict[str, str]:
    """Build a dict mapping PDF field names to their string values.

    This is the core mapping logic, separated from the PDF writing so it
    can be tested independently and reused by the grader.

    Args:
        household: Household with PII fully populated.

    Returns:
        Dict of ``{field_name: value}`` for every field that should be
        filled. Empty/unused fields are omitted.
    """
    values: Dict[str, str] = {}
    householder = household.get_householder()
    spouse = household.get_spouse()

    # =================================================================
    # Section A: About You (the householder / primary filer)
    # =================================================================
    if householder:
        values[YOU_FIRST_NAME] = householder.legal_first_name
        values[YOU_MIDDLE_INITIAL] = _middle_initial(householder.legal_middle_name)
        values[YOU_LAST_NAME] = householder.legal_last_name
        values[YOU_DOB] = _format_date(householder.dob)
        values[YOU_SSN] = householder.ssn
        values[YOU_JOB_TITLE] = householder.occupation_title or ""
        values[YOU_PHONE] = householder.phone
        values[YOU_EMAIL] = householder.email

        # Citizenship — default to US citizen (true for most VITA scenarios)
        values[YOU_US_CITIZEN] = "Yes"

    # =================================================================
    # Section B: Mailing Address
    # =================================================================
    if household.address:
        addr = household.address
        values[ADDR_STREET] = addr.street
        values[ADDR_APT] = addr.apt or ""
        values[ADDR_CITY] = addr.city
        values[ADDR_STATE] = addr.state
        values[ADDR_ZIP] = addr.zip_code

    # =================================================================
    # Section C: About Your Spouse
    # =================================================================
    if spouse:
        values[SPOUSE_FIRST_NAME] = spouse.legal_first_name
        values[SPOUSE_MIDDLE_INITIAL] = _middle_initial(spouse.legal_middle_name)
        values[SPOUSE_LAST_NAME] = spouse.legal_last_name
        values[SPOUSE_DOB] = _format_date(spouse.dob)
        values[SPOUSE_SSN] = spouse.ssn
        values[SPOUSE_JOB_TITLE] = spouse.occupation_title or ""

    # =================================================================
    # Section D: Filing Status
    # =================================================================
    filing_status = household.derive_filing_status()
    pdf_val = _FILING_STATUS_MAP.get(filing_status)
    if pdf_val:
        values[FILING_STATUS] = pdf_val

    # =================================================================
    # Section E: Dependents
    # =================================================================
    dependents = _get_dependents(household)
    for i, dep in enumerate(dependents):
        values[dep_field(i, DEP_FIRST_NAME)] = dep.legal_first_name
        values[dep_field(i, DEP_LAST_NAME)] = dep.legal_last_name
        values[dep_field(i, DEP_DOB)] = _format_date(dep.dob)
        values[dep_field(i, DEP_RELATIONSHIP)] = _relationship_label(dep)
        values[dep_field(i, DEP_MONTHS)] = str(dep.months_in_home)
        # Children are single by default
        values[dep_field(i, DEP_SINGLE_OR_MARRIED)] = "Yes"
        # US citizen — default true for most VITA scenarios
        values[dep_field(i, DEP_US_CITIZEN)] = "Yes"
        values[dep_field(i, DEP_STUDENT)] = (
            "Yes" if dep.is_full_time_student else ""
        )
        values[dep_field(i, DEP_DISABLED)] = (
            "Yes" if dep.has_disability else ""
        )

    # =================================================================
    # Section F: Additional Questions
    # =================================================================
    if householder and householder.can_be_claimed:
        values[CLAIMED_AS_DEPENDENT] = "Yes"
    else:
        values[NOT_CLAIMED_AS_DEPENDENT] = "Yes"

    # Prior year dependent — default No (simplest case)
    values[NOT_PRIOR_YEAR_DEPENDENT] = "Yes"

    return values


def populate_form(
    household: Household,
    output_path: Path,
    template_path: Optional[Path] = None,
    field_overrides: Optional[Dict[str, str]] = None,
) -> Path:
    """Clone the blank template and fill it with household data.

    Args:
        household: Household with PII fully populated.
        output_path: Where to write the filled PDF.
        template_path: Path to the blank template. Defaults to the
            committed artifact at ``training/templates/form_13614c_p1.pdf``.
        field_overrides: Optional dict of ``{field_name: value}`` to
            override computed values. Used by the error injector to
            introduce deliberate mistakes.

    Returns:
        The output path.
    """
    template = template_path or _DEFAULT_TEMPLATE
    if not template.exists():
        raise FileNotFoundError(
            f"Template not found: {template}. "
            "Run 'python scripts/build_form_template.py' first."
        )

    reader = PdfReader(str(template))
    writer = PdfWriter()
    writer.append(reader)

    # Build field values from household data
    values = build_field_values(household)

    # Apply any overrides (e.g. injected errors)
    if field_overrides:
        values.update(field_overrides)

    # Write text fields
    writer.update_page_form_field_values(writer.pages[0], values)

    # Write to disk
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    logger.info("Populated form: %s (%d fields)", output_path, len(values))
    return output_path
