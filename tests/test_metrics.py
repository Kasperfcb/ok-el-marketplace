"""Offline regression tests for the Marketplace update sensor."""
from datetime import date
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "ok_el" / "metrics.py"
SPEC = importlib.util.spec_from_file_location("marketplace_ok_el_metrics", MODULE)
metrics = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = metrics
SPEC.loader.exec_module(metrics)


class MeasuredDaysTests(unittest.TestCase):
    def snapshot(self, rows, today=date(2026, 11, 7)):
        return metrics.build_snapshot(
            today=today,
            daily=rows,
            hourly=[],
            monthly=[],
            quarterly=[],
            annual=[],
        )

    def test_count_only_measured_current_month(self):
        rows = [
            {"dato": "2026-10-31T00:00:00", "aflaest": True, "kwh": 3.5},
            {"dato": "2026-11-01T00:00:00", "aflaest": True, "kwh": 0.0},
            {"dato": "2026-11-02T00:00:00", "aflaest": True, "kwh": 4.0},
            {"dato": "2026-11-02T00:00:00", "aflaest": True, "kwh": 4.0},
            {"dato": "2026-11-03T00:00:00", "aflaest": False, "kwh": None},
            {"dato": "2026-11-04T00:00:00", "aflaest": True, "kwh": None},
        ]
        result = self.snapshot(rows)
        self.assertEqual(result.values["current_month_measured_days"], 2)
        self.assertEqual(result.attributes["current_month_measured_days"]["period"], "2026-11")

    def test_no_readings_is_zero_days_not_zero_kwh(self):
        result = self.snapshot([])
        self.assertEqual(result.values["current_month_measured_days"], 0)
        self.assertIsNone(result.values["current_month_kwh"])

    def test_year_boundary(self):
        rows = [{"dato": "2025-12-31", "aflaest": True, "kwh": 3},
                {"dato": "2026-01-01", "aflaest": True, "kwh": 4}]
        result = self.snapshot(rows, today=date(2026, 1, 2))
        self.assertEqual(result.values["current_month_measured_days"], 1)


    def test_recent_days_show_actual_calendar_dates_and_prices(self):
        rows = [
            {"dato": "2026-11-06T00:00:00", "aflaest": True, "kwh": 4.68,
             "dkk_inkl_moms": 13.0},
            {"dato": "2026-11-05T00:00:00", "aflaest": True, "kwh": 3.59,
             "dkk_inkl_moms": 12.69},
            {"dato": "2026-11-04T00:00:00", "aflaest": True, "kwh": 0.0,
             "dkk_inkl_moms": 0.0},
            {"dato": "2026-11-04T00:00:00", "aflaest": True, "kwh": 0.0,
             "dkk_inkl_moms": 0.0},
            {"dato": "2026-11-03T00:00:00", "aflaest": False, "kwh": 0.0,
             "dkk_inkl_moms": 0.0},
        ]
        result = self.snapshot(rows)
        v = result.values
        self.assertEqual(v["day_1_kwh"], 4.68)
        self.assertEqual(v["day_1_cost"], 13.0)
        self.assertEqual(v["day_2_kwh"], 3.59)
        self.assertEqual(v["day_2_cost"], 12.69)
        self.assertEqual(v["day_3_kwh"], 0.0)
        self.assertIsNone(v["day_4_kwh"])
        self.assertIsNone(v["day_4_cost"])
        self.assertAlmostEqual(v["last_7_days_kwh"], 8.27)
        self.assertAlmostEqual(v["last_7_days_cost"], 25.69)
        attr = result.attributes["last_7_days_kwh"]
        self.assertEqual(attr["measured_days"], 3)
        self.assertEqual(attr["expected_days"], 7)
        self.assertEqual(attr["from"], "2026-10-31")
        self.assertEqual(attr["to"], "2026-11-06")
        self.assertEqual(len(attr["daily_history"]), 7)
        self.assertEqual(result.attributes["day_2_kwh"]["date"], "2026-11-05")

    def test_danish_weekday_and_real_date_are_visible(self):
        rows = [
            {"dato": "2026-11-05T00:00:00", "aflaest": True, "kwh": 3.59,
             "dkk_inkl_moms": 12.69},
        ]
        result = self.snapshot(rows)
        self.assertEqual(metrics.day_label(date(2026, 11, 5)), "Torsdag 05/11-26")
        self.assertEqual(metrics.day_label(date(2026, 11, 10)), "Tirsdag 10/11-26")
        self.assertEqual(
            result.attributes["day_2_kwh"]["date_label"], "Torsdag 05/11-26"
        )
        self.assertEqual(
            result.attributes["day_2_cost"]["weekday"], "Torsdag"
        )
        self.assertEqual(
            result.attributes["last_7_days_kwh"]["daily_history"][-3]["date_label"],
            "Torsdag 05/11-26",
        )

    def test_date_labels_roll_over_week_and_year(self):
        result = self.snapshot(
            [{"dato": "2025-12-31", "aflaest": True, "kwh": 2.0}],
            today=date(2026, 1, 2),
        )
        self.assertEqual(
            result.attributes["day_2_kwh"]["date_label"], "Onsdag 31/12-25"
        )
        self.assertEqual(
            result.attributes["day_1_kwh"]["date_label"], "Torsdag 01/01-26"
        )
        self.assertIsNone(result.values["day_1_kwh"])

    def test_recent_days_all_unread_remain_unknown(self):
        result = self.snapshot([
            {"dato": "2026-11-06", "aflaest": False, "kwh": 0.0,
             "dkk_inkl_moms": 0.0}
        ])
        self.assertIsNone(result.values["day_1_kwh"])
        self.assertIsNone(result.values["last_7_days_kwh"])
        self.assertIsNone(result.values["last_7_days_cost"])
        self.assertEqual(result.attributes["last_7_days_cost"]["priced_days"], 0)

    def test_recent_days_span_year_boundary_without_future_data(self):
        result = self.snapshot([
            {"dato": "2025-12-31", "aflaest": True, "kwh": 2.0,
             "dkk_inkl_moms": 4.5},
            {"dato": "2026-01-01", "aflaest": True, "kwh": 4.0,
             "dkk_inkl_moms": 8.0},
            {"dato": "2026-01-02", "aflaest": True, "kwh": 7.0,
             "dkk_inkl_moms": 15.0},
        ], today=date(2026, 1, 2))
        self.assertEqual(result.values["day_1_kwh"], 4.0)
        self.assertEqual(result.values["day_2_kwh"], 2.0)
        self.assertEqual(result.values["last_7_days_kwh"], 6.0)
        self.assertEqual(result.attributes["last_7_days_kwh"]["to"], "2026-01-01")

    def test_recent_days_price_can_be_missing_while_kwh_is_known(self):
        result = self.snapshot([
            {"dato": "2026-11-06", "aflaest": True, "kwh": 5.0}
        ])
        self.assertEqual(result.values["day_1_kwh"], 5.0)
        self.assertIsNone(result.values["day_1_cost"])
        self.assertIsNone(result.values["last_7_days_cost"])
        self.assertEqual(result.attributes["last_7_days_kwh"]["measured_days"], 1)
        self.assertEqual(result.attributes["last_7_days_kwh"]["priced_days"], 0)


if __name__ == "__main__":
    unittest.main()
