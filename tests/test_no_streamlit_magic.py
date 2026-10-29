"""Schutztest gegen Streamlit-„Magic“ in app.py.

Streamlit verpackt jede alleinstehende Ausdrucks-Zeile des Hauptskripts in st.write(...) – auch in
Funktionen und with-Blöcken. Ausgenommen sind nur Funktionsaufrufe, Docstrings, yield und await.
Ein ternärer Ausdruck wie `a() if x else st.info(...)` ist KEIN Funktionsaufruf und landet deshalb
ungewollt auf der Seite (Hilfe-Box „DeltaGenerator(…)“ bzw. ein „None“).

Geprüft wird nur app.py, denn Magic schreibt nur das Skript um, das Streamlit direkt ausführt.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app.py"

# Knoten, in deren Rumpf ein String an erster Stelle ein Docstring ist.
DOCSTRING_OWNERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
# Ausdrücke, die Streamlit nicht anzeigt.
ALLOWED_EXPRESSIONS = (ast.Call, ast.Await, ast.Yield, ast.YieldFrom)
# Felder, in denen Anweisungslisten stehen (Rumpf, else, finally, …).
STATEMENT_FIELDS = ("body", "orelse", "finalbody")


def magic_expressions(source: str) -> list[tuple[int, str]]:
    """Alle alleinstehenden Ausdrücke, die Streamlit-Magic auf die Seite schreiben würde: (Zeile, Code)."""
    tree = ast.parse(source)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        for field in STATEMENT_FIELDS:
            statements = getattr(node, field, None)
            if not isinstance(statements, list):
                continue
            for index, statement in enumerate(statements):
                if not isinstance(statement, ast.Expr):
                    continue  # z. B. pass, Zuweisungen, if/with – keine Ausdrucks-Zeilen
                value = statement.value
                if isinstance(value, ALLOWED_EXPRESSIONS):
                    continue
                is_docstring = (
                    field == "body"
                    and index == 0
                    and isinstance(node, DOCSTRING_OWNERS)
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                )
                if is_docstring:
                    continue
                found.append((statement.lineno, ast.get_source_segment(source, statement) or ""))
    return sorted(found)


def test_app_has_no_magic_expressions() -> None:
    found = magic_expressions(APP.read_text(encoding="utf-8"))
    assert found == [], "Alleinstehende Ausdrücke in app.py würden per Streamlit-Magic angezeigt:\n" + "\n".join(
        f"  Zeile {line}: {code}" for line, code in found
    )


def test_detector_flags_problem_cases() -> None:
    source = '''
def main():
    render() if view else st.info("x")
    with tab:
        a if b else c
    "kein Docstring, weil nicht an erster Stelle"
    view
'''
    assert [line for line, _ in magic_expressions(source)] == [3, 5, 6, 7]


def test_detector_allows_calls_docstrings_and_pass() -> None:
    source = '''"""Modul-Docstring."""

def main():
    """Funktions-Docstring."""
    st.title("x")
    pass
    if view:
        render(view)
    else:
        st.info("leer")

class Foo:
    """Klassen-Docstring."""
    pass

main()
'''
    assert magic_expressions(source) == []
