from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    value: str
    kind: str
    line: int
    column: int
    start: int
    end: int


MULTI = (
    "<<=", ">>=", "...", "===", "!==", "->*", "::", "++", "--", "->",
    "&&", "||", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=",
    "&=", "|=", "^=", "<<", ">>", "##",
)


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    line = 1
    column = 1
    length = len(text)

    def advance(fragment: str) -> None:
        nonlocal line, column
        newlines = fragment.count("\n")
        if newlines:
            line += newlines
            column = len(fragment.rsplit("\n", 1)[-1]) + 1
        else:
            column += len(fragment)

    while index < length:
        start = index
        start_line = line
        start_column = column
        character = text[index]
        if character.isspace():
            index += 1
            while index < length and text[index].isspace():
                index += 1
            advance(text[start:index])
            continue
        if text.startswith("//", index):
            index = text.find("\n", index)
            if index < 0:
                break
            advance(text[start:index])
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = length if end < 0 else end + 2
            advance(text[start:index])
            continue
        if character in {'"', "'"} or (character == "@" and index + 1 < length and text[index + 1] == '"'):
            quote_index = index + 1 if character == "@" else index
            quote = text[quote_index]
            index = quote_index + 1
            escaped = False
            while index < length:
                current = text[index]
                index += 1
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == quote:
                    break
            fragment = text[start:index]
            tokens.append(Token(fragment, "string", start_line, start_column, start, index))
            advance(fragment)
            continue
        if character.isalpha() or character == "_":
            index += 1
            while index < length and (text[index].isalnum() or text[index] == "_"):
                index += 1
            fragment = text[start:index]
            tokens.append(Token(fragment, "identifier", start_line, start_column, start, index))
            advance(fragment)
            continue
        if character.isdigit():
            index += 1
            while index < length and (text[index].isalnum() or text[index] in "._"):
                index += 1
            fragment = text[start:index]
            tokens.append(Token(fragment, "number", start_line, start_column, start, index))
            advance(fragment)
            continue
        operator = next((value for value in MULTI if text.startswith(value, index)), character)
        index += len(operator)
        tokens.append(Token(operator, "operator", start_line, start_column, start, index))
        advance(operator)
    return tokens


import os
from pathlib import Path
from typing import Sequence

EXCLUDED_DIRS = {".git", ".hg", ".build", "build", "DerivedData", "Pods", "target", "vendor"}


def discover_files(root: Path, filters: Sequence[str] = ()) -> list[Path]:
    files: list[Path] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS and not name.lower().startswith("test"))
        for filename in sorted(filenames):
            if not filename.endswith((".m", ".mm")):
                continue
            path = Path(directory, filename)
            relative = path.relative_to(root).as_posix()
            if filters and not any(fragment in relative for fragment in filters):
                continue
            files.append(path)
    return files


import json
import subprocess
from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class Function:
    name: str
    file: str
    start_line: int
    end_line: int
    complexity: int


@dataclass(frozen=True)
class Metric:
    name: str
    file: str
    start_line: int
    end_line: int
    complexity: int
    coverage: float | None
    crap: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def score(complexity: int, coverage_percent: float | None) -> float | None:
    if coverage_percent is None:
        return None
    uncovered = 1.0 - coverage_percent / 100.0
    return complexity * complexity * uncovered**3 + complexity


def _matching_brace(tokens: list[Token], open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(tokens)):
        if tokens[index].value == "{":
            depth += 1
        elif tokens[index].value == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _implementation_at(tokens: list[Token], token_index: int) -> str | None:
    current: str | None = None
    for index in range(token_index):
        if tokens[index].value == "@" and index + 2 < len(tokens) and tokens[index + 1].value == "implementation":
            current = tokens[index + 2].value
        elif tokens[index].value == "@" and index + 1 < len(tokens) and tokens[index + 1].value == "end":
            current = None
    return current


def _method_name(tokens: list[Token], start: int, brace: int) -> str:
    selector: list[str] = []
    index = start + 1
    if index < brace and tokens[index].value == "(":
        depth = 1
        index += 1
        while index < brace and depth:
            depth += tokens[index].value == "("
            depth -= tokens[index].value == ")"
            index += 1
    while index < brace:
        if tokens[index].kind == "identifier":
            if index + 1 < brace and tokens[index + 1].value == ":":
                selector.append(tokens[index].value + ":")
            elif not selector:
                selector.append(tokens[index].value)
                break
        index += 1
    return "".join(selector) or f"<method@{tokens[start].line}>"


def _complexity(body: list[Token]) -> int:
    value = 1
    decision_words = {"if", "for", "while", "do", "catch", "case", "default"}
    for token in body:
        if token.value in decision_words or token.value in {"&&", "||", "?"}:
            value += 1
    return value


def extract_functions(path: Path, root: Path) -> list[Function]:
    text = path.read_text(encoding="utf-8")
    tokens = tokenize(text)
    functions: list[Function] = []
    claimed_braces: set[int] = set()

    for index, token in enumerate(tokens):
        if token.value not in {"-", "+"}:
            continue
        line_text = text.splitlines()[token.line - 1].lstrip() if token.line <= len(text.splitlines()) else ""
        if not (line_text.startswith("-") or line_text.startswith("+")):
            continue
        brace = next((cursor for cursor in range(index + 1, len(tokens)) if tokens[cursor].value in {"{", ";"}), None)
        if brace is None or tokens[brace].value != "{":
            continue
        end = _matching_brace(tokens, brace)
        if end is None:
            continue
        owner = _implementation_at(tokens, index)
        method = _method_name(tokens, index, brace)
        prefix = "+" if token.value == "+" else "-"
        name = f"{prefix}[{owner or '?'} {method}]"
        functions.append(Function(name, path.relative_to(root).as_posix(), token.line, tokens[end].line, _complexity(tokens[brace + 1 : end])))
        claimed_braces.add(brace)

    controls = {"if", "for", "while", "switch", "catch", "sizeof", "return"}
    for open_paren, token in enumerate(tokens):
        if token.value != "(":
            continue
        depth = 1
        close_paren = open_paren + 1
        while close_paren < len(tokens) and depth:
            depth += tokens[close_paren].value == "("
            depth -= tokens[close_paren].value == ")"
            close_paren += 1
        if depth or close_paren >= len(tokens) or tokens[close_paren].value != "{":
            continue
        brace = close_paren
        if brace in claimed_braces:
            continue
        name_token = tokens[open_paren - 1] if open_paren > 0 else None
        if not name_token or name_token.kind != "identifier" or name_token.value in controls:
            continue
        end = _matching_brace(tokens, brace)
        if end is None:
            continue
        functions.append(Function(name_token.value, path.relative_to(root).as_posix(), name_token.line, tokens[end].line, _complexity(tokens[brace + 1 : end])))
    functions.sort(key=lambda item: (item.start_line, item.name))
    return functions


def load_lcov(path: Path) -> dict[str, list[tuple[int, int]]]:
    current: str | None = None
    coverage: dict[str, list[tuple[int, int]]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("SF:"):
            current = raw[3:].replace("\\", "/").removeprefix("./")
            coverage.setdefault(current, [])
        elif raw.startswith("DA:") and current:
            line, count, *_ = raw[3:].split(",")
            coverage[current].append((int(line), int(count)))
    return coverage


def _points(coverage: dict[str, list[tuple[int, int]]], filename: str) -> list[tuple[int, int]] | None:
    normalized = filename.replace("\\", "/").removeprefix("./")
    if normalized in coverage:
        return coverage[normalized]
    matches = [value for key, value in coverage.items() if key.endswith("/" + normalized) or normalized.endswith("/" + key)]
    return matches[0] if len(matches) == 1 else None


def analyze(root: Path, coverage_path: Path | None, filters: Sequence[str] = ()) -> list[Metric]:
    coverage = load_lcov(coverage_path) if coverage_path and coverage_path.exists() else {}
    metrics: list[Metric] = []
    for path in discover_files(root, filters):
        for function in extract_functions(path, root):
            points = _points(coverage, function.file)
            percent: float | None = None
            if points is not None:
                relevant = [(line, count) for line, count in points if function.start_line <= line <= function.end_line]
                percent = 0.0 if not relevant else 100.0 * sum(count > 0 for _, count in relevant) / len(relevant)
            metrics.append(Metric(**asdict(function), coverage=percent, crap=score(function.complexity, percent)))
    metrics.sort(key=lambda item: (item.crap is None, -(item.crap or 0.0), item.name))
    return metrics


def run_test_command(command: str, root: Path) -> None:
    completed = subprocess.run(command, cwd=root, shell=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"test command failed with status {completed.returncode}")


def format_report(metrics: list[Metric]) -> str:
    header = f"{'Function':34} {'File':42} {'CC':>4} {'Cov%':>7} {'CRAP':>8}"
    lines = ["CRAP Report", "===========", header, "-" * len(header)]
    for metric in metrics:
        coverage = "N/A" if metric.coverage is None else f"{metric.coverage:.1f}%"
        crap = "N/A" if metric.crap is None else f"{metric.crap:.1f}"
        lines.append(f"{metric.name[:34]:34} {metric.file[:42]:42} {metric.complexity:4d} {coverage:>7} {crap:>8}")
    return "\n".join(lines) + "\n"
