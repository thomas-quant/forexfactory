"""
Tests for src/forexfactory/_analytics.py — surprise and surprise_z helpers.

Covers:
  - API-02: surprise(df) => raw actual - forecast (D-01), row-aligned, NaN-safe (D-03)
  - API-03: surprise_z(df) => z-scored surprise per ebaseId over full history (D-02),
            NaN on <2 releases or std==0 (D-03), row-aligned (D-03)
"""

import math
import unittest

import pandas as pd

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal DataFrame with actual, forecast, ebaseId columns."""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# surprise() tests — API-02
# ---------------------------------------------------------------------------


class SurpriseBasicTests(unittest.TestCase):
    """Raw arithmetic: surprise = actual - forecast (D-01)."""

    def test_positive_surprise(self):
        """actual=4.5, forecast=4.3 -> surprise ~0.2 (actual > forecast)."""
        df = _make_df([{"actual": 4.5, "forecast": 4.3, "ebaseId": 1}])
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertAlmostEqual(result.iloc[0], 0.2, places=10)

    def test_negative_surprise(self):
        """actual=4.0, forecast=4.3 -> surprise ~-0.3 (actual < forecast, sign preserved)."""
        df = _make_df([{"actual": 4.0, "forecast": 4.3, "ebaseId": 1}])
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertAlmostEqual(result.iloc[0], -0.3, places=10)

    def test_zero_surprise(self):
        """actual == forecast -> surprise == 0.0."""
        df = _make_df([{"actual": 2.5, "forecast": 2.5, "ebaseId": 1}])
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertAlmostEqual(result.iloc[0], 0.0, places=10)

    def test_no_polarity_adjustment(self):
        """Surprise is raw arithmetic — actualBetterWorse polarity is NOT applied (D-01)."""
        # A currency release where "lower is better" might have actualBetterWorse=1
        # but we still return actual - forecast as-is.
        df = _make_df(
            [{"actual": 3.0, "forecast": 3.5, "ebaseId": 2, "actualBetterWorse": 1}]
        )
        from forexfactory._analytics import surprise

        result = surprise(df)
        # Should be 3.0 - 3.5 = -0.5, NOT +0.5 (polarity not applied)
        self.assertAlmostEqual(result.iloc[0], -0.5, places=10)


class SurpriseNaNTests(unittest.TestCase):
    """NaN-propagation contract — D-03: never raise, return NaN."""

    def test_nan_actual_returns_nan(self):
        """actual=NaN, forecast=4.3 -> surprise is NaN (D-03)."""
        df = _make_df([{"actual": float("nan"), "forecast": 4.3, "ebaseId": 1}])
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertTrue(math.isnan(result.iloc[0]))

    def test_nan_forecast_returns_nan(self):
        """actual=4.5, forecast=NaN -> surprise is NaN (D-03)."""
        df = _make_df([{"actual": 4.5, "forecast": float("nan"), "ebaseId": 1}])
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertTrue(math.isnan(result.iloc[0]))

    def test_both_nan_returns_nan(self):
        """actual=NaN, forecast=NaN -> surprise is NaN."""
        df = _make_df([{"actual": float("nan"), "forecast": float("nan"), "ebaseId": 1}])
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertTrue(math.isnan(result.iloc[0]))

    def test_all_nan_dataframe_does_not_raise(self):
        """All-NaN actual/forecast DataFrame must not raise (D-03)."""
        df = _make_df(
            [
                {"actual": float("nan"), "forecast": float("nan"), "ebaseId": 1},
                {"actual": float("nan"), "forecast": float("nan"), "ebaseId": 2},
            ]
        )
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertEqual(len(result), 2)
        for val in result:
            self.assertTrue(math.isnan(val))

    def test_empty_dataframe_does_not_raise(self):
        """Empty DataFrame must not raise and must return an empty Series (D-03)."""
        df = pd.DataFrame(
            {"actual": pd.Series([], dtype=float), "forecast": pd.Series([], dtype=float)}
        )
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertEqual(len(result), 0)


class SurpriseRowAlignmentTests(unittest.TestCase):
    """Row-alignment contract — output Series index equals df.index exactly (D-03)."""

    def test_index_equals_input_index_range(self):
        """Standard RangeIndex preserved."""
        df = _make_df(
            [
                {"actual": 1.0, "forecast": 0.5, "ebaseId": 1},
                {"actual": float("nan"), "forecast": 2.0, "ebaseId": 1},
            ]
        )
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertTrue(result.index.equals(df.index))

    def test_custom_index_preserved(self):
        """Non-default integer index is preserved exactly."""
        df = _make_df(
            [
                {"actual": 1.0, "forecast": 0.5, "ebaseId": 1},
                {"actual": 2.0, "forecast": 1.5, "ebaseId": 2},
            ]
        )
        df.index = pd.Index([10, 20])
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertTrue(result.index.equals(df.index))

    def test_no_row_dropping(self):
        """Output length equals input length — no rows dropped even for NaN."""
        df = _make_df(
            [
                {"actual": 1.0, "forecast": 0.5, "ebaseId": 1},
                {"actual": float("nan"), "forecast": 2.0, "ebaseId": 2},
                {"actual": 3.0, "forecast": float("nan"), "ebaseId": 3},
            ]
        )
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertEqual(len(result), len(df))

    def test_returns_series(self):
        """Return type must be pd.Series."""
        df = _make_df([{"actual": 1.0, "forecast": 0.5, "ebaseId": 1}])
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertIsInstance(result, pd.Series)


# ---------------------------------------------------------------------------
# surprise_z() tests — API-03
# ---------------------------------------------------------------------------


class SurpriseZNaNGroupTests(unittest.TestCase):
    """NaN group rules — D-03: <2 releases or std==0 -> NaN."""

    def test_single_release_group_returns_nan(self):
        """Group with only 1 release -> NaN (D-03: <2 releases)."""
        df = _make_df([{"actual": 4.5, "forecast": 4.3, "ebaseId": 100}])
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertTrue(math.isnan(result.iloc[0]))

    def test_constant_surprise_group_returns_nan(self):
        """Group with std==0 (all surprise values identical) -> NaN (D-03: no divide-by-zero)."""
        df = _make_df(
            [
                {"actual": 4.5, "forecast": 4.3, "ebaseId": 200},
                {"actual": 4.5, "forecast": 4.3, "ebaseId": 200},
                {"actual": 4.5, "forecast": 4.3, "ebaseId": 200},
            ]
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        for val in result:
            self.assertTrue(math.isnan(val))

    def test_nan_surprise_rows_return_nan_in_z(self):
        """Rows with NaN surprise remain NaN in the z output (D-03)."""
        df = _make_df(
            [
                {"actual": float("nan"), "forecast": 4.3, "ebaseId": 300},
                {"actual": 4.5, "forecast": 4.0, "ebaseId": 300},
                {"actual": 5.0, "forecast": 4.0, "ebaseId": 300},
            ]
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        # Row 0 has NaN surprise -> NaN z
        self.assertTrue(math.isnan(result.iloc[0]))


class SurpriseZMultiReleaseTests(unittest.TestCase):
    """Multi-release group -> finite z-scores with mean ~0 across the group (D-02)."""

    def test_two_release_group_finite_z(self):
        """Group with 2 distinct surprise values -> finite z-scores."""
        df = _make_df(
            [
                {"actual": 5.0, "forecast": 4.0, "ebaseId": 400},  # surprise=1.0
                {"actual": 3.0, "forecast": 4.0, "ebaseId": 400},  # surprise=-1.0
            ]
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        for val in result:
            self.assertFalse(math.isnan(val))
            self.assertTrue(math.isfinite(val))

    def test_group_mean_approximately_zero(self):
        """z-scores over a full group must have mean ~0 (standardization property)."""
        df = _make_df(
            [
                {"actual": 5.0, "forecast": 4.0, "ebaseId": 500},  # surprise=1.0
                {"actual": 3.0, "forecast": 4.0, "ebaseId": 500},  # surprise=-1.0
                {"actual": 5.5, "forecast": 4.0, "ebaseId": 500},  # surprise=1.5
                {"actual": 2.5, "forecast": 4.0, "ebaseId": 500},  # surprise=-1.5
            ]
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        group_mean = result.mean()
        self.assertAlmostEqual(group_mean, 0.0, places=10)

    def test_multiple_groups_standardized_independently(self):
        """Each ebaseId group is standardized independently (single groupby D-02)."""
        df = _make_df(
            [
                {"actual": 5.0, "forecast": 4.0, "ebaseId": 600},  # surprise=1.0
                {"actual": 3.0, "forecast": 4.0, "ebaseId": 600},  # surprise=-1.0
                {"actual": 100.0, "forecast": 90.0, "ebaseId": 700},  # surprise=10.0
                {"actual": 80.0, "forecast": 90.0, "ebaseId": 700},  # surprise=-10.0
            ]
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        # All should be finite (2 releases each)
        for val in result:
            self.assertFalse(math.isnan(val))
            self.assertTrue(math.isfinite(val))
        # Group 600: z-scores for ±1.0 surprises around mean 0
        # Group 700: z-scores for ±10.0 surprises around mean 0
        # Despite very different scales, the z-scores should be equal in magnitude
        self.assertAlmostEqual(abs(result.iloc[0]), abs(result.iloc[2]), places=10)


class SurpriseZEdgeCaseTests(unittest.TestCase):
    """Edge cases: empty, single-row, all-NaN input (D-03: never raise)."""

    def test_empty_dataframe_does_not_raise(self):
        """Empty DataFrame must not raise and must return an empty Series (D-03)."""
        df = pd.DataFrame(
            {
                "actual": pd.Series([], dtype=float),
                "forecast": pd.Series([], dtype=float),
                "ebaseId": pd.Series([], dtype="Int64"),
            }
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertEqual(len(result), 0)

    def test_single_row_does_not_raise(self):
        """Single-row DataFrame must not raise — returns NaN (<2 releases)."""
        df = _make_df([{"actual": 4.5, "forecast": 4.3, "ebaseId": 800}])
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertEqual(len(result), 1)
        self.assertTrue(math.isnan(result.iloc[0]))

    def test_all_nan_surprise_does_not_raise(self):
        """All-NaN surprise (all rows have NaN actual/forecast) must not raise."""
        df = _make_df(
            [
                {"actual": float("nan"), "forecast": float("nan"), "ebaseId": 900},
                {"actual": float("nan"), "forecast": float("nan"), "ebaseId": 900},
            ]
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertEqual(len(result), 2)


class SurpriseZRowAlignmentTests(unittest.TestCase):
    """Row-alignment contract — output Series index equals df.index exactly (D-03)."""

    def test_index_equals_input_index(self):
        """Standard RangeIndex preserved."""
        df = _make_df(
            [
                {"actual": 5.0, "forecast": 4.0, "ebaseId": 1000},
                {"actual": 3.0, "forecast": 4.0, "ebaseId": 1000},
                {"actual": 4.5, "forecast": 4.3, "ebaseId": 1001},  # single release
            ]
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertTrue(result.index.equals(df.index))

    def test_custom_index_preserved(self):
        """Non-default integer index is preserved exactly."""
        df = _make_df(
            [
                {"actual": 5.0, "forecast": 4.0, "ebaseId": 1100},
                {"actual": 3.0, "forecast": 4.0, "ebaseId": 1100},
            ]
        )
        df.index = pd.Index([100, 200])
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertTrue(result.index.equals(df.index))

    def test_no_row_dropping(self):
        """Output length equals input length — NaN rows not dropped."""
        df = _make_df(
            [
                {"actual": 5.0, "forecast": 4.0, "ebaseId": 1200},
                {"actual": float("nan"), "forecast": 4.0, "ebaseId": 1200},
                {"actual": 3.0, "forecast": 4.0, "ebaseId": 1200},
            ]
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertEqual(len(result), len(df))

    def test_returns_series(self):
        """Return type must be pd.Series."""
        df = _make_df(
            [
                {"actual": 5.0, "forecast": 4.0, "ebaseId": 1300},
                {"actual": 3.0, "forecast": 4.0, "ebaseId": 1300},
            ]
        )
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertIsInstance(result, pd.Series)


class SurpriseZNullableEbaseIdTests(unittest.TestCase):
    """surprise_z must tolerate nullable Int64 ebaseId with <NA> values (D-03)."""

    def test_na_ebase_id_does_not_raise(self):
        """Rows with pd.NA ebaseId (nullable Int64) must not raise."""
        df = pd.DataFrame(
            {
                "actual": [4.5, 4.0],
                "forecast": [4.3, 4.3],
                "ebaseId": pd.array([pd.NA, pd.NA], dtype="Int64"),
            }
        )
        from forexfactory._analytics import surprise_z

        # Should not raise — <NA> ebaseId rows form a single group that may be NaN
        result = surprise_z(df)
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# Missing-column guard tests — Gap 1 regression (05-04)
# ---------------------------------------------------------------------------


class SurpriseMissingColumnTests(unittest.TestCase):
    """surprise() must return all-NaN row-aligned Series when required columns are absent (D-03)."""

    def test_missing_actual_returns_all_nan(self):
        """Frame with 'forecast' but no 'actual' -> all-NaN, no raise."""
        df = pd.DataFrame({"forecast": [4.3]})
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.index.equals(df.index))
        self.assertTrue(result.isna().all())

    def test_missing_forecast_returns_all_nan(self):
        """Frame with 'actual' but no 'forecast' -> all-NaN, no raise."""
        df = pd.DataFrame({"actual": [4.5]})
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.index.equals(df.index))
        self.assertTrue(result.isna().all())

    def test_missing_both_columns_returns_all_nan(self):
        """Frame with neither 'actual' nor 'forecast' -> all-NaN, no raise."""
        df = pd.DataFrame({"foo": [1, 2]})
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.index.equals(df.index))
        self.assertTrue(result.isna().all())

    def test_empty_no_column_dataframe_returns_empty_nan_series(self):
        """pd.DataFrame() (zero rows, zero columns) -> empty all-NaN Series, no raise."""
        df = pd.DataFrame()
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), 0)
        self.assertTrue(result.index.equals(df.index))

    def test_custom_index_preserved_missing_columns(self):
        """Custom index is preserved even when columns are absent."""
        df = pd.DataFrame({"bar": [10, 20, 30]}, index=pd.Index([5, 10, 15]))
        from forexfactory._analytics import surprise

        result = surprise(df)
        self.assertTrue(result.index.equals(df.index))
        self.assertTrue(result.isna().all())


class SurpriseZMissingColumnTests(unittest.TestCase):
    """surprise_z() must return all-NaN row-aligned Series when required columns are absent (D-03)."""

    def test_missing_ebaseid_returns_all_nan(self):
        """Frame with actual+forecast but no 'ebaseId' -> all-NaN, no raise."""
        df = pd.DataFrame({"actual": [4.5], "forecast": [4.3]})
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.index.equals(df.index))
        self.assertTrue(result.isna().all())

    def test_has_ebaseid_but_missing_actual_returns_all_nan(self):
        """Frame with ebaseId but no 'actual' -> all-NaN, no raise (transitive guard)."""
        df = pd.DataFrame({"forecast": [4.3], "ebaseId": [100]})
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.index.equals(df.index))
        self.assertTrue(result.isna().all())

    def test_has_ebaseid_but_missing_forecast_returns_all_nan(self):
        """Frame with ebaseId but no 'forecast' -> all-NaN, no raise (transitive guard)."""
        df = pd.DataFrame({"actual": [4.5], "ebaseId": [100]})
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.index.equals(df.index))
        self.assertTrue(result.isna().all())

    def test_empty_no_column_dataframe_returns_empty_series(self):
        """pd.DataFrame() (zero rows, zero columns) -> empty Series, no raise."""
        df = pd.DataFrame()
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), 0)

    def test_missing_ebaseid_multi_row_row_aligned(self):
        """Multi-row frame missing ebaseId -> all-NaN, index preserved."""
        df = pd.DataFrame({"actual": [4.5, 5.0, 3.2], "forecast": [4.3, 4.8, 3.0]})
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.index.equals(df.index))
        self.assertTrue(result.isna().all())

    def test_no_column_frame_with_custom_index(self):
        """Custom-indexed frame with no columns -> all-NaN, index preserved."""
        df = pd.DataFrame(index=pd.Index([7, 8, 9]))
        from forexfactory._analytics import surprise_z

        result = surprise_z(df)
        self.assertEqual(len(result), len(df))
        self.assertTrue(result.index.equals(df.index))


if __name__ == "__main__":
    unittest.main()
