"""
Document renderer — generates mock identity documents and tax forms.

Uses Jinja2 templates + WeasyPrint to produce:
- SSN card (PDF)
- Driver's license (PDF)
- State ID card (PDF)
- Form 13614-C Part I (PDF, blank or pre-filled) — future
- Form 1040 header (PDF) — future
- W-2 forms (PDF) — future

All documents include "SAMPLE — FOR TRAINING USE ONLY" watermark.

Templates are in training/templates/
"""

import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from generator.models import Household, Person

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
    # Standard validity period — back-calculate a plausible issue date
    return date(expiry.year - 8, expiry.month, expiry.day)


class DocumentRenderer:
    """Renders HTML templates to document images (PNG) and PDFs.

    Args:
        output_dir: Directory to write rendered files into.
    """

    def __init__(self, output_dir: str = "data/scenarios") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
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

    def render_ssn_card(self, person: Person) -> Path:
        """Render an SSN card as PDF.

        Args:
            person: Person with ssn and name fields populated.

        Returns:
            Path to the generated PDF file.
        """
        html = self.render_ssn_card_html(person)
        filename = f"ssn_{person.person_id}.pdf"
        out_path = self.output_dir / filename
        self._render_html_to_pdf(html, out_path)
        logger.info("Rendered SSN card: %s", out_path)
        return out_path

    # =================================================================
    # Driver's License
    # =================================================================

    def render_drivers_license(self, person: Person) -> Path:
        """Render a driver's license as PDF.

        Args:
            person: Person with id_type='drivers_license' and PII populated.

        Returns:
            Path to the generated PDF file.
        """
        return self._render_id_card(person, "drivers_license")

    # =================================================================
    # State ID Card
    # =================================================================

    def render_state_id(self, person: Person) -> Path:
        """Render a state identification card as PDF.

        Args:
            person: Person with id_type='state_id' and PII populated.

        Returns:
            Path to the generated PDF file.
        """
        return self._render_id_card(person, "state_id")

    # =================================================================
    # Convenience: render whichever ID type the person has
    # =================================================================

    def render_photo_id(self, person: Person) -> Optional[Path]:
        """Render the person's photo ID (DL or state ID) based on id_type.

        Args:
            person: Person with id_type and PII populated.

        Returns:
            Path to generated PDF, or None if person has no ID.
        """
        if person.id_type == "drivers_license":
            return self.render_drivers_license(person)
        elif person.id_type == "state_id":
            return self.render_state_id(person)
        return None

    # =================================================================
    # Render all documents for a household
    # =================================================================

    def render_household_documents(
        self, household: Household,
    ) -> Dict[str, Path]:
        """Render SSN cards and photo IDs for all household members.

        Args:
            household: Household with PII populated on all members.

        Returns:
            Dict mapping document labels to file paths, e.g.
            {"ssn_P1": Path(...), "id_P1": Path(...), "ssn_P2": Path(...)}.
        """
        paths: Dict[str, Path] = {}
        for person in household.members:
            pid = person.person_id
            # SSN card for everyone
            if person.ssn:
                paths[f"ssn_{pid}"] = self.render_ssn_card(person)
            # Photo ID for adults
            id_path = self.render_photo_id(person)
            if id_path is not None:
                paths[f"id_{pid}"] = id_path
        logger.info(
            "Rendered %d documents for household %s",
            len(paths), household.household_id,
        )
        return paths

    # =================================================================
    # Future stubs
    # =================================================================

    def render_intake_form(
        self, household: Household, prefilled: bool = False,
    ) -> Path:
        """Render Form 13614-C Part I as PDF. Returns path to generated PDF."""
        raise NotImplementedError("Intake form rendering is planned for Sprint 6")

    def render_w2(self, person: Person) -> Path:
        """Render W-2 as PDF. Planned for Sprint 9."""
        raise NotImplementedError("W-2 rendering is planned for Sprint 9")

    def render_1040_header(self, household: Household) -> Path:
        """Render Form 1040 page 1 header. Planned for Sprint 9."""
        raise NotImplementedError("1040 header rendering is planned for Sprint 9")

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

    def _render_id_card(self, person: Person, id_type: str) -> Path:
        """Render a DL or state ID card using the appropriate template.

        Args:
            person: Person with PII and ID fields populated.
            id_type: 'drivers_license' or 'state_id'.

        Returns:
            Path to the generated PDF file.
        """
        html = self._render_id_card_html(person, id_type)

        label = "dl" if id_type == "drivers_license" else "sid"
        filename = f"{label}_{person.person_id}.pdf"
        out_path = self.output_dir / filename
        self._render_html_to_pdf(html, out_path)

        doc_label = "driver's license" if id_type == "drivers_license" else "state ID"
        logger.info("Rendered %s: %s", doc_label, out_path)
        return out_path

    @staticmethod
    def _render_html_to_pdf(html: str, out_path: Path) -> None:
        """Convert an HTML string to a PDF file via WeasyPrint.

        Args:
            html: Fully rendered HTML string.
            out_path: Destination file path (.pdf).

        Raises:
            ImportError: If WeasyPrint is not installed.
        """
        try:
            from weasyprint import HTML  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "WeasyPrint is required for document rendering. "
                "Install it with: pip install weasyprint\n"
                "System dependencies may also be needed — see "
                "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
            )

        doc = HTML(
            string=html,
            base_url=str(_TEMPLATES_DIR),
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.write_pdf(str(out_path))
