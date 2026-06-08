from pathlib import Path


README = Path(__file__).resolve().parents[1] / "README.md"


def test_project_structure_chart_uses_plain_ascii_and_matches_repo_layout():
    text = README.read_text(encoding="utf-8")

    # Chart header
    assert "```text\nforexfactory/\n" in text

    # Top-level files
    assert "|-- pyproject.toml" in text
    assert "|-- requirements.txt" in text
    assert "|-- README.md" in text

    # Package source layout (src/forexfactory/ combined path, D-13)
    assert "|-- src/forexfactory/" in text
    assert "|   |-- __init__.py" in text
    assert "|   |-- cli.py" in text
    assert "|   `-- _scrape.py" in text

    # Tests directory
    assert "|-- tests/" in text
    assert "|   |-- test_docs.py" in text
    assert "|   |-- test_pipeline.py" in text
    assert "|   `-- test_scrape.py" in text

    # Raw input directory (last top-level item; empty after populate-only build)
    assert "`-- out/" in text
    assert "re-scrape" in text


def test_readme_schema_documents_current_parquet_columns():
    text = README.read_text(encoding="utf-8")

    # DATA-01 core schema columns
    assert "| `datetime_utc` |" in text
    assert "| `currency` |" in text
    assert "| `impact` |" in text
    assert "| `title` |" in text
    assert "| `id` |" in text
    assert "| `leaked` | boolean | Whether Forex Factory marked the event as leaked |" in text

    # Phase-2 raw value strings (DATA-02)
    assert "| `forecast_raw` |" in text
    assert "| `actual_raw` |" in text
    assert "| `previous_raw` |" in text
    assert "| `revision_raw` |" in text

    # Phase-2 parsed numerics (DATA-02)
    assert "| `forecast` |" in text
    assert "| `actual` |" in text
    assert "| `previous` |" in text
    assert "| `revision` |" in text

    # Phase-2 surprise flags and identity (DATA-03)
    assert "| `actualBetterWorse` |" in text
    assert "| `revisionBetterWorse` |" in text
    assert "| `ebaseId` |" in text
    assert "| `country` |" in text
    assert "| `hasDataValues` |" in text
