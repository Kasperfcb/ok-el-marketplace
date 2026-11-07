"""Tests for bounded, private, persistent OK electricity time series."""
import importlib.util
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "custom_components" / "ok_el" / "history_data.py"
SPEC = importlib.util.spec_from_file_location("ok_el_history_data_tests", PATH)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class HistoryTests(unittest.TestCase):
    def test_merge_preserves_existing_reading_when_later_unavailable(self):
        original = [{"dato": "2026-11-05T00:00:00", "aflaest": True,
                     "kwh": 3.59, "dkk_inkl_moms": 12.69}]
        missing = [{"dato": "2026-11-05T00:00:00", "aflaest": False,
                    "kwh": None, "dkk_inkl_moms": None}]
        result = mod.merge_rows(original, missing, "DAY")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kwh"], 3.59)
        self.assertEqual(result[0]["dkk_inkl_moms"], 12.69)
        self.assertTrue(result[0]["aflaest"])

    def test_genuine_zero_and_price_corrections(self):
        old = [{"dato": "2026-11-05", "aflaest": True, "kwh": 5,
                "dkk_inkl_moms": 15}]
        new = [{"dato": "2026-11-05", "aflaest": True, "kwh": 0.0,
                "dkk_inkl_moms": 0.0}]
        result = mod.merge_rows(old, new, "DAY")
        self.assertEqual(result[0]["kwh"], 0.0)
        self.assertEqual(result[0]["dkk_inkl_moms"], 0.0)

    def test_filters_identifiers_and_sensitive_unexpected_fields(self):
        rows = [{"dato": "2026-11-05", "aflaest": True, "kwh": 4.0,
                 "aftalenr": 1234567, "email": "do-not-copy",
                 "password": "secret", "token": "abc"}]
        result = mod.merge_rows([], rows, "DAY")
        self.assertEqual(len(result), 1)
        for key in ("aftalenr", "email", "password", "token"):
            self.assertNotIn(key, result[0])

    def test_sorting_deduplication_and_period_isolation(self):
        a = {"DAY": [{"dato": "2026-11-03", "kwh": 3},
                     {"dato": "2026-11-01", "kwh": 1}]}
        b = {"DAY": [{"dato": "2026-11-03", "kwh": 4},
                     {"dato": "2026-11-02", "kwh": None}]}
        result = mod.merge_history(a, b)
        self.assertEqual([x["dato"] for x in result["DAY"]],
                         ["2026-11-01", "2026-11-02", "2026-11-03"])
        self.assertEqual(result["DAY"][-1]["kwh"], 4)
        self.assertEqual(result["HOUR"], [])
        self.assertEqual(mod.history_summary(result)["DAY"], 3)

    def test_incremental_month_plan_skips_cached_and_checked(self):
        from datetime import date
        months = [(2026, 11), (2026, 10), (2026, 9), (2026, 8),
                  (2026, 7), (2026, 6)]
        saved = [
            {"dato": "2026-09-01T00:00:00", "kwh": 2.0},
            {"dato": "2026-08-01T00:00:00", "kwh": 0.0},
        ]
        requested = mod.missing_archive_months(
            months, date(2026, 11, 8), saved, ["2026-07", "2026-06"]
        )
        self.assertEqual(requested, [(2026, 11), (2026, 10)])

    def test_incremental_month_plan_retries_failed_scopes(self):
        from datetime import date
        months = [(2026, 6), (2026, 5)]
        wanted = mod.missing_archive_months(
            months, date(2026, 11, 8), [], ["2026-05"]
        )
        self.assertEqual(wanted, [(2026, 6)])

    def test_incremental_hour_plan_skips_complete_days(self):
        daily = [
            {"dato": "2026-11-07T00:00:00", "aflaest": False, "kwh": None},
            {"dato": "2026-11-06T00:00:00", "aflaest": True, "kwh": 4.2},
            {"dato": "2026-11-05T00:00:00", "aflaest": True, "kwh": 3.1},
            {"dato": "2026-11-04T00:00:00", "aflaest": True, "kwh": 3.0},
        ]
        existing = [
            {"dato": f"2026-11-06T{h:02d}:00:00",
             "kwh": 0.2, "aflaest": True}
            for h in range(24)
        ] + [
            {"dato": f"2026-11-05T{h:02d}:00:00",
             "kwh": 0.3, "aflaest": True}
            for h in range(10)
        ]
        self.assertEqual(
            mod.missing_hour_dates(daily, existing, 3),
            ["2026-11-05", "2026-11-04"],
        )

    def test_reject_invalid_timestamp_and_limit_size(self):
        self.assertEqual(mod.merge_rows([], [{"dato": "not-a-date", "kwh": 4}], "DAY"), [])
        with self.assertRaises(ValueError):
            mod.merge_rows([], [], "WEEK")
        original = mod.LIMITS["YEAR"]
        try:
            mod.LIMITS["YEAR"] = 2
            rows = [{"dato": f"{year}-01-01", "kwh": 1} for year in range(2023, 2028)]
            result = mod.merge_rows([], rows, "YEAR")
            self.assertEqual([r["dato"] for r in result], ["2026-01-01", "2027-01-01"])
        finally:
            mod.LIMITS["YEAR"] = original


if __name__ == "__main__":
    unittest.main()
