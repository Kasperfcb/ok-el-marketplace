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


if __name__ == "__main__":
    unittest.main()
