# crap4objc

`crap4objc` calculates CRAP scores for Objective-C methods and C/C++ functions in `.m` and `.mm` files. It uses a dependency-free lexer and LCOV line coverage.

## Install

```bash
pipx install git+https://github.com/lukasa1993/crap4objc.git
```

## Run

```bash
crap4objc --test-command "make coverage" --coverage target/coverage/lcov.info --fail-over 6
```

Use `--no-test` to read an existing LCOV report. Use `--json` for machine-readable output.

Complexity starts at `1` and counts branch keywords, switch clauses, conditional operators, and `&&`/`||`.

## Development

```bash
python -m pip install -e . pytest
pytest -q
```
