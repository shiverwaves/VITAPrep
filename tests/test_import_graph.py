"""Enforce the architectural boundary: tax_core must not import from upper layers.

tax_core is a pure rules engine with no dependencies on generator, training,
intake, learn, or api. This test uses ast.parse to catch all import forms
(import X, from X import Y, relative imports) rather than grep, which would
miss aliased or conditional imports.
"""

import ast
from pathlib import Path

FORBIDDEN_PREFIXES = ("generator", "training", "api", "intake", "learn")

TAX_CORE_ROOT = Path(__file__).resolve().parent.parent / "tax_core"


def _collect_imported_modules(filepath: Path) -> list[tuple[str, int]]:
    """Return (module_name, line_number) for every import in a Python file."""
    source = filepath.read_text()
    tree = ast.parse(source, filename=str(filepath))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.module, node.lineno))
    return imports


def test_tax_core_does_not_import_upper_layers():
    """tax_core/ must not import from generator/, training/, api/, intake/, or learn/."""
    if not TAX_CORE_ROOT.exists():
        return

    violations = []
    for pyfile in TAX_CORE_ROOT.rglob("*.py"):
        for module_name, lineno in _collect_imported_modules(pyfile):
            top_level = module_name.split(".")[0]
            if top_level in FORBIDDEN_PREFIXES:
                rel = pyfile.relative_to(TAX_CORE_ROOT.parent)
                violations.append(f"  {rel}:{lineno} imports '{module_name}'")

    assert not violations, (
        "tax_core must not import from upper layers:\n" + "\n".join(violations)
    )
