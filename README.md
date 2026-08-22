# crap4objc

`crap4objc` calculates function-level CRAP scores for Objective-C source with a Tree-sitter syntax tree and executable-line coverage. Missing coverage is an error by default.

```bash
pipx install git+https://github.com/lukasa1993/crap4objc.git
crap4objc --fail-over 6
```

Supported coverage inputs: LCOV, Cobertura XML, coverage.py JSON, Istanbul JSON, and LLVM export JSON. Use `--no-test` to analyze an existing report. Use `--allow-missing-coverage` only for exploratory work.

Exit status: `0` pass, `1` configuration/execution/coverage error, `2` quality limit failure.

## Development

```bash
python -m pip install -e . pytest
pytest -q
```
