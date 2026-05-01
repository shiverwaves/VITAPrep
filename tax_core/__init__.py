"""tax_core — pure tax-law rules engine.

No UI, no narrative, no curriculum logic. Encodes tax-law predicates,
threshold lookups, classification tests, and computation routines.

This module has no dependencies on intake/, learn/, generator/, training/,
or api/. That constraint is enforced by tests/test_import_graph.py.
"""
