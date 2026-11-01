"""gen_codemap.py — write layer B of docs/CODEMAP.md from the code itself (rule #15).

    python tools/gen_codemap.py            # rewrite layer B in place
    python tools/gen_codemap.py --check    # write nothing; exit 1 if layer B is stale

Why a repo-local copy instead of the house generator
(`Documents/Claude/Projects/Nick/tools/gen_codemap.py`): that one maps only a
`features/` folder (rule #14), and HPO predates it. Its code lives in main.py,
core/, ui/, installer/, tools/ and scripts/, so the house generator would write
"no features folder" between the markers and empty the map. A gate that reads a
path outside the repo also cannot run in a cloud checkout (#22). The markers and
the bullet format are the house generator's; each file line adds the module's
own first docstring line.

Only the text between the two markers is written. Layer A, the hand-written
table above them, is never touched. `publish_release.py` refuses a release
while `--check` would fail, so the map cannot ship stale.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEMAP = Path("docs") / "CODEMAP.md"
AUTO_START = "<!-- CODEMAP:AUTO:START -->"
AUTO_END = "<!-- CODEMAP:AUTO:END -->"
COMMAND = "python tools/gen_codemap.py"

# (heading, paths) in reading order; a folder means its own *.py files, not
# its subfolders, so ui/ and ui/dialogs/ get a heading each
SECTIONS = (
    ("main.py — the window", ("main.py",)),
    ("core/ — logic, no UI", ("core",)),
    ("ui/ — widgets", ("ui",)),
    ("ui/dialogs/ — dialogs", ("ui/dialogs",)),
    ("installer/ — the setup program", ("installer",)),
    ("tools/ — release and commit tooling", ("tools",)),
    ("scripts/ — one-off maintenance scripts", ("scripts",)),
)


class CodemapError(Exception):
    """docs/CODEMAP.md is missing, or its markers are not exactly one pair."""


def first_doc_line(node) -> str:
    """The first line of a node's docstring, or "" when it has none."""
    doc = ast.get_docstring(node)
    return doc.strip().splitlines()[0].strip() if doc else ""


def signature(node) -> str:
    """Name plus argument names, without types or defaults."""
    a = node.args
    names = [x.arg for x in a.posonlyargs + a.args]
    if a.vararg:
        names.append("*" + a.vararg.arg)
    names += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        names.append("**" + a.kwarg.arg)
    return f"{node.name}({', '.join(names)})"


def scan_file(path: Path, root: Path) -> list[str]:
    """Markdown lines for one module: its path and summary, then its public names."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel = path.relative_to(root).as_posix()
    summary = first_doc_line(tree)
    out = [f"- `{rel}`" + (f" — {summary}" if summary else "")]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            doc = first_doc_line(node)
            out.append(f"    • `{signature(node)}`" + (f" — {doc}" if doc else ""))
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            doc = first_doc_line(node)
            out.append(f"    • `class {node.name}`" + (f" — {doc}" if doc else ""))
            methods = [m.name for m in node.body
                       if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and not m.name.startswith("_")]
            if methods:
                out.append(f"        ↳ {', '.join(methods)}")
    return out


def files_of(root: Path, rel: str) -> list[Path]:
    """The .py files a section covers, sorted; __init__.py is skipped."""
    p = root / rel
    if p.is_file():
        return [p]
    return sorted((f for f in p.glob("*.py") if f.name != "__init__.py"),
                  key=lambda f: f.name)


def build_auto(root: Path) -> str:
    """Layer B: every section's modules and their public functions and classes."""
    out: list[str] = []
    for heading, rels in SECTIONS:
        files = [f for rel in rels for f in files_of(root, rel)]
        if not files:
            continue
        out.append(f"### {heading}")
        for f in files:
            out.extend(scan_file(f, root))
        out.append("")
    return "\n".join(out).rstrip()


def render(root: Path = ROOT) -> tuple[str, str]:
    """(current text, text with layer B regenerated); LF line ends in both."""
    path = root / CODEMAP
    if not path.is_file():
        raise CodemapError(f"{CODEMAP.as_posix()} is missing")
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(AUTO_START) != 1 or text.count(AUTO_END) != 1:
        raise CodemapError(f"{CODEMAP.as_posix()} needs exactly one "
                           f"{AUTO_START} and one {AUTO_END}")
    block = f"{AUTO_START}\n{build_auto(root)}\n{AUTO_END}"
    new = re.sub(re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END),
                 lambda _m: block, text, flags=re.S)
    return text, new


def is_fresh(root: Path = ROOT) -> bool:
    """True when layer B already matches the code."""
    text, new = render(root)
    return text == new


def main(argv: list[str] | None = None) -> int:
    """Rewrite layer B, or with --check only report whether it is stale."""
    args = sys.argv[1:] if argv is None else argv
    try:
        text, new = render(ROOT)
    except CodemapError as e:
        print(f"[gen_codemap] {e}")
        return 1
    if "--check" in args:
        if text == new:
            print("[gen_codemap] docs/CODEMAP.md is up to date")
            return 0
        print(f"[gen_codemap] docs/CODEMAP.md is stale - run: {COMMAND}")
        return 1
    if text != new:
        (ROOT / CODEMAP).write_text(new, encoding="utf-8", newline="\n")
        print("[gen_codemap] updated docs/CODEMAP.md")
    else:
        print("[gen_codemap] docs/CODEMAP.md is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
