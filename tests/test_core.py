from pathlib import Path

from crap4objc.core import analyze, extract_functions, score


def test_extracts_c_function_and_objc_method(tmp_path: Path) -> None:
    source = tmp_path / "sample.m"
    source.write_text("""@implementation Widget
- (int)run:(BOOL)a other:(BOOL)b {
  if (a && b) { return 1; }
  return 0;
}
@end

int choose(int x) {
  while (x > 0) { x--; }
  return x;
}
""", encoding="utf-8")
    functions = extract_functions(source, tmp_path)
    assert {item.name for item in functions} == {"-[Widget run:other:]", "choose"}
    method = next(item for item in functions if "Widget" in item.name)
    assert method.complexity == 3


def test_maps_lcov(tmp_path: Path) -> None:
    source = tmp_path / "sample.m"
    source.write_text("int choose(int x) {\n if (x) return 1;\n return 0;\n}\n", encoding="utf-8")
    coverage = tmp_path / "lcov.info"
    coverage.write_text(f"SF:{source}\nDA:2,1\nDA:3,0\nend_of_record\n", encoding="utf-8")
    metric = analyze(tmp_path, coverage)[0]
    assert metric.coverage == 50
    assert metric.crap == score(2, 50)
