"""Erzeugt die maschinelle Referenz der Codebasis direkt aus dem Quelltext.

- docs/API-REFERENZ.md: jedes Modul unter collector/src/pokercollector mit Zweck (erster Absatz des Docstrings),
  Konstanten, Klassen, Methoden und Funktionen samt Signatur, erster Docstring-Zeile und Zeilennummer (per ast,
  der Code wird dafuer nicht ausgefuehrt).
- docs/CLI-REFERENZ.md: die Hilfe jedes Befehls und Unterbefehls von `pokercollector` (aus dem argparse-Parser).

Aufruf aus dem Repo-Wurzelordner:
    uv run --no-sync --project collector python scripts/gen_reference.py [AUSGABEORDNER]
Ohne Argument wird nach docs/ geschrieben. Fuer die CLI-Referenz muss das Paket importierbar sein.
"""
from __future__ import annotations

import argparse
import ast
import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path


def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "collector" / "src" / "pokercollector").is_dir():
            return p
    raise SystemExit("collector/src/pokercollector nicht gefunden")


def first_paragraph(doc: str | None) -> str:
    if not doc:
        return ""
    return " ".join(doc.strip().split("\n\n")[0].split())


def first_line(doc: str | None) -> str:
    if not doc:
        return ""
    return doc.strip().splitlines()[0].strip()


def short(text: str, n: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = ast.unparse(node.args)
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{node.name}({args}){ret}"


def is_const_name(name: str) -> bool:
    return name.isupper() or (name.startswith("_") and name[1:].isupper())


def module_section(path: Path, src_root: Path) -> list[str]:
    rel = path.relative_to(src_root).as_posix()
    mod = rel[:-3].replace("/", ".")
    if mod.endswith(".__init__"):
        mod = mod[: -len(".__init__")]
    text = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(text)
    lines = text.count("\n") + 1
    out = [f"### `{mod}`", "", f"Datei `collector/src/{rel}` · {lines} Zeilen", ""]
    doc = first_paragraph(ast.get_docstring(tree))
    if doc:
        out += [doc, ""]

    consts, funcs, classes, private = [], [], [], []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name) and is_const_name(t.id) and node.value is not None:
                    consts.append((t.id, short(ast.unparse(node.value), 70), node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            (private if node.name.startswith("_") else funcs).append(node)
        elif isinstance(node, ast.ClassDef):
            classes.append(node)

    if consts:
        out += ["**Konstanten**", "", "| Name | Wert | Zeile |", "| --- | --- | --- |"]
        for name, val, ln in consts:
            out.append(f"| `{name}` | `{val.replace('|', '¦')}` | {ln} |")
        out.append("")
    for cls in classes:
        bases = ", ".join(ast.unparse(b) for b in cls.bases)
        out.append(f"**Klasse `{cls.name}`**" + (f" ({bases})" if bases else "") + f" · Zeile {cls.lineno}")
        cdoc = first_paragraph(ast.get_docstring(cls))
        if cdoc:
            out.append(f": {short(cdoc, 300)}")
        out.append("")
        methods = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        pub = [m for m in methods if not m.name.startswith("_") or m.name in ("__init__", "__call__")]
        priv = [m.name for m in methods if m not in pub]
        for m in pub:
            d = first_line(ast.get_docstring(m))
            out.append(f"- `{short(signature(m), 160)}` · Z. {m.lineno}" + (f": {short(d, 200)}" if d else ""))
        if priv:
            out.append(f"- interne Methoden: {', '.join(f'`{p}`' for p in priv)}")
        out.append("")
    if funcs:
        out += ["**Funktionen**", ""]
        for f in funcs:
            d = first_line(ast.get_docstring(f))
            out.append(f"- `{short(signature(f), 160)}` · Z. {f.lineno}" + (f": {short(d, 200)}" if d else ""))
        out.append("")
    if private:
        out += [f"Interne Helfer: {', '.join(f'`{p.name}`' for p in private)}", ""]
    return out


def api_reference(root: Path) -> str:
    src_root = root / "collector" / "src"
    files = sorted(p for p in (src_root / "pokercollector").rglob("*.py") if "__pycache__" not in p.parts)
    total = sum(p.read_text(encoding="utf-8-sig").count("\n") + 1 for p in files)
    out = ["# API-Referenz", "",
           f"Automatisch erzeugt aus dem Quelltext (`scripts/gen_reference.py`): {len(files)} Module, {total} Zeilen. "
           "Pro Modul: Zweck, Konstanten, Klassen mit Methoden, Funktionen mit Signatur und erster Docstring-Zeile. "
           "Die Erklaerung der Zusammenhaenge steht in `TECHNISCHE-DOKUMENTATION.md`.", ""]
    groups: dict[str, list[Path]] = {}
    for p in files:
        key = "pokercollector.ai (KI: Engine, Bots, Training, Suche, Wertnetze)" if "ai" in p.relative_to(
            src_root / "pokercollector").parts[:-1] else "pokercollector (Erfassung, Rekonstruktion, Bedienung)"
        groups.setdefault(key, []).append(p)
    out += ["## Inhalt", ""]
    for key, ps in groups.items():
        out.append(f"- {key}: " + ", ".join(f"`{p.stem}`" for p in ps))
    out.append("")
    for key, ps in groups.items():
        out += [f"## {key}", ""]
        for p in ps:
            out += module_section(p, src_root)
    return "\n".join(out).rstrip() + "\n"


def cli_reference() -> str:
    from pokercollector import cli
    captured: dict[str, argparse.ArgumentParser] = {}
    orig = argparse.ArgumentParser.parse_args

    def grab(self, args=None, namespace=None):
        captured.setdefault("p", self)
        raise SystemExit(0)

    argparse.ArgumentParser.parse_args = grab
    os.environ["COLUMNS"] = "110"
    try:
        with redirect_stdout(io.StringIO()):
            cli.main([])
    except SystemExit:
        pass
    finally:
        argparse.ArgumentParser.parse_args = orig
    if "p" not in captured:
        raise SystemExit("argparse-Parser von pokercollector.cli nicht gefunden")

    out = ["# CLI-Referenz", "",
           "Automatisch erzeugt aus dem argparse-Parser von `pokercollector` (`scripts/gen_reference.py`). "
           "Aufruf unter Windows mit `pc.cmd <befehl> ...`, unter Linux/macOS mit `./pc.sh <befehl> ...`.", ""]
    seen: set[int] = set()
    entries: list[tuple[list[str], argparse.ArgumentParser]] = []

    def walk(parser: argparse.ArgumentParser, path: list[str]) -> None:
        if id(parser) in seen:
            return
        seen.add(id(parser))
        entries.append((path, parser))
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sp in action.choices.items():
                    walk(sp, path + [name])

    walk(captured["p"], ["pokercollector"])
    out += ["## Befehlsuebersicht", ""]
    for path, _ in entries[1:]:
        out.append("  " * (len(path) - 2) + f"- `{' '.join(path[1:])}`")
    out.append("")
    for path, parser in entries:
        level = "##" if len(path) <= 2 else "###"
        out += [f"{level} `{' '.join(path)}`", "", "```text", parser.format_help().rstrip(), "```", ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    root = find_root(Path(__file__).resolve().parent)
    args = argv if argv is not None else sys.argv[1:]
    out_dir = Path(args[0]) if args else root / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    api = api_reference(root)
    (out_dir / "API-REFERENZ.md").write_text(api, encoding="utf-8")
    print(f"API-REFERENZ.md: {api.count(chr(10))} Zeilen")
    try:
        cli_text = cli_reference()
    except Exception as exc:  # die API-Referenz soll auch ohne importierbares Paket entstehen
        print(f"CLI-Referenz uebersprungen: {exc!r}")
        return 1
    (out_dir / "CLI-REFERENZ.md").write_text(cli_text, encoding="utf-8")
    print(f"CLI-REFERENZ.md: {cli_text.count(chr(10))} Zeilen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
