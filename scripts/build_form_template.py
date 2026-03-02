#!/usr/bin/env python3
"""
Build the fillable Form 13614-C Part I PDF template.

Generates ``training/templates/form_13614c_p1.pdf`` — a fillable PDF
with AcroForm fields (text boxes, checkboxes, radio buttons) that
mirror the IRS VITA intake sheet Part I.

This is a *build-time* script: run it once (or whenever the form layout
changes) and commit the resulting PDF. The ExerciseEngine, form populator,
and grader all reference the field names defined in
``training/form_fields.py``.

Usage:
    python scripts/build_form_template.py
"""

import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas

from training.form_fields import (
    YOU_FIRST_NAME, YOU_MIDDLE_INITIAL, YOU_LAST_NAME,
    YOU_DOB, YOU_SSN, YOU_JOB_TITLE,
    YOU_US_CITIZEN, YOU_NOT_US_CITIZEN,
    YOU_PHONE, YOU_EMAIL,
    ADDR_STREET, ADDR_APT, ADDR_CITY, ADDR_STATE, ADDR_ZIP,
    SPOUSE_FIRST_NAME, SPOUSE_MIDDLE_INITIAL, SPOUSE_LAST_NAME,
    SPOUSE_DOB, SPOUSE_SSN, SPOUSE_JOB_TITLE,
    FILING_STATUS, FS_SINGLE, FS_MFJ, FS_MFS, FS_HOH, FS_QSS,
    dep_field,
    DEP_FIRST_NAME, DEP_LAST_NAME, DEP_DOB, DEP_RELATIONSHIP,
    DEP_MONTHS, DEP_SINGLE_OR_MARRIED, DEP_US_CITIZEN,
    DEP_STUDENT, DEP_DISABLED, MAX_DEPENDENTS,
    CLAIMED_AS_DEPENDENT, NOT_CLAIMED_AS_DEPENDENT,
    PRIOR_YEAR_DEPENDENT, NOT_PRIOR_YEAR_DEPENDENT,
)

# =========================================================================
# Layout constants
# =========================================================================

PAGE_W, PAGE_H = letter  # 612 × 792
MARGIN_LEFT = 0.5 * inch
MARGIN_RIGHT = 0.5 * inch
CONTENT_W = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT

# Colors
HEADER_BG = HexColor("#1a3a5c")
LABEL_COLOR = HexColor("#333333")
BORDER_COLOR = HexColor("#999999")
FIELD_BG = Color(1, 1, 1, 1)  # white

# Font sizes
TITLE_SIZE = 14
SECTION_TITLE_SIZE = 11
LABEL_SIZE = 8
FIELD_FONT_SIZE = 10

# Field dimensions
TEXT_FIELD_H = 18
CHECKBOX_SIZE = 12
ROW_GAP = 4
SECTION_GAP = 10

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "training" / "templates" / "form_13614c_p1.pdf"
)


# =========================================================================
# Helper drawing functions
# =========================================================================

def draw_section_header(c: Canvas, y: float, text: str) -> float:
    """Draw a section header bar and return the new y position."""
    bar_h = 20
    c.setFillColor(HEADER_BG)
    c.rect(MARGIN_LEFT, y - bar_h, CONTENT_W, bar_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", SECTION_TITLE_SIZE)
    c.drawString(MARGIN_LEFT + 8, y - bar_h + 6, text)
    c.setFillColor(black)
    return y - bar_h - ROW_GAP


def draw_label(c: Canvas, x: float, y: float, text: str) -> None:
    """Draw a field label above an input field."""
    c.setFillColor(LABEL_COLOR)
    c.setFont("Helvetica", LABEL_SIZE)
    c.drawString(x, y + TEXT_FIELD_H + 2, text)
    c.setFillColor(black)


def add_text_field(
    c: Canvas, name: str, x: float, y: float, width: float,
    label: str = "",
) -> None:
    """Draw a labeled text input field using the acroForm API."""
    if label:
        draw_label(c, x, y, label)
    c.acroForm.textfield(
        name=name,
        x=x,
        y=y,
        width=width,
        height=TEXT_FIELD_H,
        borderWidth=1,
        borderColor=BORDER_COLOR,
        fillColor=FIELD_BG,
        textColor=black,
        fontName="Helvetica",
        fontSize=FIELD_FONT_SIZE,
        maxlen=100,
        fieldFlags="",
        forceBorder=True,
    )


def add_checkbox(
    c: Canvas, name: str, x: float, y: float,
    label: str = "",
) -> float:
    """Draw a checkbox with label to its right. Returns x after label."""
    c.acroForm.checkbox(
        name=name,
        x=x,
        y=y,
        size=CHECKBOX_SIZE,
        borderWidth=1,
        borderColor=BORDER_COLOR,
        fillColor=FIELD_BG,
        textColor=black,
        buttonStyle="check",
        checked=False,
        forceBorder=True,
        fieldFlags="",
    )
    if label:
        c.setFont("Helvetica", LABEL_SIZE)
        c.setFillColor(LABEL_COLOR)
        label_x = x + CHECKBOX_SIZE + 3
        c.drawString(label_x, y + 2, label)
        c.setFillColor(black)
        return label_x + c.stringWidth(label, "Helvetica", LABEL_SIZE) + 12
    return x + CHECKBOX_SIZE + 6


def add_radio(
    c: Canvas, group_name: str, value: str,
    x: float, y: float, label: str = "",
) -> float:
    """Draw a radio button. Returns x position after the label."""
    c.acroForm.radio(
        name=group_name,
        value=value,
        x=x,
        y=y,
        size=CHECKBOX_SIZE,
        borderWidth=1,
        borderColor=BORDER_COLOR,
        fillColor=FIELD_BG,
        textColor=black,
        buttonStyle="circle",
        shape="circle",
        selected=False,
        forceBorder=True,
    )
    if label:
        c.setFont("Helvetica", LABEL_SIZE)
        c.setFillColor(LABEL_COLOR)
        label_x = x + CHECKBOX_SIZE + 3
        c.drawString(label_x, y + 2, label)
        c.setFillColor(black)
        return label_x + c.stringWidth(label, "Helvetica", LABEL_SIZE) + 14
    return x + CHECKBOX_SIZE + 6


def draw_watermark(c: Canvas) -> None:
    """Draw diagonal watermark across the page."""
    c.saveState()
    c.setFillColor(HexColor("#ff0000"))
    c.setFillAlpha(0.08)
    c.setFont("Helvetica-Bold", 40)
    c.translate(PAGE_W / 2, PAGE_H / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, "SAMPLE \u2014 FOR TRAINING USE ONLY")
    c.restoreState()


# =========================================================================
# Main form builder
# =========================================================================

def build_form(output_path: Path) -> Path:
    """Build the fillable 13614-C Part I PDF.

    Args:
        output_path: Where to write the PDF.

    Returns:
        The output path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(output_path), pagesize=letter)
    c.setTitle("Form 13614-C Part I \u2014 Personal Information (SAMPLE)")
    c.setAuthor("VITATrainer")

    y = PAGE_H - 0.5 * inch

    # =================================================================
    # Title
    # =================================================================
    c.setFillColor(HEADER_BG)
    c.setFont("Helvetica-Bold", TITLE_SIZE)
    c.drawString(
        MARGIN_LEFT, y,
        "Form 13614-C  Part I \u2014 Your Personal Information",
    )
    y -= 6
    c.setFont("Helvetica", 8)
    c.setFillColor(LABEL_COLOR)
    c.drawString(
        MARGIN_LEFT, y - 10,
        "Intake/Interview & Quality Review Sheet  |  "
        "SAMPLE \u2014 FOR TRAINING USE ONLY",
    )
    c.setFillColor(black)
    y -= 26

    # =================================================================
    # Section A: About You
    # =================================================================
    y = draw_section_header(c, y, "Section A: About You")

    label_h = 12
    col1_w = 2.8 * inch
    col_mi_w = 0.6 * inch
    col3_w = CONTENT_W - col1_w - col_mi_w - 2 * ROW_GAP
    y -= (TEXT_FIELD_H + label_h)

    # Row 1: First Name, MI, Last Name
    x = MARGIN_LEFT
    add_text_field(c, YOU_FIRST_NAME, x, y, col1_w, "1. First Name")
    x += col1_w + ROW_GAP
    add_text_field(c, YOU_MIDDLE_INITIAL, x, y, col_mi_w, "MI")
    x += col_mi_w + ROW_GAP
    add_text_field(c, YOU_LAST_NAME, x, y, col3_w, "Last Name")

    # Row 2: DOB, SSN
    y -= (TEXT_FIELD_H + label_h + ROW_GAP)
    x = MARGIN_LEFT
    dob_w = 1.8 * inch
    ssn_w = 2.0 * inch
    add_text_field(c, YOU_DOB, x, y, dob_w, "2. Date of Birth (MM/DD/YYYY)")
    x += dob_w + ROW_GAP
    add_text_field(c, YOU_SSN, x, y, ssn_w, "3. Your SSN or ITIN")

    # Row 3: Job title, US Citizen yes/no
    y -= (TEXT_FIELD_H + label_h + ROW_GAP)
    x = MARGIN_LEFT
    job_w = 3.0 * inch
    add_text_field(c, YOU_JOB_TITLE, x, y, job_w, "4. Job Title")
    x += job_w + ROW_GAP * 4

    c.setFont("Helvetica", LABEL_SIZE)
    c.setFillColor(LABEL_COLOR)
    c.drawString(x, y + TEXT_FIELD_H + 2, "5. Are you a U.S. citizen?")
    c.setFillColor(black)
    cb_y = y + 3
    x2 = add_checkbox(c, YOU_US_CITIZEN, x, cb_y, "Yes")
    add_checkbox(c, YOU_NOT_US_CITIZEN, x2, cb_y, "No")

    # Row 4: Phone, Email
    y -= (TEXT_FIELD_H + label_h + ROW_GAP)
    x = MARGIN_LEFT
    phone_w = 2.2 * inch
    email_w = CONTENT_W - phone_w - ROW_GAP
    add_text_field(c, YOU_PHONE, x, y, phone_w, "6. Daytime Phone Number")
    x += phone_w + ROW_GAP
    add_text_field(c, YOU_EMAIL, x, y, email_w, "7. Email Address")

    y -= SECTION_GAP

    # =================================================================
    # Section B: Mailing Address
    # =================================================================
    y = draw_section_header(c, y, "Section B: Mailing Address")
    y -= (TEXT_FIELD_H + label_h)

    x = MARGIN_LEFT
    street_w = 4.5 * inch
    apt_w = CONTENT_W - street_w - ROW_GAP
    add_text_field(c, ADDR_STREET, x, y, street_w, "8. Street Address")
    x += street_w + ROW_GAP
    add_text_field(c, ADDR_APT, x, y, apt_w, "Apt #")

    y -= (TEXT_FIELD_H + label_h + ROW_GAP)
    x = MARGIN_LEFT
    city_w = 3.2 * inch
    state_w = 1.0 * inch
    zip_w = CONTENT_W - city_w - state_w - 2 * ROW_GAP
    add_text_field(c, ADDR_CITY, x, y, city_w, "City")
    x += city_w + ROW_GAP
    add_text_field(c, ADDR_STATE, x, y, state_w, "State")
    x += state_w + ROW_GAP
    add_text_field(c, ADDR_ZIP, x, y, zip_w, "ZIP Code")

    y -= SECTION_GAP

    # =================================================================
    # Section C: About Your Spouse
    # =================================================================
    y = draw_section_header(c, y, "Section C: About Your Spouse (if applicable)")
    y -= (TEXT_FIELD_H + label_h)

    x = MARGIN_LEFT
    add_text_field(c, SPOUSE_FIRST_NAME, x, y, col1_w, "9. First Name")
    x += col1_w + ROW_GAP
    add_text_field(c, SPOUSE_MIDDLE_INITIAL, x, y, col_mi_w, "MI")
    x += col_mi_w + ROW_GAP
    add_text_field(c, SPOUSE_LAST_NAME, x, y, col3_w, "Last Name")

    y -= (TEXT_FIELD_H + label_h + ROW_GAP)
    x = MARGIN_LEFT
    add_text_field(c, SPOUSE_DOB, x, y, dob_w, "10. Spouse Date of Birth")
    x += dob_w + ROW_GAP
    add_text_field(c, SPOUSE_SSN, x, y, ssn_w, "11. Spouse SSN or ITIN")

    y -= (TEXT_FIELD_H + label_h + ROW_GAP)
    x = MARGIN_LEFT
    add_text_field(c, SPOUSE_JOB_TITLE, x, y, job_w, "12. Spouse Job Title")

    y -= SECTION_GAP

    # =================================================================
    # Section D: Filing Status
    # =================================================================
    y = draw_section_header(c, y, "Section D: Filing Status")

    filing_labels = {
        FS_SINGLE: "Single",
        FS_MFJ: "Married Filing Jointly (MFJ)",
        FS_MFS: "Married Filing Separately (MFS)",
        FS_HOH: "Head of Household (HOH)",
        FS_QSS: "Qualifying Surviving Spouse (QSS)",
    }

    y -= (CHECKBOX_SIZE + 6)
    c.setFont("Helvetica", LABEL_SIZE)
    c.setFillColor(LABEL_COLOR)
    c.drawString(
        MARGIN_LEFT, y + CHECKBOX_SIZE + 4,
        "13. Check your filing status:",
    )
    c.setFillColor(black)

    x = MARGIN_LEFT
    for val in [FS_SINGLE, FS_MFJ, FS_MFS]:
        x = add_radio(c, FILING_STATUS, val, x, y, filing_labels[val])

    y -= (CHECKBOX_SIZE + ROW_GAP + 4)
    x = MARGIN_LEFT
    for val in [FS_HOH, FS_QSS]:
        x = add_radio(c, FILING_STATUS, val, x, y, filing_labels[val])

    y -= SECTION_GAP

    # =================================================================
    # Section E: Dependents
    # =================================================================
    y = draw_section_header(c, y, "Section E: Dependents")

    dep_col_first = 1.3 * inch
    dep_col_last = 1.3 * inch
    dep_col_dob = 1.1 * inch
    dep_col_rel = 1.1 * inch
    dep_col_months = 0.6 * inch
    dep_col_sm = 0.45 * inch
    dep_col_cb = 0.40 * inch

    # Column header positions
    col_positions = [MARGIN_LEFT]
    for w in [dep_col_first, dep_col_last, dep_col_dob, dep_col_rel,
              dep_col_months, dep_col_sm, dep_col_cb, dep_col_cb]:
        col_positions.append(col_positions[-1] + w + 2)

    header_labels = [
        "First Name", "Last Name", "DOB", "Relationship",
        "Mo.", "S/M", "Cit", "Stu", "Dis",
    ]

    y -= 14
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(LABEL_COLOR)
    for hx, htxt in zip(col_positions, header_labels):
        c.drawString(hx, y, htxt)
    c.setFillColor(black)

    for i in range(MAX_DEPENDENTS):
        y -= (TEXT_FIELD_H + ROW_GAP)
        x = MARGIN_LEFT

        add_text_field(c, dep_field(i, DEP_FIRST_NAME), x, y, dep_col_first)
        x += dep_col_first + 2
        add_text_field(c, dep_field(i, DEP_LAST_NAME), x, y, dep_col_last)
        x += dep_col_last + 2
        add_text_field(c, dep_field(i, DEP_DOB), x, y, dep_col_dob)
        x += dep_col_dob + 2
        add_text_field(c, dep_field(i, DEP_RELATIONSHIP), x, y, dep_col_rel)
        x += dep_col_rel + 2
        add_text_field(c, dep_field(i, DEP_MONTHS), x, y, dep_col_months)
        x += dep_col_months + 2

        cb_y = y + 3
        add_checkbox(c, dep_field(i, DEP_SINGLE_OR_MARRIED), x, cb_y)
        x += dep_col_sm + 2
        add_checkbox(c, dep_field(i, DEP_US_CITIZEN), x, cb_y)
        x += dep_col_cb + 2
        add_checkbox(c, dep_field(i, DEP_STUDENT), x, cb_y)
        x += dep_col_cb + 2
        add_checkbox(c, dep_field(i, DEP_DISABLED), x, cb_y)

    y -= SECTION_GAP

    # =================================================================
    # Section F: Additional Questions
    # =================================================================
    y = draw_section_header(c, y, "Section F: Additional Questions")
    y -= (CHECKBOX_SIZE + 8)

    # Q15
    c.setFont("Helvetica", LABEL_SIZE)
    c.setFillColor(LABEL_COLOR)
    c.drawString(
        MARGIN_LEFT, y + CHECKBOX_SIZE + 2,
        "15. Can anyone claim you as a dependent?",
    )
    c.setFillColor(black)
    x = MARGIN_LEFT
    x = add_checkbox(c, CLAIMED_AS_DEPENDENT, x, y, "Yes")
    add_checkbox(c, NOT_CLAIMED_AS_DEPENDENT, x, y, "No")

    # Q16
    y -= (CHECKBOX_SIZE + ROW_GAP + 10)
    c.setFont("Helvetica", LABEL_SIZE)
    c.setFillColor(LABEL_COLOR)
    c.drawString(
        MARGIN_LEFT, y + CHECKBOX_SIZE + 2,
        "16. Have you been claimed as a dependent in prior years?",
    )
    c.setFillColor(black)
    x = MARGIN_LEFT
    x = add_checkbox(c, PRIOR_YEAR_DEPENDENT, x, y, "Yes")
    add_checkbox(c, NOT_PRIOR_YEAR_DEPENDENT, x, y, "No")

    # =================================================================
    # Watermark
    # =================================================================
    draw_watermark(c)

    c.save()
    return output_path


# =========================================================================
# CLI entry point
# =========================================================================

if __name__ == "__main__":
    path = build_form(OUTPUT_PATH)
    print(f"Built fillable PDF: {path}")
    print(f"File size: {path.stat().st_size:,} bytes")
