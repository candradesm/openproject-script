"""Unit tests for openproject.dates module."""
import argparse
import unittest
from datetime import date

from openproject.dates import (
    _parse_iso_duration,
    date_range,
    hours_to_iso8601,
    is_weekend,
    parse_date_arg,
)


class TestIsWeekend(unittest.TestCase):
    """Tests for is_weekend()."""

    def test_saturday_is_weekend(self):
        # 2026-04-18 is a Saturday
        self.assertTrue(is_weekend(date(2026, 4, 18)))

    def test_sunday_is_weekend(self):
        # 2026-04-19 is a Sunday
        self.assertTrue(is_weekend(date(2026, 4, 19)))

    def test_monday_is_not_weekend(self):
        # 2026-04-20 is a Monday
        self.assertFalse(is_weekend(date(2026, 4, 20)))

    def test_friday_is_not_weekend(self):
        # 2026-04-24 is a Friday
        self.assertFalse(is_weekend(date(2026, 4, 24)))


class TestDateRange(unittest.TestCase):
    """Tests for date_range()."""

    def test_single_day_range(self):
        d = date(2026, 4, 20)
        self.assertEqual(date_range(d, d), [d])

    def test_start_equals_end(self):
        d = date(2026, 1, 1)
        result = date_range(d, d)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], d)

    def test_multi_day_range(self):
        start = date(2026, 4, 20)
        end = date(2026, 4, 22)
        expected = [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]
        self.assertEqual(date_range(start, end), expected)

    def test_range_count(self):
        # Monday to Friday = 5 days
        start = date(2026, 4, 20)  # Monday
        end = date(2026, 4, 24)    # Friday
        result = date_range(start, end)
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], start)
        self.assertEqual(result[-1], end)


class TestHoursToIso8601(unittest.TestCase):
    """Tests for hours_to_iso8601()."""

    def test_whole_hours(self):
        self.assertEqual(hours_to_iso8601(8.0), "PT8H")

    def test_half_hour(self):
        self.assertEqual(hours_to_iso8601(0.5), "PT0H30M")

    def test_hours_and_minutes(self):
        self.assertEqual(hours_to_iso8601(7.5), "PT7H30M")

    def test_one_hour(self):
        self.assertEqual(hours_to_iso8601(1.0), "PT1H")

    def test_zero_minutes_omitted(self):
        result = hours_to_iso8601(4.0)
        self.assertEqual(result, "PT4H")
        self.assertNotIn("M", result)


class TestParseIsoDuration(unittest.TestCase):
    """Tests for _parse_iso_duration()."""

    def test_hours_only(self):
        self.assertAlmostEqual(_parse_iso_duration("PT8H"), 8.0)

    def test_hours_and_minutes(self):
        self.assertAlmostEqual(_parse_iso_duration("PT7H30M"), 7.5)

    def test_minutes_only(self):
        self.assertAlmostEqual(_parse_iso_duration("PT30M"), 0.5)

    def test_lowercase(self):
        self.assertAlmostEqual(_parse_iso_duration("pt8h"), 8.0)


class TestParseDateArg(unittest.TestCase):
    """Tests for parse_date_arg()."""

    def test_valid_date(self):
        result = parse_date_arg("2026-03-12")
        self.assertEqual(result, date(2026, 3, 12))

    def test_invalid_date_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_date_arg("not-a-date")

    def test_wrong_format_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_date_arg("12/03/2026")


if __name__ == "__main__":
    unittest.main()
