"""Ground truth data models — the canonical answer key for a scenario.

GroundTruth is computed once at generation time and stored with the scenario.
The grader consumes it directly with zero domain logic. Three layers:

1. Return-level answers (filing status, AGI, taxable income, total tax, etc.)
2. Per-person classifications (role, dependency type, credit eligibility)
3. Predicate detail snapshots (structured results from rich-result predicates)

This module lives in tax_core because it is a pure data structure with no
upper-layer dependencies. The computation that *fills* GroundTruth will live
in tax_core/computation.py (Restructure B Phase 2).
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


SCHEMA_VERSION = 1


@dataclass
class PersonClassification:
    """Classification of one person's role on the tax return.

    Args:
        person_id: Unique identifier matching Person.person_id.
        role: "primary", "spouse", or "dependent".
        dependency_type: "qualifying_child", "qualifying_relative", or "none".
        credit_eligibility: Flags for which credits this person generates.
    """
    person_id: str = ""
    role: str = ""  # "primary", "spouse", "dependent"
    dependency_type: str = "none"  # "qualifying_child", "qualifying_relative", "none"
    credit_eligibility: Dict[str, bool] = field(default_factory=dict)
    # e.g. {"ctc": True, "actc": False, "eitc_qualifying_child": True}

    def to_dict(self) -> dict:
        return {
            "person_id": self.person_id,
            "role": self.role,
            "dependency_type": self.dependency_type,
            "credit_eligibility": dict(self.credit_eligibility),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PersonClassification":
        return cls(
            person_id=data.get("person_id", ""),
            role=data.get("role", ""),
            dependency_type=data.get("dependency_type", "none"),
            credit_eligibility=dict(data.get("credit_eligibility", {})),
        )


@dataclass
class GroundTruth:
    """Canonical answer key for a generated scenario.

    Populated by compute_ground_truth() in Restructure B Phase 2.
    The grader reads from this directly — no recomputation, no fallback.

    schema_version is checked on load; mismatches are refused so that
    predicate changes don't silently grade against stale truth.
    """
    schema_version: int = SCHEMA_VERSION
    tax_year: int = 2022

    # Return-level answers
    filing_status: str = ""  # FilingStatus enum value as string
    agi: int = 0
    taxable_income: int = 0
    total_tax: int = 0
    refund_or_owed: int = 0
    deduction_type: str = "standard"  # "standard" or "itemized"
    standard_deduction: int = 0
    itemized_deduction_total: int = 0
    credits_claimed: Dict[str, int] = field(default_factory=dict)
    # e.g. {"ctc": 2000, "eitc": 0, "actc": 1500}

    # Per-person classifications
    person_classifications: Dict[str, PersonClassification] = field(
        default_factory=dict,
    )  # keyed by person_id

    # Predicate detail snapshots — keyed by predicate name, values are
    # the structured result dicts from rich-result predicates.
    predicate_results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "tax_year": self.tax_year,
            "filing_status": self.filing_status,
            "agi": self.agi,
            "taxable_income": self.taxable_income,
            "total_tax": self.total_tax,
            "refund_or_owed": self.refund_or_owed,
            "deduction_type": self.deduction_type,
            "standard_deduction": self.standard_deduction,
            "itemized_deduction_total": self.itemized_deduction_total,
            "credits_claimed": dict(self.credits_claimed),
            "person_classifications": {
                pid: pc.to_dict()
                for pid, pc in self.person_classifications.items()
            },
            "predicate_results": self.predicate_results,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GroundTruth":
        version = data.get("schema_version", 0)
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"GroundTruth schema version mismatch: "
                f"expected {SCHEMA_VERSION}, got {version}"
            )
        classifications = {}
        for pid, pc_data in data.get("person_classifications", {}).items():
            classifications[pid] = PersonClassification.from_dict(pc_data)

        return cls(
            schema_version=version,
            tax_year=data.get("tax_year", 2022),
            filing_status=data.get("filing_status", ""),
            agi=data.get("agi", 0),
            taxable_income=data.get("taxable_income", 0),
            total_tax=data.get("total_tax", 0),
            refund_or_owed=data.get("refund_or_owed", 0),
            deduction_type=data.get("deduction_type", "standard"),
            standard_deduction=data.get("standard_deduction", 0),
            itemized_deduction_total=data.get("itemized_deduction_total", 0),
            credits_claimed=dict(data.get("credits_claimed", {})),
            person_classifications=classifications,
            predicate_results=data.get("predicate_results", {}),
        )
