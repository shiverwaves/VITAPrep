"""Tests for tax_core.ground_truth data models.

Round-trip serialization: to_dict → JSON → from_dict → assert equal.
Also tests schema_version enforcement on deserialization.
"""

import json

import pytest

from tax_core.ground_truth import (
    SCHEMA_VERSION,
    GroundTruth,
    PersonClassification,
)


# ── PersonClassification ─────────────────────────────────────────────

class TestPersonClassification:
    def test_round_trip_primary(self):
        pc = PersonClassification(
            person_id="p1",
            role="primary",
            dependency_type="none",
            credit_eligibility={"ctc": False, "eitc_qualifying_child": False},
        )
        d = pc.to_dict()
        rebuilt = PersonClassification.from_dict(d)
        assert rebuilt.person_id == pc.person_id
        assert rebuilt.role == pc.role
        assert rebuilt.dependency_type == pc.dependency_type
        assert rebuilt.credit_eligibility == pc.credit_eligibility

    def test_round_trip_dependent(self):
        pc = PersonClassification(
            person_id="p3",
            role="dependent",
            dependency_type="qualifying_child",
            credit_eligibility={
                "ctc": True,
                "actc": False,
                "eitc_qualifying_child": True,
            },
        )
        d = pc.to_dict()
        json_str = json.dumps(d)
        rebuilt = PersonClassification.from_dict(json.loads(json_str))
        assert rebuilt.person_id == "p3"
        assert rebuilt.role == "dependent"
        assert rebuilt.dependency_type == "qualifying_child"
        assert rebuilt.credit_eligibility["ctc"] is True
        assert rebuilt.credit_eligibility["eitc_qualifying_child"] is True

    def test_round_trip_spouse(self):
        pc = PersonClassification(
            person_id="p2",
            role="spouse",
            dependency_type="none",
            credit_eligibility={},
        )
        rebuilt = PersonClassification.from_dict(pc.to_dict())
        assert rebuilt.role == "spouse"
        assert rebuilt.dependency_type == "none"

    def test_defaults(self):
        pc = PersonClassification()
        assert pc.person_id == ""
        assert pc.role == ""
        assert pc.dependency_type == "none"
        assert pc.credit_eligibility == {}

    def test_from_dict_missing_keys(self):
        rebuilt = PersonClassification.from_dict({})
        assert rebuilt.person_id == ""
        assert rebuilt.dependency_type == "none"
        assert rebuilt.credit_eligibility == {}


# ── GroundTruth ───────────────────────────────────────────────────────

class TestGroundTruth:
    def _full_ground_truth(self) -> GroundTruth:
        return GroundTruth(
            schema_version=SCHEMA_VERSION,
            tax_year=2022,
            filing_status="married_filing_jointly",
            agi=85000,
            taxable_income=59100,
            total_tax=6732,
            refund_or_owed=1268,
            deduction_type="standard",
            standard_deduction=25900,
            itemized_deduction_total=18000,
            credits_claimed={"ctc": 4000, "eitc": 0, "actc": 0},
            person_classifications={
                "p1": PersonClassification(
                    person_id="p1",
                    role="primary",
                    dependency_type="none",
                    credit_eligibility={"ctc": False},
                ),
                "p2": PersonClassification(
                    person_id="p2",
                    role="spouse",
                    dependency_type="none",
                    credit_eligibility={"ctc": False},
                ),
                "p3": PersonClassification(
                    person_id="p3",
                    role="dependent",
                    dependency_type="qualifying_child",
                    credit_eligibility={"ctc": True, "eitc_qualifying_child": True},
                ),
                "p4": PersonClassification(
                    person_id="p4",
                    role="dependent",
                    dependency_type="qualifying_child",
                    credit_eligibility={"ctc": True, "eitc_qualifying_child": True},
                ),
            },
            predicate_results={
                "qualifying_child_residency_test_p3": {
                    "passed": True,
                    "months_in_home": 12,
                    "required_months": 7,
                },
                "qualifying_child_residency_test_p4": {
                    "passed": True,
                    "months_in_home": 10,
                    "required_months": 7,
                },
            },
        )

    def test_round_trip_full(self):
        gt = self._full_ground_truth()
        d = gt.to_dict()
        json_str = json.dumps(d)
        rebuilt = GroundTruth.from_dict(json.loads(json_str))

        assert rebuilt.schema_version == SCHEMA_VERSION
        assert rebuilt.tax_year == 2022
        assert rebuilt.filing_status == "married_filing_jointly"
        assert rebuilt.agi == 85000
        assert rebuilt.taxable_income == 59100
        assert rebuilt.total_tax == 6732
        assert rebuilt.refund_or_owed == 1268
        assert rebuilt.deduction_type == "standard"
        assert rebuilt.standard_deduction == 25900
        assert rebuilt.itemized_deduction_total == 18000
        assert rebuilt.credits_claimed == {"ctc": 4000, "eitc": 0, "actc": 0}

    def test_round_trip_person_classifications(self):
        gt = self._full_ground_truth()
        rebuilt = GroundTruth.from_dict(gt.to_dict())

        assert len(rebuilt.person_classifications) == 4
        assert rebuilt.person_classifications["p1"].role == "primary"
        assert rebuilt.person_classifications["p3"].dependency_type == "qualifying_child"
        assert rebuilt.person_classifications["p3"].credit_eligibility["ctc"] is True

    def test_round_trip_predicate_results(self):
        gt = self._full_ground_truth()
        rebuilt = GroundTruth.from_dict(gt.to_dict())

        assert len(rebuilt.predicate_results) == 2
        p3_res = rebuilt.predicate_results["qualifying_child_residency_test_p3"]
        assert p3_res["passed"] is True
        assert p3_res["months_in_home"] == 12

    def test_schema_version_mismatch_raises(self):
        gt = self._full_ground_truth()
        d = gt.to_dict()
        d["schema_version"] = 999
        with pytest.raises(ValueError, match="schema version mismatch"):
            GroundTruth.from_dict(d)

    def test_schema_version_missing_raises(self):
        d = {"tax_year": 2022, "filing_status": "single"}
        with pytest.raises(ValueError, match="schema version mismatch"):
            GroundTruth.from_dict(d)

    def test_defaults(self):
        gt = GroundTruth()
        assert gt.schema_version == SCHEMA_VERSION
        assert gt.tax_year == 2022
        assert gt.filing_status == ""
        assert gt.agi == 0
        assert gt.credits_claimed == {}
        assert gt.person_classifications == {}
        assert gt.predicate_results == {}

    def test_round_trip_empty_collections(self):
        gt = GroundTruth(
            filing_status="single",
            agi=15000,
            taxable_income=2050,
            total_tax=205,
            refund_or_owed=-205,
            credits_claimed={},
            person_classifications={
                "p1": PersonClassification(
                    person_id="p1", role="primary",
                ),
            },
            predicate_results={},
        )
        rebuilt = GroundTruth.from_dict(gt.to_dict())
        assert rebuilt.credits_claimed == {}
        assert rebuilt.predicate_results == {}
        assert len(rebuilt.person_classifications) == 1

    def test_to_dict_contains_schema_version(self):
        gt = GroundTruth()
        d = gt.to_dict()
        assert "schema_version" in d
        assert d["schema_version"] == SCHEMA_VERSION

    def test_itemized_deduction_scenario(self):
        gt = GroundTruth(
            filing_status="single",
            agi=100000,
            taxable_income=85000,
            deduction_type="itemized",
            standard_deduction=12950,
            itemized_deduction_total=15000,
        )
        rebuilt = GroundTruth.from_dict(gt.to_dict())
        assert rebuilt.deduction_type == "itemized"
        assert rebuilt.itemized_deduction_total == 15000
