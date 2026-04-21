"""Tests for the CLI commands (using Typer's test runner)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from flowboard.cli.main import app

runner = CliRunner()


class TestCliDemo:
    """GIVEN cli demo and the scenario: demo generates html"""
    def test_demo_generates_html(self, tmp_path: Path) -> None:
        """WHEN the code under test is exercised for: demo generates html"""
        output = tmp_path / "demo.html"
        result = runner.invoke(app, ["demo", "--output", str(output)])

        """THEN the expected behaviour holds: demo generates html"""
        assert result.exit_code == 0, result.output
        assert output.exists()
        content = output.read_text()
        assert "<!DOCTYPE html>" in content

    """GIVEN cli demo and the scenario: demo default output"""
    def test_demo_default_output(self) -> None:
        """WHEN the code under test is exercised for: demo default output"""
        result = runner.invoke(app, ["demo"])

        """THEN the expected behaviour holds: demo default output"""
        assert result.exit_code == 0, result.output
        default = Path("output/demo_dashboard.html")
        if default.exists():
            default.unlink()


class TestCliValidateConfig:
    """GIVEN cli validate config and the scenario: validate example config"""
    def test_validate_example_config(self) -> None:
        """WHEN the code under test is exercised for: validate example config"""
        example = Path(__file__).parent.parent / "examples" / "config.example.json"
        result = runner.invoke(app, ["validate-config", "--config", str(example)])

        """THEN the expected behaviour holds: validate example config"""
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    """GIVEN cli validate config and the scenario: validate missing file"""
    def test_validate_missing_file(self) -> None:
        """WHEN the code under test is exercised for: validate missing file"""
        result = runner.invoke(app, ["validate-config", "--config", "/nonexistent.json"])

        """THEN the expected behaviour holds: validate missing file"""
        assert result.exit_code == 1


class TestCliVersion:
    """GIVEN cli version and the scenario: version prints"""
    def test_version_prints(self) -> None:
        """WHEN the code under test is exercised for: version prints"""
        result = runner.invoke(app, ["version"])

        """THEN the expected behaviour holds: version prints"""
        assert result.exit_code == 0
        assert "1.0.0" in result.output
