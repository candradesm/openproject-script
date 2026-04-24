"""Unit tests for openproject.cli module (build_arg_parser + validate_flag_args)."""
import argparse
import sys
import unittest
from datetime import date


from openproject.cli import build_arg_parser, validate_flag_args


# ── ErrorCatcher helper (stdlib only — no mock) ────────────────────────────────

class ErrorCatcher:
    """Replaces parser.error so we can assert on it without exiting the process."""

    def __init__(self):
        self.last_error = None

    def error(self, msg):
        self.last_error = msg
        raise SystemExit(2)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_valid_args(**overrides):
    """Return a Namespace with all required fields for a valid single-date run."""
    defaults = dict(
        base_url="https://openproject.example.com",
        api_key="secret-token",
        work_package_id=1296,
        user_id=None,
        activity_id=3,
        hours=8.0,
        comment="",
        date=date(2026, 3, 12),
        start_date=None,
        end_date=None,
        special_days_file=None,
        festive_activity_id=None,
        vacation_activity_id=None,
        dry_run=False,
        monke=False,
        insecure=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ══════════════════════════════════════════════════════════════════════════════
# TestBuildArgParser
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildArgParser(unittest.TestCase):

    def setUp(self):
        self.parser = build_arg_parser()

    def test_parser_returns_parser(self):
        self.assertIsInstance(self.parser, argparse.ArgumentParser)

    def test_date_flag_parsed(self):
        args = self.parser.parse_args(["--date", "2026-03-12"])
        self.assertEqual(args.date, date(2026, 3, 12))

    def test_start_end_flags_parsed(self):
        args = self.parser.parse_args([
            "--start-date", "2026-03-01",
            "--end-date",   "2026-03-31",
        ])
        self.assertEqual(args.start_date, date(2026, 3, 1))
        self.assertEqual(args.end_date,   date(2026, 3, 31))

    def test_special_days_file_parsed(self):
        args = self.parser.parse_args(["--special-days-file", "path.csv"])
        self.assertEqual(args.special_days_file, "path.csv")

    def test_festive_activity_id_parsed(self):
        args = self.parser.parse_args(["--festive-activity-id", "5"])
        self.assertEqual(args.festive_activity_id, 5)

    def test_vacation_activity_id_parsed(self):
        args = self.parser.parse_args(["--vacation-activity-id", "7"])
        self.assertEqual(args.vacation_activity_id, 7)

    def test_default_hours(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.hours, 8.0)

    def test_default_activity_id(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.activity_id, 3)

    def test_dry_run_flag(self):
        args = self.parser.parse_args(["--dry-run"])
        self.assertTrue(args.dry_run)

    def test_monke_flag(self):
        args = self.parser.parse_args(["--monke"])
        self.assertTrue(args.monke)

    def test_date_and_start_date_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args([
                "--date",       "2026-03-12",
                "--start-date", "2026-03-01",
            ])


# ══════════════════════════════════════════════════════════════════════════════
# TestValidateFlagArgs
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateFlagArgs(unittest.TestCase):

    def _catcher(self):
        return ErrorCatcher()

    def test_missing_base_url_raises(self):
        args = _make_valid_args(base_url=None)
        catcher = self._catcher()
        with self.assertRaises(SystemExit):
            validate_flag_args(args, catcher)
        self.assertIsNotNone(catcher.last_error)
        self.assertIn("base-url", catcher.last_error)

    def test_missing_api_key_raises(self):
        args = _make_valid_args(api_key=None)
        catcher = self._catcher()
        with self.assertRaises(SystemExit):
            validate_flag_args(args, catcher)
        self.assertIsNotNone(catcher.last_error)
        self.assertIn("api-key", catcher.last_error)

    def test_missing_work_package_raises(self):
        args = _make_valid_args(work_package_id=None)
        catcher = self._catcher()
        with self.assertRaises(SystemExit):
            validate_flag_args(args, catcher)
        self.assertIsNotNone(catcher.last_error)
        self.assertIn("work-package-id", catcher.last_error)

    def test_missing_date_mode_raises(self):
        args = _make_valid_args(date=None, start_date=None, end_date=None)
        catcher = self._catcher()
        with self.assertRaises(SystemExit):
            validate_flag_args(args, catcher)
        self.assertIsNotNone(catcher.last_error)

    def test_start_without_end_raises(self):
        args = _make_valid_args(date=None, start_date=date(2026, 3, 1), end_date=None)
        catcher = self._catcher()
        with self.assertRaises(SystemExit):
            validate_flag_args(args, catcher)
        self.assertIsNotNone(catcher.last_error)
        self.assertIn("end-date", catcher.last_error)

    def test_end_without_start_raises(self):
        args = _make_valid_args(date=None, start_date=None, end_date=date(2026, 3, 31))
        catcher = self._catcher()
        with self.assertRaises(SystemExit):
            validate_flag_args(args, catcher)
        self.assertIsNotNone(catcher.last_error)
        self.assertIn("start-date", catcher.last_error)

    def test_start_after_end_raises(self):
        args = _make_valid_args(
            date=None,
            start_date=date(2026, 3, 31),
            end_date=date(2026, 3, 1),
        )
        catcher = self._catcher()
        with self.assertRaises(SystemExit):
            validate_flag_args(args, catcher)
        self.assertIsNotNone(catcher.last_error)

    def test_zero_hours_raises(self):
        args = _make_valid_args(hours=0.0)
        catcher = self._catcher()
        with self.assertRaises(SystemExit):
            validate_flag_args(args, catcher)
        self.assertIsNotNone(catcher.last_error)
        self.assertIn("hours", catcher.last_error)

    def test_negative_hours_raises(self):
        args = _make_valid_args(hours=-1.0)
        catcher = self._catcher()
        with self.assertRaises(SystemExit):
            validate_flag_args(args, catcher)
        self.assertIsNotNone(catcher.last_error)
        self.assertIn("hours", catcher.last_error)

    def test_valid_single_date_passes(self):
        args = _make_valid_args()
        catcher = self._catcher()
        # Should not raise
        validate_flag_args(args, catcher)
        self.assertIsNone(catcher.last_error)

    def test_valid_date_range_passes(self):
        args = _make_valid_args(
            date=None,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        catcher = self._catcher()
        # Should not raise
        validate_flag_args(args, catcher)
        self.assertIsNone(catcher.last_error)


if __name__ == "__main__":
    unittest.main()
