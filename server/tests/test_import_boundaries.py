"""Tests for architectural layer boundaries using import-linter per docs/02 §4.1."""

from pathlib import Path

from click.testing import CliRunner
from importlinter.cli import lint_imports_command

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SERVER_DIR = REPO_ROOT / "server"


def test_import_boundaries_conform_to_architecture() -> None:
    """Verify that the codebase satisfies all architectural boundary contracts."""
    runner = CliRunner()
    result = runner.invoke(
        lint_imports_command, ["--config", str(SERVER_DIR / ".importlinter"), "--no-cache"]
    )
    assert result.exit_code == 0, f"Import boundary checks failed:\n{result.output}"
    assert "Contracts: 7 kept, 0 broken" in result.output


def test_import_boundary_detects_deliberate_violation(tmp_path: Path) -> None:
    """Verify that import-linter fails when a deliberate boundary violation is introduced.

    docs/02 §4.1: 'analysis/ never imports llm/ (analysis is deterministic)'
    """
    pkg_dir = tmp_path / "synthetic_app"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    analysis_dir = pkg_dir / "analysis"
    analysis_dir.mkdir()
    (analysis_dir / "__init__.py").write_text("", encoding="utf-8")
    # Deliberate violation: analysis imports llm
    (analysis_dir / "scanner.py").write_text("import synthetic_app.llm\n", encoding="utf-8")

    llm_dir = pkg_dir / "llm"
    llm_dir.mkdir()
    (llm_dir / "__init__.py").write_text("", encoding="utf-8")

    config_file = tmp_path / ".importlinter"
    config_file.write_text(
        """[importlinter]
root_package = synthetic_app

[importlinter:contract:analysis-no-llm]
name = Analysis cannot import LLM
type = forbidden
source_modules =
    synthetic_app.analysis
forbidden_modules =
    synthetic_app.llm
""",
        encoding="utf-8",
    )

    import sys

    sys.path.insert(0, str(tmp_path))
    try:
        runner = CliRunner()
        result = runner.invoke(lint_imports_command, ["--config", str(config_file), "--no-cache"])
        assert result.exit_code != 0, "import-linter must fail on deliberate boundary violation"
        assert "BROKEN" in result.output
    finally:
        sys.path.remove(str(tmp_path))
