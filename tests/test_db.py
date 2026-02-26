"""Tests for generator.db — DistributionLoader."""

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine

from generator.db import (
    DistributionLoader,
    PART1_TABLES,
    PART2_TABLES,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_test_db(path: Path, tables: list[str]) -> None:
    """Create a small SQLite database with dummy distribution tables."""
    engine = create_engine(f"sqlite:///{path}")
    for table_name in tables:
        df = pd.DataFrame({
            "label": ["a", "b", "c"],
            "weight": [100, 200, 300],
        })
        df.to_sql(table_name, engine, if_exists="replace", index=False)
    engine.dispose()


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temp directory mimicking data/ with a SQLite file."""
    db_path = tmp_path / "distributions_hi_2022.sqlite"
    _create_test_db(db_path, PART1_TABLES)
    return tmp_path


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Create a single temp SQLite file with all tables."""
    db_path = tmp_path / "distributions_hi_2022.sqlite"
    _create_test_db(db_path, PART1_TABLES + PART2_TABLES)
    return db_path


# ── Explicit connection ─────────────────────────────────────────────────


class TestExplicitConnection:
    """Tests for DistributionLoader with an explicit connection string."""

    def test_load_part1_tables(self, tmp_db_path: Path) -> None:
        conn = f"sqlite:///{tmp_db_path}"
        loader = DistributionLoader(conn)

        tables = loader.load_part1_tables("HI", 2022)

        assert len(tables) == len(PART1_TABLES)
        for name in PART1_TABLES:
            assert name in tables
            assert isinstance(tables[name], pd.DataFrame)
            assert len(tables[name]) == 3

        loader.close()

    def test_load_part2_tables(self, tmp_db_path: Path) -> None:
        conn = f"sqlite:///{tmp_db_path}"
        loader = DistributionLoader(conn)

        tables = loader.load_part2_tables("CA", 2021)

        assert len(tables) == len(PART2_TABLES)
        for name in PART2_TABLES:
            assert name in tables

        loader.close()

    def test_load_all_tables(self, tmp_db_path: Path) -> None:
        conn = f"sqlite:///{tmp_db_path}"
        loader = DistributionLoader(conn)

        tables = loader.load_all_tables("HI", 2022)

        expected = len(PART1_TABLES) + len(PART2_TABLES)
        assert len(tables) == expected

        loader.close()

    def test_missing_tables_are_skipped(self, tmp_path: Path) -> None:
        """If the DB only has Part 1 tables, Part 2 loads return empty."""
        db_path = tmp_path / "partial.sqlite"
        _create_test_db(db_path, PART1_TABLES[:3])  # Only 3 tables

        loader = DistributionLoader(f"sqlite:///{db_path}")
        tables = loader.load_part1_tables("HI", 2022)

        assert len(tables) == 3
        loader.close()


# ── Auto-detect ──────────────────────────────────────────────────────────


class TestAutoDetect:
    """Tests for auto-detecting SQLite files in data/ directory."""

    def test_auto_detect_by_state_year(
        self, tmp_data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loader = DistributionLoader()
        # Point the loader's data dir to our temp directory
        loader._data_dir = tmp_data_dir

        tables = loader.load_part1_tables("HI", 2022)
        assert len(tables) == len(PART1_TABLES)
        loader.close()

    def test_auto_detect_fallback_different_year(
        self, tmp_data_dir: Path
    ) -> None:
        """Requesting year 2021 should fall back to the 2022 file."""
        loader = DistributionLoader()
        loader._data_dir = tmp_data_dir

        tables = loader.load_part1_tables("HI", 2021)
        assert len(tables) == len(PART1_TABLES)
        loader.close()

    def test_auto_detect_no_file_raises(self, tmp_path: Path) -> None:
        """Requesting a state with no data should raise FileNotFoundError."""
        loader = DistributionLoader()
        loader._data_dir = tmp_path  # Empty directory

        with pytest.raises(FileNotFoundError, match="No distribution database"):
            loader.load_part1_tables("CA", 2022)

    def test_state_year_required_without_connection(self) -> None:
        """Without a connection string, state and year must be provided."""
        loader = DistributionLoader()
        loader._data_dir = Path("/nonexistent")

        with pytest.raises(ValueError, match="state and year are required"):
            loader._get_engine()

    def test_engine_caching(self, tmp_data_dir: Path) -> None:
        """Engines should be cached so we don't recreate them."""
        loader = DistributionLoader()
        loader._data_dir = tmp_data_dir

        engine1 = loader._get_engine("HI", 2022)
        engine2 = loader._get_engine("HI", 2022)
        assert engine1 is engine2
        loader.close()


# ── DATABASE_URL env var ─────────────────────────────────────────────────


class TestEnvVar:
    """Tests for DATABASE_URL environment variable fallback."""

    def test_database_url_env_var(
        self, tmp_db_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_db_path}")

        loader = DistributionLoader()
        tables = loader.load_part1_tables("HI", 2022)

        assert len(tables) == len(PART1_TABLES)
        loader.close()

        # Clean up env var
        monkeypatch.delenv("DATABASE_URL")


# ── list_available_states ────────────────────────────────────────────────


class TestListAvailableStates:
    """Tests for scanning available state/year combos."""

    def test_list_states_auto_detect(self, tmp_data_dir: Path) -> None:
        loader = DistributionLoader()
        loader._data_dir = tmp_data_dir

        states = loader.list_available_states()

        assert "HI" in states
        assert 2022 in states["HI"]

    def test_list_states_multiple_files(self, tmp_path: Path) -> None:
        """Multiple SQLite files for different states/years."""
        _create_test_db(
            tmp_path / "distributions_hi_2022.sqlite", PART1_TABLES[:1]
        )
        _create_test_db(
            tmp_path / "distributions_ca_2021.sqlite", PART1_TABLES[:1]
        )
        _create_test_db(
            tmp_path / "distributions_ca_2022.sqlite", PART1_TABLES[:1]
        )

        loader = DistributionLoader()
        loader._data_dir = tmp_path

        states = loader.list_available_states()

        assert states == {"HI": [2022], "CA": [2021, 2022]}

    def test_list_states_empty_dir(self, tmp_path: Path) -> None:
        loader = DistributionLoader()
        loader._data_dir = tmp_path

        states = loader.list_available_states()
        assert states == {}

    def test_list_states_explicit_sqlite(self, tmp_db_path: Path) -> None:
        conn = f"sqlite:///{tmp_db_path}"
        loader = DistributionLoader(conn)

        states = loader.list_available_states()

        assert "HI" in states
        assert 2022 in states["HI"]
        loader.close()


# ── DataFrame content ────────────────────────────────────────────────────


class TestDataFrameContent:
    """Verify loaded DataFrames have the expected content."""

    def test_loaded_df_has_correct_columns(self, tmp_db_path: Path) -> None:
        loader = DistributionLoader(f"sqlite:///{tmp_db_path}")
        tables = loader.load_part1_tables("HI", 2022)

        df = tables["household_patterns"]
        assert "label" in df.columns
        assert "weight" in df.columns
        loader.close()

    def test_loaded_df_has_correct_data(self, tmp_db_path: Path) -> None:
        loader = DistributionLoader(f"sqlite:///{tmp_db_path}")
        tables = loader.load_part1_tables("HI", 2022)

        df = tables["household_patterns"]
        assert df["weight"].sum() == 600
        assert list(df["label"]) == ["a", "b", "c"]
        loader.close()


# ── Close / cleanup ─────────────────────────────────────────────────────


class TestCleanup:
    """Tests for engine cleanup."""

    def test_close_disposes_engines(self, tmp_db_path: Path) -> None:
        loader = DistributionLoader(f"sqlite:///{tmp_db_path}")
        loader.load_part1_tables("HI", 2022)

        loader.close()
        assert len(loader._engines) == 0
