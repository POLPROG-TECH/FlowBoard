"""Tests for the CLI commands (using Typer's test runner)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from flowboard.cli.main import app

runner = CliRunner()


class TestCliDemo:
    def test_demo_generates_html(self, tmp_path: Path) -> None:
        output = tmp_path / "demo.html"
        result = runner.invoke(app, ["demo", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert output.exists()
        content = output.read_text()
        assert "<!DOCTYPE html>" in content

    def test_demo_default_output(self) -> None:
        result = runner.invoke(app, ["demo"])
        assert result.exit_code == 0, result.output
        default = Path("output/demo_dashboard.html")
        if default.exists():
            default.unlink()


class TestCliValidateConfig:
    def test_validate_example_config(self) -> None:
        example = Path(__file__).parent.parent / "examples" / "config.example.json"
        result = runner.invoke(app, ["validate-config", "--config", str(example)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_missing_file(self) -> None:
        result = runner.invoke(app, ["validate-config", "--config", "/nonexistent.json"])
        assert result.exit_code == 1


class TestCliVersion:
    def test_version_prints(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output
