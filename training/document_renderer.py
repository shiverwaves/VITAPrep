"""
Document renderer — generates mock identity and tax documents as HTML.

Uses Jinja2 templates to produce HTML strings for browser display:
- SSN card
- Driver's license / State ID card
- W-2 Wage and Tax Statement
- 1099-INT Interest Income
- 1099-DIV Dividends and Distributions
- 1099-R Distributions From Pensions
- SSA-1099 Social Security Benefit Statement
- 1099-NEC Nonemployee Compensation

All documents include "SAMPLE — FOR TRAINING USE ONLY" watermark.

Templates are in training/templates/
"""

import logging
from datetime import date
from pathlib import Path
from typing import Dict, Optional

from jinja2 import Environment, FileSystemLoader

from generator.models import (
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    Form1099R,
    Person,
    SSA1099,
    W2,
)

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Full state names for document headers.
_STATE_NAMES: Dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def _format_dollars(amount: int) -> str:
    """Format an integer dollar amount as $X,XXX.00 for tax documents."""
    if amount == 0:
        return ""
    return f"${amount:,.2f}"


def _format_date(d: Optional[date]) -> str:
    """Format a date as MM/DD/YYYY for documents."""
    if d is None:
        return ""
    return d.strftime("%m/%d/%Y")


def _estimate_issue_date(expiry: Optional[date]) -> Optional[date]:
    """Estimate the issue date from expiry (assume 8-year validity)."""
    if expiry is None:
        return None
    return date(expiry.year - 8, expiry.month, expiry.day)


class DocumentRenderer:
    """Renders Jinja2 templates to HTML strings for browser display.

    Args:
        output_dir: Legacy parameter, kept for API compatibility.
    """

    def __init__(self, output_dir: str = "data/scenarios") -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=False,
        )

    # =================================================================
    # SSN Card
    # =================================================================

    def render_ssn_card_html(self, person: Person) -> str:
        """Render an SSN card as an HTML string for browser display.

        Args:
            person: Person with ssn and name fields populated.

        Returns:
            Rendered HTML string.
        """
        template = self._env.get_template("ssn_card.html")
        return template.render(
            ssn=person.ssn,
            full_name=person.full_legal_name(),
        )

    # =================================================================
    # Photo ID (Driver's License / State ID)
    # =================================================================

    def render_photo_id_html(self, person: Person) -> Optional[str]:
        """Render the person's photo ID as HTML based on id_type.

        Args:
            person: Person with id_type and PII populated.

        Returns:
            Rendered HTML string, or None if person has no ID.
        """
        if person.id_type == "drivers_license":
            return self._render_id_card_html(person, "drivers_license")
        elif person.id_type == "state_id":
            return self._render_id_card_html(person, "state_id")
        return None

    # =================================================================
    # Internal helpers
    # =================================================================

    # =================================================================
    # W-2 Wage and Tax Statement
    # =================================================================

    def render_w2_html(self, person: Person, w2: W2, tax_year: int = 2022) -> str:
        """Render a W-2 form as an HTML string.

        Args:
            person: Person (employee) with PII populated.
            w2: W2 dataclass with wage and tax data.
            tax_year: Tax year to display on the form.

        Returns:
            Rendered HTML string.
        """
        template = self._env.get_template("w2.html")

        employer_addr = ""
        if w2.employer and w2.employer.address:
            a = w2.employer.address
            parts = [a.street]
            if a.apt:
                parts.append(a.apt)
            parts.append(f"{a.city}, {a.state} {a.zip_code}")
            employer_addr = ", ".join(parts)

        employee_addr = ""
        if person.id_address:
            a = person.id_address
            parts = [a.street]
            if a.apt:
                parts.append(a.apt)
            parts.append(f"{a.city}, {a.state} {a.zip_code}")
            employee_addr = ", ".join(parts)

        box_12_list = [{"code": c, "amount": _format_dollars(a)} for c, a in w2.box_12]

        return template.render(
            tax_year=tax_year,
            control_number=w2.control_number,
            employer_ein=w2.employer.ein if w2.employer else "",
            employer_name=w2.employer.name if w2.employer else "",
            employer_address=employer_addr,
            employee_name=person.full_legal_name(),
            employee_ssn=person.ssn,
            employee_address=employee_addr,
            wages=_format_dollars(w2.wages),
            federal_tax_withheld=_format_dollars(w2.federal_tax_withheld),
            social_security_wages=_format_dollars(w2.social_security_wages),
            social_security_tax=_format_dollars(w2.social_security_tax),
            medicare_wages=_format_dollars(w2.medicare_wages),
            medicare_tax=_format_dollars(w2.medicare_tax),
            state=w2.state,
            state_wages=_format_dollars(w2.state_wages),
            state_tax=_format_dollars(w2.state_tax),
            box_12=box_12_list,
        )

    # =================================================================
    # 1099-INT Interest Income
    # =================================================================

    def render_1099_int_html(
        self, person: Person, form: Form1099INT, tax_year: int = 2022
    ) -> str:
        """Render a 1099-INT form as an HTML string.

        Args:
            person: Person (recipient) with PII populated.
            form: Form1099INT dataclass.
            tax_year: Tax year to display on the form.

        Returns:
            Rendered HTML string.
        """
        template = self._env.get_template("1099_int.html")
        return template.render(
            tax_year=tax_year,
            payer_name=form.payer_name,
            payer_tin=form.payer_tin,
            recipient_name=person.full_legal_name(),
            recipient_tin=person.ssn,
            interest_income=_format_dollars(form.interest_income),
            us_savings_bond_interest=_format_dollars(form.us_savings_bond_interest),
            federal_tax_withheld=_format_dollars(form.federal_tax_withheld),
        )

    # =================================================================
    # 1099-DIV Dividends and Distributions
    # =================================================================

    def render_1099_div_html(
        self, person: Person, form: Form1099DIV, tax_year: int = 2022
    ) -> str:
        """Render a 1099-DIV form as an HTML string.

        Args:
            person: Person (recipient) with PII populated.
            form: Form1099DIV dataclass.
            tax_year: Tax year to display on the form.

        Returns:
            Rendered HTML string.
        """
        template = self._env.get_template("1099_div.html")
        return template.render(
            tax_year=tax_year,
            payer_name=form.payer_name,
            payer_tin=form.payer_tin,
            recipient_name=person.full_legal_name(),
            recipient_tin=person.ssn,
            ordinary_dividends=_format_dollars(form.ordinary_dividends),
            qualified_dividends=_format_dollars(form.qualified_dividends),
            capital_gain_distributions=_format_dollars(form.capital_gain_distributions),
            federal_tax_withheld=_format_dollars(form.federal_tax_withheld),
        )

    # =================================================================
    # 1099-R Distributions From Pensions
    # =================================================================

    def render_1099_r_html(
        self, person: Person, form: Form1099R, tax_year: int = 2022
    ) -> str:
        """Render a 1099-R form as an HTML string.

        Args:
            person: Person (recipient) with PII populated.
            form: Form1099R dataclass.
            tax_year: Tax year to display on the form.

        Returns:
            Rendered HTML string.
        """
        template = self._env.get_template("1099_r.html")
        return template.render(
            tax_year=tax_year,
            payer_name=form.payer_name,
            payer_tin=form.payer_tin,
            recipient_name=person.full_legal_name(),
            recipient_tin=person.ssn,
            gross_distribution=_format_dollars(form.gross_distribution),
            taxable_amount=_format_dollars(form.taxable_amount),
            federal_tax_withheld=_format_dollars(form.federal_tax_withheld),
            distribution_code=form.distribution_code,
        )

    # =================================================================
    # SSA-1099 Social Security Benefit Statement
    # =================================================================

    def render_ssa_1099_html(
        self, person: Person, form: SSA1099, tax_year: int = 2022
    ) -> str:
        """Render an SSA-1099 form as an HTML string.

        Args:
            person: Person (beneficiary) with PII populated.
            form: SSA1099 dataclass.
            tax_year: Tax year to display on the form.

        Returns:
            Rendered HTML string.
        """
        template = self._env.get_template("ssa_1099.html")
        return template.render(
            tax_year=tax_year,
            recipient_name=person.full_legal_name(),
            recipient_tin=person.ssn,
            total_benefits=_format_dollars(form.total_benefits),
            benefits_repaid=_format_dollars(form.benefits_repaid),
            net_benefits=_format_dollars(form.net_benefits),
        )

    # =================================================================
    # 1099-NEC Nonemployee Compensation
    # =================================================================

    def render_1099_nec_html(
        self, person: Person, form: Form1099NEC, tax_year: int = 2022
    ) -> str:
        """Render a 1099-NEC form as an HTML string.

        Args:
            person: Person (recipient) with PII populated.
            form: Form1099NEC dataclass.
            tax_year: Tax year to display on the form.

        Returns:
            Rendered HTML string.
        """
        template = self._env.get_template("1099_nec.html")
        return template.render(
            tax_year=tax_year,
            payer_name=form.payer_name,
            payer_tin=form.payer_tin,
            recipient_name=person.full_legal_name(),
            recipient_tin=person.ssn,
            nonemployee_compensation=_format_dollars(form.nonemployee_compensation),
            federal_tax_withheld=_format_dollars(form.federal_tax_withheld),
        )

    # =================================================================
    # Internal helpers
    # =================================================================

    def _render_id_card_html(self, person: Person, id_type: str) -> str:
        """Render a DL or state ID card as an HTML string.

        Args:
            person: Person with PII and ID fields populated.
            id_type: 'drivers_license' or 'state_id'.

        Returns:
            Rendered HTML string.
        """
        if id_type == "state_id":
            template = self._env.get_template("state_id.html")
        else:
            template = self._env.get_template("drivers_license.html")

        addr = person.id_address
        state_name = _STATE_NAMES.get(person.id_state, person.id_state)
        issue_date = _estimate_issue_date(person.id_expiry)

        expired = False
        if person.id_expiry is not None:
            expired = person.id_expiry < date.today()

        return template.render(
            state_name=state_name,
            id_number=person.id_number,
            dl_class="3",
            expiry_formatted=_format_date(person.id_expiry),
            issue_formatted=_format_date(issue_date),
            first_name=person.legal_first_name,
            middle_name=person.legal_middle_name,
            middle_initial=person.legal_middle_name[0] if person.legal_middle_name else "",
            last_name=person.legal_last_name,
            suffix=person.suffix,
            address_street=addr.street if addr else "",
            address_apt=addr.apt if addr else "",
            address_city=addr.city if addr else "",
            address_state=addr.state if addr else "",
            address_zip=addr.zip_code if addr else "",
            dob_formatted=_format_date(person.dob),
            sex=person.sex,
            expired=expired,
        )
