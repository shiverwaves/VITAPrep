"""
Document renderer — generates mock identity documents as HTML.

Uses Jinja2 templates to produce HTML strings for browser display:
- SSN card
- Driver's license
- State ID card

All documents include "SAMPLE — FOR TRAINING USE ONLY" watermark.

Templates are in training/templates/
"""

import logging
from datetime import date
from pathlib import Path
from typing import Dict, Optional

from jinja2 import Environment, FileSystemLoader

from generator.models import Person

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
