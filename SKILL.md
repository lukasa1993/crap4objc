# crap4objc

Use `crap4objc` for CRAP verification of Objective-C projects.

1. Run `crap4objc --help` before first use.
2. Use the project test/build commands that create current coverage or execute the full unit suite.
3. Run the gate with `--fail-over 6`.
4. Treat exit `1` as an infrastructure or configuration failure. Do not report it as a quality pass.
5. Treat exit `2` as a quality-gate failure.
