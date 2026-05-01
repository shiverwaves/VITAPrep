"""Tests for tax_core.computation and compute_ground_truth.

Hand-built Household fixtures with known expected values covering:
1. Single filer with one W-2
2. Married couple with children (CTC)
3. Senior with SS income (taxability tiers)
4. Self-employed above SE threshold
5. Itemizer vs standard deduction boundary

Also tests individual computation functions at their boundaries.
"""

import pytest
from types import SimpleNamespace
from typing import List

from tax_core.computation import (
    CreditResult,
    DeductionResult,
    choose_deduction,
    classify_persons,
    compute_agi,
    compute_credits,
    compute_federal_tax,
    compute_se_tax,
    total_payments,
)
from tax_core.ground_truth import (
    SCHEMA_VERSION,
    GroundTruth,
    PersonClassification,
    compute_ground_truth,
)


# ── Fixture helpers ───────────────────────────────────────────────────

def _person(**kwargs):
    defaults = {
        "person_id": "p1",
        "relationship": "householder",
        "age": 35,
        "sex": "M",
        "wage_income": 0,
        "self_employment_income": 0,
        "social_security_income": 0,
        "retirement_income": 0,
        "interest_income": 0,
        "dividend_income": 0,
        "other_income": 0,
        "public_assistance_income": 0,
        "student_loan_interest": 0,
        "educator_expenses": 0,
        "ira_contributions": 0,
        "is_full_time_student": False,
        "is_dependent": False,
        "can_be_claimed": False,
        "months_in_home": 12,
        "w2s": [],
        "form_1099_ints": [],
        "form_1099_divs": [],
        "form_1099_rs": [],
        "form_1099_necs": [],
    }
    defaults.update(kwargs)
    p = SimpleNamespace(**defaults)
    p.total_income = lambda: (
        p.wage_income + p.self_employment_income + p.social_security_income
        + p.retirement_income + p.interest_income + p.dividend_income
        + p.other_income + p.public_assistance_income
    )
    return p


def _w2(**kwargs):
    defaults = {"federal_tax_withheld": 0}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _household(members, **kwargs):
    defaults = {
        "state_income_tax": 0,
        "property_taxes": 0,
        "mortgage_interest": 0,
        "medical_expenses": 0,
        "charitable_contributions": 0,
    }
    defaults.update(kwargs)

    def _get_children():
        return [m for m in members if m.age < 18]

    def _get_adults():
        return [m for m in members if m.age >= 18]

    def _get_householder():
        for m in members:
            rel = m.relationship
            if hasattr(rel, "value"):
                rel = rel.value
            if rel == "householder":
                return m
        return None

    def _get_spouse():
        for m in members:
            rel = m.relationship
            if hasattr(rel, "value"):
                rel = rel.value
            if rel == "spouse":
                return m
        return None

    def _is_married():
        return _get_spouse() is not None

    hh = SimpleNamespace(
        members=members,
        get_children=_get_children,
        get_adults=_get_adults,
        get_householder=_get_householder,
        get_spouse=_get_spouse,
        is_married=_is_married,
        **defaults,
    )
    return hh


# ── compute_se_tax ────────────────────────────────────────────────────

class TestComputeSeTax:
    def test_below_threshold(self):
        p = _person(self_employment_income=399)
        assert compute_se_tax(p) == 0

    def test_at_threshold(self):
        p = _person(self_employment_income=400)
        expected = int(int(400 * 0.9235) * 0.153)
        assert compute_se_tax(p) == expected

    def test_substantial_se(self):
        p = _person(self_employment_income=50000)
        taxable_se = int(50000 * 0.9235)  # 46175
        expected = int(taxable_se * 0.153)  # 7064
        assert compute_se_tax(p) == expected


# ── compute_agi ───────────────────────────────────────────────────────

class TestComputeAGI:
    def test_wages_only(self):
        p = _person(wage_income=50000)
        hh = _household([p])
        assert compute_agi(hh) == 50000

    def test_with_above_line_deductions(self):
        p = _person(
            wage_income=60000,
            student_loan_interest=2000,
            educator_expenses=200,
            ira_contributions=3000,
        )
        hh = _household([p])
        assert compute_agi(hh) == 60000 - 2000 - 200 - 3000

    def test_student_loan_capped(self):
        p = _person(wage_income=60000, student_loan_interest=5000)
        hh = _household([p])
        assert compute_agi(hh) == 60000 - 2500  # cap is $2,500

    def test_educator_expenses_capped(self):
        p = _person(wage_income=40000, educator_expenses=500)
        hh = _household([p])
        assert compute_agi(hh) == 40000 - 300  # cap is $300

    def test_ira_capped_by_age(self):
        p = _person(age=30, wage_income=50000, ira_contributions=10000)
        hh = _household([p])
        assert compute_agi(hh) == 50000 - 6000  # under-50 cap

    def test_ira_catchup_over_50(self):
        p = _person(age=55, wage_income=50000, ira_contributions=10000)
        hh = _household([p])
        assert compute_agi(hh) == 50000 - 7000  # 50+ cap

    def test_se_deduction_half_of_se_tax(self):
        p = _person(self_employment_income=50000)
        hh = _household([p])
        se_tax = compute_se_tax(p)
        expected = 50000 - se_tax // 2
        assert compute_agi(hh) == expected

    def test_multi_person_household(self):
        p1 = _person(person_id="p1", wage_income=50000)
        p2 = _person(
            person_id="p2", relationship="spouse", age=33,
            wage_income=30000, student_loan_interest=1500,
        )
        hh = _household([p1, p2])
        assert compute_agi(hh) == 50000 + 30000 - 1500


# ── choose_deduction ──────────────────────────────────────────────────

class TestChooseDeduction:
    def test_standard_wins(self):
        hh = _household(
            [_person()],
            state_income_tax=3000, property_taxes=2000,
            mortgage_interest=4000, charitable_contributions=1000,
        )
        result = choose_deduction(hh, "single", 50000)
        assert result.deduction_type == "standard"
        assert result.amount == 12950

    def test_itemized_wins(self):
        hh = _household(
            [_person()],
            state_income_tax=8000, property_taxes=5000,
            mortgage_interest=6000, charitable_contributions=2000,
        )
        # SALT = min(13000, 10000) = 10000
        # medical = 0 (no medical expenses)
        # itemized = 10000 + 6000 + 0 + 2000 = 18000 > 12950
        result = choose_deduction(hh, "single", 50000)
        assert result.deduction_type == "itemized"
        assert result.amount == 18000

    def test_boundary_equal_takes_standard(self):
        hh = _household(
            [_person()],
            state_income_tax=5950, property_taxes=4000,
            mortgage_interest=3000,
        )
        # SALT = min(9950, 10000) = 9950
        # itemized = 9950 + 3000 = 12950, exactly equal → standard
        result = choose_deduction(hh, "single", 50000)
        assert result.deduction_type == "standard"


# ── compute_federal_tax ───────────────────────────────────────────────

class TestComputeFederalTax:
    def test_zero_income(self):
        assert compute_federal_tax(0, "single") == 0

    def test_negative_income(self):
        assert compute_federal_tax(-1000, "single") == 0

    def test_single_in_10_bracket(self):
        # $10,000 taxable → all in 10% bracket
        assert compute_federal_tax(10000, "single") == 1000

    def test_single_in_12_bracket(self):
        # $20,000 taxable
        # first $10,275 at 10% = $1,027
        # next $9,725 at 12% = $1,167
        # total = $2,194
        assert compute_federal_tax(20000, "single") == 2194

    def test_single_at_bracket_boundary(self):
        # exactly $10,275 → all at 10%
        assert compute_federal_tax(10275, "single") == 1027

    def test_mfj_wider_brackets(self):
        # MFJ $20,000 → all in 10% bracket (extends to $20,550)
        assert compute_federal_tax(20000, "married_filing_jointly") == 2000

    def test_mfj_spans_brackets(self):
        # MFJ $50,000
        # first $20,550 at 10% = $2,055
        # next $29,450 at 12% = $3,534
        # total = $5,589
        assert compute_federal_tax(50000, "married_filing_jointly") == 5589

    def test_hoh_brackets(self):
        # HoH $20,000
        # first $14,650 at 10% = $1,465
        # next $5,350 at 12% = $642
        # total = $2,107
        assert compute_federal_tax(20000, "head_of_household") == 2107

    def test_higher_bracket(self):
        # Single $100,000
        # $10,275 at 10% = $1,027
        # $31,500 at 12% = $3,780
        # $47,300 at 22% = $10,406
        # $10,925 at 24% = $2,622
        # total = $17,835
        assert compute_federal_tax(100000, "single") == 17835


# ── classify_persons ──────────────────────────────────────────────────

class TestClassifyPersons:
    def test_single_filer(self):
        p = _person()
        hh = _household([p])
        cls = classify_persons(hh, "single")
        assert cls["p1"].role == "primary"
        assert cls["p1"].dependency_type == "none"

    def test_married_couple(self):
        p1 = _person(person_id="p1")
        p2 = _person(person_id="p2", relationship="spouse")
        hh = _household([p1, p2])
        cls = classify_persons(hh, "married_filing_jointly")
        assert cls["p1"].role == "primary"
        assert cls["p2"].role == "spouse"

    def test_qualifying_child(self):
        p1 = _person(person_id="p1")
        child = _person(
            person_id="c1", relationship="biological_child",
            age=10, months_in_home=12,
        )
        hh = _household([p1, child])
        cls = classify_persons(hh, "head_of_household")
        assert cls["c1"].role == "dependent"
        assert cls["c1"].dependency_type == "qualifying_child"
        assert cls["c1"].credit_eligibility["ctc"] is True

    def test_child_17_no_ctc(self):
        """Child 17+ is qualifying child but no CTC (must be under 17)."""
        p1 = _person(person_id="p1")
        child = _person(
            person_id="c1", relationship="biological_child",
            age=17, months_in_home=12,
        )
        hh = _household([p1, child])
        cls = classify_persons(hh, "head_of_household")
        assert cls["c1"].dependency_type == "qualifying_child"
        assert cls["c1"].credit_eligibility["ctc"] is False

    def test_qualifying_relative(self):
        p1 = _person(person_id="p1", wage_income=50000)
        parent = _person(
            person_id="pr1", relationship="parent",
            age=70, wage_income=3000,
        )
        hh = _household([p1, parent])
        cls = classify_persons(hh, "single")
        assert cls["pr1"].dependency_type == "qualifying_relative"

    def test_child_fails_residency_falls_to_qr(self):
        """Child who fails residency (4 months) but has $0 income qualifies
        as qualifying relative instead (bio child in QR relationship set)."""
        p1 = _person(person_id="p1")
        child = _person(
            person_id="c1", relationship="biological_child",
            age=10, months_in_home=4,
        )
        hh = _household([p1, child])
        cls = classify_persons(hh, "head_of_household")
        assert cls["c1"].dependency_type == "qualifying_relative"
        assert cls["c1"].role == "dependent"

    def test_non_relative_not_dependent(self):
        """Roommate with $0 income is not a dependent (relationship fails)."""
        p1 = _person(person_id="p1", wage_income=50000)
        roommate = _person(
            person_id="r1", relationship="roommate",
            age=25, wage_income=0,
        )
        hh = _household([p1, roommate])
        cls = classify_persons(hh, "single")
        assert cls["r1"].dependency_type == "none"
        assert cls["r1"].role == "other"


# ── total_payments ────────────────────────────────────────────────────

class TestTotalPayments:
    def test_single_w2(self):
        p = _person(w2s=[_w2(federal_tax_withheld=5000)])
        hh = _household([p])
        assert total_payments(hh) == 5000

    def test_multiple_w2s(self):
        p = _person(w2s=[
            _w2(federal_tax_withheld=3000),
            _w2(federal_tax_withheld=2000),
        ])
        hh = _household([p])
        assert total_payments(hh) == 5000

    def test_includes_1099_withholding(self):
        p = _person(
            w2s=[_w2(federal_tax_withheld=4000)],
            form_1099_ints=[SimpleNamespace(federal_tax_withheld=100)],
            form_1099_divs=[SimpleNamespace(federal_tax_withheld=200)],
            form_1099_rs=[SimpleNamespace(federal_tax_withheld=300)],
            form_1099_necs=[SimpleNamespace(federal_tax_withheld=0)],
        )
        hh = _household([p])
        assert total_payments(hh) == 4600

    def test_no_documents(self):
        p = _person()
        hh = _household([p])
        assert total_payments(hh) == 0


# ── compute_credits ──────────────────────────────────────────────────

class TestComputeCredits:
    def test_no_qualifying_children(self):
        p = _person(wage_income=50000)
        hh = _household([p])
        cls = classify_persons(hh, "single")
        result = compute_credits(hh, cls, "single", 50000, 5000)
        assert result.details["ctc"] == 0

    def test_ctc_two_children(self):
        p = _person(person_id="p1", wage_income=50000)
        c1 = _person(
            person_id="c1", relationship="biological_child",
            age=10, months_in_home=12,
        )
        c2 = _person(
            person_id="c2", relationship="biological_child",
            age=8, months_in_home=12,
        )
        hh = _household([p, c1, c2])
        cls = classify_persons(hh, "head_of_household")
        # tax_before_credits high enough to absorb full CTC
        result = compute_credits(hh, cls, "head_of_household", 50000, 10000)
        assert result.details["ctc"] == 4000
        assert result.nonrefundable_total == 4000

    def test_ctc_capped_by_tax(self):
        p = _person(person_id="p1", wage_income=20000)
        c1 = _person(
            person_id="c1", relationship="biological_child",
            age=10, months_in_home=12,
        )
        hh = _household([p, c1])
        cls = classify_persons(hh, "head_of_household")
        result = compute_credits(hh, cls, "head_of_household", 20000, 500)
        assert result.details["ctc"] == 500
        assert result.nonrefundable_total == 500
        # remaining goes to ACTC
        assert result.details["actc"] > 0

    def test_ctc_phaseout(self):
        p = _person(person_id="p1", wage_income=250000)
        c1 = _person(
            person_id="c1", relationship="biological_child",
            age=10, months_in_home=12,
        )
        hh = _household([p, c1])
        cls = classify_persons(hh, "single")
        # AGI $250k, single threshold $200k
        # excess = $50k → reduction = 50 * $50 = $2,500
        # raw CTC = $2,000 - $2,500 = $0 (can't go below 0)
        result = compute_credits(hh, cls, "single", 250000, 40000)
        assert result.details["ctc"] == 0


# ═════════════════════════════════════════════════════════════════════
# End-to-end: compute_ground_truth with 5+ household patterns
# ═════════════════════════════════════════════════════════════════════

class TestComputeGroundTruth:
    def test_pattern1_single_w2(self):
        """Single filer, $50k wages, $5k withheld, standard deduction."""
        p = _person(
            wage_income=50000,
            w2s=[_w2(federal_tax_withheld=5000)],
        )
        hh = _household([p])
        gt = compute_ground_truth(hh)

        assert gt.schema_version == SCHEMA_VERSION
        assert gt.filing_status == "single"
        assert gt.agi == 50000
        assert gt.deduction_type == "standard"
        assert gt.standard_deduction == 12950
        assert gt.taxable_income == 50000 - 12950  # 37050
        assert gt.total_tax == compute_federal_tax(37050, "single")
        assert gt.refund_or_owed == 5000 + 0 - gt.total_tax
        assert len(gt.person_classifications) == 1
        assert gt.person_classifications["p1"].role == "primary"

    def test_pattern2_married_with_children(self):
        """MFJ, two children under 17, CTC applies."""
        p1 = _person(
            person_id="p1",
            wage_income=60000,
            w2s=[_w2(federal_tax_withheld=6000)],
        )
        p2 = _person(
            person_id="p2", relationship="spouse", age=33,
            wage_income=40000,
            w2s=[_w2(federal_tax_withheld=4000)],
        )
        c1 = _person(
            person_id="c1", relationship="biological_child", age=10,
        )
        c2 = _person(
            person_id="c2", relationship="biological_child", age=8,
        )
        hh = _household([p1, p2, c1, c2])
        gt = compute_ground_truth(hh)

        assert gt.filing_status == "married_filing_jointly"
        assert gt.agi == 100000
        assert gt.deduction_type == "standard"
        assert gt.standard_deduction == 25900
        assert gt.taxable_income == 74100

        tax = compute_federal_tax(74100, "married_filing_jointly")
        assert gt.credits_claimed["ctc"] == min(4000, tax)
        assert gt.person_classifications["c1"].dependency_type == "qualifying_child"
        assert gt.person_classifications["c2"].dependency_type == "qualifying_child"

    def test_pattern3_senior_with_ss(self):
        """Single senior, SS income + small wage. SS partially taxable."""
        p = _person(
            age=70,
            wage_income=15000,
            social_security_income=18000,
            w2s=[_w2(federal_tax_withheld=1500)],
        )
        hh = _household([p])
        gt = compute_ground_truth(hh)

        assert gt.filing_status == "single"
        # AGI includes total_income = 15000 + 18000 = 33000
        assert gt.agi == 33000
        assert "ss_taxability_p1" in gt.predicate_results
        ss_detail = gt.predicate_results["ss_taxability_p1"]
        assert ss_detail["social_security_income"] == 18000

    def test_pattern4_self_employed(self):
        """Single filer with SE income above $400 threshold."""
        p = _person(
            self_employment_income=50000,
            w2s=[],
        )
        hh = _household([p])
        gt = compute_ground_truth(hh)

        assert gt.filing_status == "single"
        se_tax = compute_se_tax(p)
        se_deduction = se_tax // 2
        assert gt.agi == 50000 - se_deduction
        # total_tax includes SE tax
        fed_tax = compute_federal_tax(gt.taxable_income, "single")
        assert gt.total_tax == fed_tax + se_tax

    def test_pattern5_itemizer(self):
        """Single filer who itemizes (high SALT + mortgage)."""
        p = _person(
            wage_income=100000,
            w2s=[_w2(federal_tax_withheld=15000)],
        )
        hh = _household(
            [p],
            state_income_tax=8000,
            property_taxes=6000,
            mortgage_interest=7000,
            charitable_contributions=2000,
        )
        gt = compute_ground_truth(hh)

        assert gt.filing_status == "single"
        assert gt.agi == 100000
        # SALT = min(14000, 10000) = 10000
        # itemized = 10000 + 7000 + 0 + 2000 = 19000 > 12950
        assert gt.deduction_type == "itemized"
        assert gt.itemized_deduction_total == 19000
        assert gt.taxable_income == 100000 - 19000

    def test_pattern6_hoh_with_dependent_parent(self):
        """Head of household with a qualifying relative (parent)."""
        p1 = _person(
            person_id="p1",
            wage_income=55000,
            w2s=[_w2(federal_tax_withheld=5500)],
        )
        parent = _person(
            person_id="pr1", relationship="parent",
            age=72, wage_income=3000,
        )
        hh = _household([p1, parent])
        gt = compute_ground_truth(hh)

        # No children → derive_filing_status gives "single" (stub)
        # Parent is qualifying relative
        assert gt.person_classifications["pr1"].dependency_type == "qualifying_relative"
        assert gt.agi == 55000 + 3000

    def test_ground_truth_round_trips(self):
        """Verify compute_ground_truth output round-trips through serialization."""
        p = _person(
            wage_income=45000,
            w2s=[_w2(federal_tax_withheld=4000)],
        )
        hh = _household([p])
        gt = compute_ground_truth(hh)
        d = gt.to_dict()
        rebuilt = GroundTruth.from_dict(d)

        assert rebuilt.schema_version == gt.schema_version
        assert rebuilt.filing_status == gt.filing_status
        assert rebuilt.agi == gt.agi
        assert rebuilt.taxable_income == gt.taxable_income
        assert rebuilt.total_tax == gt.total_tax
        assert rebuilt.refund_or_owed == gt.refund_or_owed
        assert rebuilt.deduction_type == gt.deduction_type
        assert rebuilt.credits_claimed == gt.credits_claimed
        assert len(rebuilt.person_classifications) == len(gt.person_classifications)

    def test_actc_refundable(self):
        """Low-income filer where CTC exceeds tax → ACTC kicks in."""
        p = _person(
            person_id="p1",
            wage_income=20000,
            w2s=[_w2(federal_tax_withheld=1000)],
        )
        c1 = _person(
            person_id="c1", relationship="biological_child", age=5,
        )
        hh = _household([p, c1])
        gt = compute_ground_truth(hh)

        assert gt.filing_status == "head_of_household"
        # With low income, tax < CTC → ACTC should be > 0
        assert gt.credits_claimed["actc"] > 0
        assert gt.credits_claimed["ctc"] <= gt.total_tax or gt.credits_claimed["ctc"] <= compute_federal_tax(gt.taxable_income, "head_of_household")
