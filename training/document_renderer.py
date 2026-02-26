"""
Document renderer — generates mock identity documents and tax forms.

Uses Jinja2 templates + WeasyPrint to produce:
- SSN card images (PNG)
- Driver's license images (PNG)
- Form 13614-C Part I (PDF, blank or pre-filled)
- Form 1040 header (PDF, future)
- W-2 forms (PDF, future)

All documents include "SAMPLE — FOR TRAINING USE ONLY" watermark.

Templates are in training/templates/
"""

import logging
from pathlib import Path
from typing import Optional

from generator.models import Person, Household

logger = logging.getLogger(__name__)


class DocumentRenderer:
    """Renders HTML templates to document images and PDFs."""

    def __init__(self, output_dir: str = "data/scenarios"):
        self.output_dir = Path(output_dir)
        # TODO: Initialize Jinja2 environment with templates/ directory

    def render_ssn_card(self, person: Person) -> Path:
        """Render SSN card as PNG. Returns path to generated image."""
        # TODO: Implement
        pass

    def render_drivers_license(self, person: Person) -> Path:
        """Render driver's license as PNG. Returns path to generated image."""
        # TODO: Implement
        pass

    def render_intake_form(self, household: Household, prefilled: bool = False) -> Path:
        """Render Form 13614-C Part I as PDF. Returns path to generated PDF."""
        # TODO: Implement
        pass

    def render_w2(self, person: Person) -> Path:
        """Render W-2 as PDF. Future — Sprint 9."""
        pass

    def render_1040_header(self, household: Household) -> Path:
        """Render Form 1040 page 1 header. Future."""
        pass
