"""
Core data models for household generation and VITA training.

These are the foundation of the entire app. Every other module imports from here.
All fields have defaults so models can be built incrementally across pipeline stages.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class FilingStatus(Enum):
    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_SURVIVING_SPOUSE = "qualifying_surviving_spouse"


class EmploymentStatus(Enum):
    EMPLOYED = "employed"
    UNEMPLOYED = "unemployed"
    NOT_IN_LABOR_FORCE = "not_in_labor_force"


class RelationshipType(Enum):
    HOUSEHOLDER = "householder"
    SPOUSE = "spouse"
    UNMARRIED_PARTNER = "unmarried_partner"
    BIOLOGICAL_CHILD = "biological_child"
    ADOPTED_CHILD = "adopted_child"
    STEPCHILD = "stepchild"
    GRANDCHILD = "grandchild"
    PARENT = "parent"
    SIBLING = "sibling"
    OTHER_RELATIVE = "other_relative"
    ROOMMATE = "roommate"
    OTHER_NONRELATIVE = "other_nonrelative"


class Race(Enum):
    WHITE = "white"
    BLACK = "black"
    AMERICAN_INDIAN = "american_indian"
    ALASKA_NATIVE = "alaska_native"
    AMERICAN_INDIAN_ALASKA_NATIVE = "american_indian_alaska_native"
    ASIAN = "asian"
    NATIVE_HAWAIIAN_PACIFIC_ISLANDER = "native_hawaiian_pacific_islander"
    OTHER = "other"
    TWO_OR_MORE = "two_or_more"


class EducationLevel(Enum):
    LESS_THAN_HS = "less_than_hs"
    HIGH_SCHOOL = "high_school"
    SOME_COLLEGE = "some_college"
    ASSOCIATES = "associates"
    BACHELORS = "bachelors"
    MASTERS = "masters"
    PROFESSIONAL = "professional"
    DOCTORATE = "doctorate"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Address:
    """Physical mailing address."""
    street: str = ""
    apt: Optional[str] = None
    city: str = ""
    state: str = ""
    zip_code: str = ""

    def to_dict(self) -> dict:
        return {
            "street": self.street,
            "apt": self.apt,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
        }

    def one_line(self) -> str:
        """Format as single line: '123 Main St, Apt 4, Honolulu, HI 96816'"""
        parts = [self.street]
        if self.apt:
            parts[0] += f", {self.apt}"
        parts.append(f"{self.city}, {self.state} {self.zip_code}")
        return ", ".join(parts)


@dataclass
class Employer:
    """An employer or payer that issues tax documents (W-2, 1099)."""
    name: str = ""
    ein: str = ""  # Format: XX-XXXXXXX
    address: Optional[Address] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ein": self.ein,
            "address": self.address.to_dict() if self.address else None,
        }


@dataclass
class W2:
    """IRS Form W-2: Wage and Tax Statement."""
    employer: Optional[Employer] = None
    wages: int = 0  # Box 1
    federal_tax_withheld: int = 0  # Box 2
    social_security_wages: int = 0  # Box 3
    social_security_tax: int = 0  # Box 4
    medicare_wages: int = 0  # Box 5
    medicare_tax: int = 0  # Box 6
    box_12: List[Tuple[str, int]] = field(default_factory=list)  # e.g. [("D", 5000)]
    state: str = ""  # Box 15
    state_wages: int = 0  # Box 16
    state_tax: int = 0  # Box 17
    control_number: str = ""

    def to_dict(self) -> dict:
        return {
            "employer": self.employer.to_dict() if self.employer else None,
            "wages": self.wages,
            "federal_tax_withheld": self.federal_tax_withheld,
            "social_security_wages": self.social_security_wages,
            "social_security_tax": self.social_security_tax,
            "medicare_wages": self.medicare_wages,
            "medicare_tax": self.medicare_tax,
            "box_12": [{"code": c, "amount": a} for c, a in self.box_12],
            "state": self.state,
            "state_wages": self.state_wages,
            "state_tax": self.state_tax,
            "control_number": self.control_number,
        }


@dataclass
class Form1099INT:
    """IRS Form 1099-INT: Interest Income."""
    payer_name: str = ""
    payer_tin: str = ""
    interest_income: int = 0  # Box 1
    us_savings_bond_interest: int = 0  # Box 3
    federal_tax_withheld: int = 0  # Box 4

    def to_dict(self) -> dict:
        return {
            "payer_name": self.payer_name,
            "payer_tin": self.payer_tin,
            "interest_income": self.interest_income,
            "us_savings_bond_interest": self.us_savings_bond_interest,
            "federal_tax_withheld": self.federal_tax_withheld,
        }


@dataclass
class Form1099DIV:
    """IRS Form 1099-DIV: Dividends and Distributions."""
    payer_name: str = ""
    payer_tin: str = ""
    ordinary_dividends: int = 0  # Box 1a
    qualified_dividends: int = 0  # Box 1b
    capital_gain_distributions: int = 0  # Box 2a
    federal_tax_withheld: int = 0  # Box 4

    def to_dict(self) -> dict:
        return {
            "payer_name": self.payer_name,
            "payer_tin": self.payer_tin,
            "ordinary_dividends": self.ordinary_dividends,
            "qualified_dividends": self.qualified_dividends,
            "capital_gain_distributions": self.capital_gain_distributions,
            "federal_tax_withheld": self.federal_tax_withheld,
        }


@dataclass
class Form1099R:
    """IRS Form 1099-R: Distributions From Pensions, Annuities, etc."""
    payer_name: str = ""
    payer_tin: str = ""
    gross_distribution: int = 0  # Box 1
    taxable_amount: int = 0  # Box 2a
    federal_tax_withheld: int = 0  # Box 4
    distribution_code: str = ""  # Box 7: "7" normal, "1" early, "3" disability, "4" death

    def to_dict(self) -> dict:
        return {
            "payer_name": self.payer_name,
            "payer_tin": self.payer_tin,
            "gross_distribution": self.gross_distribution,
            "taxable_amount": self.taxable_amount,
            "federal_tax_withheld": self.federal_tax_withheld,
            "distribution_code": self.distribution_code,
        }


@dataclass
class SSA1099:
    """SSA-1099: Social Security Benefit Statement."""
    total_benefits: int = 0  # Box 3
    benefits_repaid: int = 0  # Box 4
    net_benefits: int = 0  # Box 5

    def to_dict(self) -> dict:
        return {
            "total_benefits": self.total_benefits,
            "benefits_repaid": self.benefits_repaid,
            "net_benefits": self.net_benefits,
        }


@dataclass
class Form1099NEC:
    """IRS Form 1099-NEC: Nonemployee Compensation."""
    payer_name: str = ""
    payer_tin: str = ""
    nonemployee_compensation: int = 0  # Box 1
    federal_tax_withheld: int = 0  # Box 4

    def to_dict(self) -> dict:
        return {
            "payer_name": self.payer_name,
            "payer_tin": self.payer_tin,
            "nonemployee_compensation": self.nonemployee_compensation,
            "federal_tax_withheld": self.federal_tax_withheld,
        }


@dataclass
class Person:
    """
    Represents one individual in a household.

    Fields are populated incrementally across pipeline stages:
    - Demographics (Sprint 3): age, sex, race, relationship
    - PII (Sprint 4): names, SSN, DOB, address, ID details
    - Employment (Sprint 9): employment_status, education, occupation
    - Income (Sprint 9): wage_income, ss_income, etc.
    """
    person_id: str = ""
    relationship: RelationshipType = RelationshipType.HOUSEHOLDER

    # === Demographics (populated by demographics.py / children.py) ===
    age: int = 0
    sex: str = ""  # "M" or "F"
    race: str = ""  # Race enum value
    hispanic_origin: bool = False

    # === PII (populated by pii.py) ===
    legal_first_name: str = ""
    legal_middle_name: str = ""
    legal_last_name: str = ""
    suffix: str = ""  # Jr., Sr., III
    ssn: str = ""  # Format: 9XX-XX-XXXX
    dob: Optional[date] = None
    phone: str = ""
    email: str = ""

    # === ID Document Details (populated by pii.py) ===
    id_type: str = ""  # "drivers_license", "state_id", ""
    id_state: str = ""
    id_number: str = ""
    id_expiry: Optional[date] = None
    id_address: Optional[Address] = None  # Address on ID (may differ from household)

    # === Dependent Info (populated by demographics.py / children.py) ===
    is_dependent: bool = False
    can_be_claimed: bool = False
    months_in_home: int = 12
    is_full_time_student: bool = False

    # === Employment (populated by employment.py — Sprint 9) ===
    employment_status: str = ""
    education: str = ""
    occupation_code: Optional[str] = None
    occupation_title: Optional[str] = None
    has_disability: bool = False

    # === Income (populated by income.py — Sprint 9) ===
    wage_income: int = 0
    self_employment_income: int = 0
    social_security_income: int = 0
    retirement_income: int = 0
    interest_income: int = 0
    dividend_income: int = 0
    other_income: int = 0
    public_assistance_income: int = 0

    # === Income Documents (populated by income.py — Sprint 9) ===
    w2s: List[W2] = field(default_factory=list)
    form_1099_ints: List[Form1099INT] = field(default_factory=list)
    form_1099_divs: List[Form1099DIV] = field(default_factory=list)
    form_1099_rs: List[Form1099R] = field(default_factory=list)
    ssa_1099: Optional[SSA1099] = None
    form_1099_necs: List[Form1099NEC] = field(default_factory=list)

    # === Expenses (populated by expenses.py — future) ===
    student_loan_interest: int = 0
    educator_expenses: int = 0
    ira_contributions: int = 0

    # --- Helper Methods ---

    def total_income(self) -> int:
        return (
            self.wage_income
            + self.self_employment_income
            + self.social_security_income
            + self.retirement_income
            + self.interest_income
            + self.dividend_income
            + self.other_income
            + self.public_assistance_income
        )

    def is_adult(self) -> bool:
        return self.age >= 18

    def is_child(self) -> bool:
        return self.age < 18

    def is_senior(self) -> bool:
        return self.age >= 65

    def is_employed(self) -> bool:
        return self.employment_status == EmploymentStatus.EMPLOYED.value

    def full_legal_name(self) -> str:
        """Full name as it appears on SSN card."""
        parts = [self.legal_first_name]
        if self.legal_middle_name:
            parts.append(self.legal_middle_name)
        parts.append(self.legal_last_name)
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(parts)

    def to_dict(self) -> dict:
        return {
            "person_id": self.person_id,
            "relationship": self.relationship.value if isinstance(self.relationship, RelationshipType) else self.relationship,
            "age": self.age,
            "sex": self.sex,
            "race": self.race,
            "hispanic_origin": self.hispanic_origin,
            "legal_first_name": self.legal_first_name,
            "legal_middle_name": self.legal_middle_name,
            "legal_last_name": self.legal_last_name,
            "suffix": self.suffix,
            "ssn": self.ssn,
            "dob": self.dob.isoformat() if self.dob else None,
            "phone": self.phone,
            "email": self.email,
            "id_type": self.id_type,
            "id_state": self.id_state,
            "id_number": self.id_number,
            "id_expiry": self.id_expiry.isoformat() if self.id_expiry else None,
            "id_address": self.id_address.to_dict() if self.id_address else None,
            "is_dependent": self.is_dependent,
            "can_be_claimed": self.can_be_claimed,
            "months_in_home": self.months_in_home,
            "is_full_time_student": self.is_full_time_student,
            "employment_status": self.employment_status,
            "education": self.education,
            "occupation_code": self.occupation_code,
            "occupation_title": self.occupation_title,
            "w2s": [w.to_dict() for w in self.w2s],
            "form_1099_ints": [f.to_dict() for f in self.form_1099_ints],
            "form_1099_divs": [f.to_dict() for f in self.form_1099_divs],
            "form_1099_rs": [f.to_dict() for f in self.form_1099_rs],
            "ssa_1099": self.ssa_1099.to_dict() if self.ssa_1099 else None,
            "form_1099_necs": [f.to_dict() for f in self.form_1099_necs],
            "total_income": self.total_income(),
            "is_adult": self.is_adult(),
        }


@dataclass
class Household:
    """
    A group of people living at one address.

    Populated incrementally:
    - Sprint 3: pattern, members (demographics only)
    - Sprint 4: address, PII on members
    - Sprint 9+: income, expenses
    """
    household_id: str = ""
    state: str = ""
    year: int = 0
    pattern: str = ""
    members: List[Person] = field(default_factory=list)
    address: Optional[Address] = None

    # Pattern metadata
    expected_adults: Optional[int] = None
    expected_children_range: Optional[Tuple[int, int]] = None
    expected_complexity: Optional[str] = None

    # Household-level expenses (Sprint 9+)
    property_taxes: int = 0
    mortgage_interest: int = 0
    state_income_tax: int = 0
    medical_expenses: int = 0
    charitable_contributions: int = 0
    child_care_expenses: int = 0
    education_expenses: int = 0

    # --- Helper Methods ---

    def get_adults(self) -> List[Person]:
        return [p for p in self.members if p.is_adult()]

    def get_children(self) -> List[Person]:
        return [p for p in self.members if p.is_child()]

    def get_householder(self) -> Optional[Person]:
        for p in self.members:
            if p.relationship == RelationshipType.HOUSEHOLDER:
                return p
        return None

    def get_spouse(self) -> Optional[Person]:
        for p in self.members:
            if p.relationship == RelationshipType.SPOUSE:
                return p
        return None

    def get_dependents(self) -> List[Person]:
        return [p for p in self.members if p.is_dependent or p.can_be_claimed]

    def is_married(self) -> bool:
        return self.get_spouse() is not None

    def total_household_income(self) -> int:
        return sum(p.total_income() for p in self.members)

    def derive_filing_status(self) -> FilingStatus:
        """Derive filing status from household composition."""
        if self.is_married():
            return FilingStatus.MARRIED_FILING_JOINTLY
        children = self.get_children()
        if children:
            return FilingStatus.HEAD_OF_HOUSEHOLD
        return FilingStatus.SINGLE

    def to_dict(self) -> dict:
        return {
            "household_id": self.household_id,
            "state": self.state,
            "year": self.year,
            "pattern": self.pattern,
            "address": self.address.to_dict() if self.address else None,
            "members": [m.to_dict() for m in self.members],
            "adult_count": len(self.get_adults()),
            "child_count": len(self.get_children()),
            "total_household_income": self.total_household_income(),
            "is_married": self.is_married(),
            "filing_status": self.derive_filing_status().value,
        }


@dataclass
class FilingUnit:
    """A tax return within a household."""
    filing_unit_id: str = ""
    household_id: str = ""
    filing_status: FilingStatus = FilingStatus.SINGLE

    primary_filer: Optional[Person] = None
    spouse_filer: Optional[Person] = None
    dependents: List[Person] = field(default_factory=list)

    # Tax calculation fields (future)
    adjusted_gross_income: int = 0
    taxable_income: int = 0
    total_tax: int = 0
    refund_or_owed: int = 0


@dataclass
class ClientFact:
    """A verbal fact the client provides during the VITA intake interview.

    These are facts that cannot be verified from identity documents alone
    and must be obtained by asking the client directly.
    """
    category: str = ""  # "citizenship", "contact", "employment", "dependent", "filing"
    question: str = ""  # What the volunteer would ask
    answer: str = ""  # What the client responds
    form_field: str = ""  # PDF field name this maps to
    person_id: str = ""  # Which person this fact is about
    required: bool = True  # Whether this fact is needed to complete the form


@dataclass
class InjectedError:
    """A deliberate discrepancy seeded for verification exercises."""
    error_id: str = ""
    category: str = ""  # "name", "ssn", "address", "dob", "filing_status", "dependent"
    field: str = ""  # Specific field affected (e.g., "spouse_ssn")
    person_id: str = ""  # Which person is affected
    document: str = ""  # Which document has the error (e.g., "intake_form", "ssn_card")
    correct_value: str = ""  # Ground truth
    erroneous_value: str = ""  # What was placed on the document
    explanation: str = ""  # Human-readable for grading feedback
    difficulty: str = ""  # "easy", "medium", "hard"


@dataclass
class GradingResult:
    """Result of grading a student submission."""
    score: int = 0
    max_score: int = 0
    correct_flags: List[dict] = field(default_factory=list)
    missed_flags: List[dict] = field(default_factory=list)
    false_flags: List[dict] = field(default_factory=list)
    accuracy: float = 0.0
    feedback: str = ""
    field_feedback: List[dict] = field(default_factory=list)


@dataclass
class Scenario:
    """A complete exercise package."""
    scenario_id: str = ""
    mode: str = ""  # "intake", "verify", "crosscheck"
    difficulty: str = ""  # "easy", "medium", "hard"
    household: Optional[Household] = None
    injected_errors: List[InjectedError] = field(default_factory=list)
    client_facts: List[ClientFact] = field(default_factory=list)
    document_paths: dict = field(default_factory=dict)  # {"ssn_primary": "/path/to.pdf", ...}
    created_at: Optional[str] = None


# =============================================================================
# Household Pattern Metadata
# =============================================================================

PATTERN_METADATA = {
    "married_couple_no_children": {
        "expected_adults": 2,
        "expected_children": (0, 0),
        "complexity": "simple",
        "description": "Married couple without children",
        "relationships": [RelationshipType.HOUSEHOLDER, RelationshipType.SPOUSE],
    },
    "married_couple_with_children": {
        "expected_adults": 2,
        "expected_children": (1, 5),
        "complexity": "simple",
        "description": "Married couple with children",
        "relationships": [RelationshipType.HOUSEHOLDER, RelationshipType.SPOUSE],
    },
    "single_parent": {
        "expected_adults": 1,
        "expected_children": (1, 4),
        "complexity": "simple",
        "description": "Single parent with children",
        "relationships": [RelationshipType.HOUSEHOLDER],
    },
    "single_adult": {
        "expected_adults": 1,
        "expected_children": (0, 0),
        "complexity": "simple",
        "description": "Single person living alone",
        "relationships": [RelationshipType.HOUSEHOLDER],
    },
    "blended_family": {
        "expected_adults": 2,
        "expected_children": (2, 5),
        "complexity": "complex",
        "description": "Married couple with bio and/or stepchildren",
        "relationships": [RelationshipType.HOUSEHOLDER, RelationshipType.SPOUSE],
    },
    "multigenerational": {
        "expected_adults": (2, 4),
        "expected_children": (0, 3),
        "complexity": "complex",
        "description": "3+ generations in household",
        "relationships": [RelationshipType.HOUSEHOLDER],
    },
    "unmarried_partners": {
        "expected_adults": 2,
        "expected_children": (0, 3),
        "complexity": "complex",
        "description": "Cohabiting couple (not married)",
        "relationships": [RelationshipType.HOUSEHOLDER, RelationshipType.UNMARRIED_PARTNER],
    },
    "other": {
        "expected_adults": (1, 5),
        "expected_children": (0, 3),
        "complexity": "medium",
        "description": "Other household arrangement",
        "relationships": [RelationshipType.HOUSEHOLDER],
    },
}
