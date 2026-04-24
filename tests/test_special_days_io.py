"""Unit tests for openproject.special_days.io module."""
import os
import tempfile
import unittest
from datetime import date

from openproject.special_days.io import (
    _load_csv_entries,
    _load_ics_entries,
    compare_entries,
    ensure_csv_from_ics,
    expand_entries,
    load_special_day_entries,
    save_csv_entries,
)
from openproject.special_days.model import SpecialDayEntry


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_temp_file(content, suffix=".tmp"):
    """Write content to a named temp file and return its path. Caller must unlink."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        os.close(fd)
        raise
    return path


def _make_entry(start, end, entry_type="festive", name="Test"):
    return SpecialDayEntry(start=start, end=end, type=entry_type, name=name)


# ── TestSaveAndLoadCsv ─────────────────────────────────────────────────────────

class TestSaveAndLoadCsv(unittest.TestCase):
    """Tests for save_csv_entries() + _load_csv_entries() round-trip."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_round_trip(self):
        entries = [
            _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year"),
            _make_entry(date(2026, 8, 15), date(2026, 8, 15), "vacation", "Summer break"),
        ]
        save_csv_entries(self.path, entries)
        loaded = _load_csv_entries(self.path)
        self.assertEqual(len(loaded), 2)
        # Sorted by start date, so New Year comes first
        self.assertEqual(loaded[0].name, "New Year")
        self.assertEqual(loaded[0].type, "festive")
        self.assertEqual(loaded[0].start, date(2026, 1, 1))
        self.assertEqual(loaded[1].name, "Summer break")
        self.assertEqual(loaded[1].type, "vacation")

    def test_malformed_rows_skipped(self):
        content = (
            "start_date,end_date,type,name\n"
            "2026-01-01,2026-01-01,festive,Good Entry\n"
            "not-a-date,2026-01-02,festive,Bad Entry\n"
            "2026-03-01,2026-03-01,vacation,Another Good\n"
        )
        path = _write_temp_file(content, suffix=".csv")
        try:
            loaded = _load_csv_entries(path)
            self.assertEqual(len(loaded), 2)
            names = [e.name for e in loaded]
            self.assertIn("Good Entry", names)
            self.assertIn("Another Good", names)
            self.assertNotIn("Bad Entry", names)
        finally:
            os.unlink(path)

    def test_sorted_by_start_date(self):
        entries = [
            _make_entry(date(2026, 12, 25), date(2026, 12, 25), "festive", "Christmas"),
            _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year"),
            _make_entry(date(2026, 6, 15), date(2026, 6, 15), "vacation", "Mid Year"),
        ]
        save_csv_entries(self.path, entries)
        loaded = _load_csv_entries(self.path)
        starts = [e.start for e in loaded]
        self.assertEqual(starts, sorted(starts))

    def test_empty_entries(self):
        save_csv_entries(self.path, [])
        loaded = _load_csv_entries(self.path)
        self.assertEqual(loaded, [])

    def test_unknown_type_coerced(self):
        content = (
            "start_date,end_date,type,name\n"
            "2026-05-01,2026-05-01,holiday,Labour Day\n"
        )
        path = _write_temp_file(content, suffix=".csv")
        try:
            loaded = _load_csv_entries(path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].type, "festive")
        finally:
            os.unlink(path)

    def test_end_before_start_corrected(self):
        content = (
            "start_date,end_date,type,name\n"
            "2026-05-10,2026-05-05,festive,Backwards Day\n"
        )
        path = _write_temp_file(content, suffix=".csv")
        try:
            loaded = _load_csv_entries(path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].end, loaded[0].start)
        finally:
            os.unlink(path)


# ── TestExpandEntries ──────────────────────────────────────────────────────────

class TestExpandEntries(unittest.TestCase):
    """Tests for expand_entries()."""

    def test_single_day(self):
        d = date(2026, 4, 20)
        entry = _make_entry(d, d, "festive", "Holiday")
        result = expand_entries([entry])
        self.assertIn(d, result)
        self.assertEqual(result[d], ("festive", "Holiday"))

    def test_multi_day_range(self):
        start = date(2026, 4, 20)
        end = date(2026, 4, 22)
        entry = _make_entry(start, end, "vacation", "Trip")
        result = expand_entries([entry])
        self.assertEqual(len(result), 3)
        for d in [date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22)]:
            self.assertIn(d, result)
            self.assertEqual(result[d], ("vacation", "Trip"))

    def test_overlap_last_wins(self):
        d = date(2026, 4, 20)
        entry1 = _make_entry(d, d, "festive", "First")
        entry2 = _make_entry(d, d, "vacation", "Second")
        result = expand_entries([entry1, entry2])
        self.assertEqual(result[d], ("vacation", "Second"))

    def test_empty_list(self):
        result = expand_entries([])
        self.assertEqual(result, {})


# ── TestCompareEntries ─────────────────────────────────────────────────────────

class TestCompareEntries(unittest.TestCase):
    """Tests for compare_entries()."""

    def test_new_entry_detected(self):
        ics = [_make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year")]
        csv = []
        result = compare_entries(ics, csv)
        self.assertEqual(len(result["new"]), 1)
        self.assertEqual(result["new"][0].name, "New Year")
        self.assertEqual(len(result["existing"]), 0)
        self.assertEqual(len(result["conflicts"]), 0)
        self.assertEqual(len(result["csv_only"]), 0)

    def test_existing_entry(self):
        entry = _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year")
        result = compare_entries([entry], [entry])
        self.assertEqual(len(result["existing"]), 1)
        self.assertEqual(len(result["new"]), 0)
        self.assertEqual(len(result["conflicts"]), 0)

    def test_conflict_diff_name(self):
        ics_e = _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year ICS")
        csv_e = _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year CSV")
        result = compare_entries([ics_e], [csv_e])
        self.assertEqual(len(result["conflicts"]), 1)
        conflict_ics, conflict_csv = result["conflicts"][0]
        self.assertEqual(conflict_ics.name, "New Year ICS")
        self.assertEqual(conflict_csv.name, "New Year CSV")

    def test_conflict_diff_type(self):
        ics_e = _make_entry(date(2026, 5, 1), date(2026, 5, 1), "festive", "Labour Day")
        csv_e = _make_entry(date(2026, 5, 1), date(2026, 5, 1), "vacation", "Labour Day")
        result = compare_entries([ics_e], [csv_e])
        self.assertEqual(len(result["conflicts"]), 1)

    def test_csv_only_entry(self):
        csv_e = _make_entry(date(2026, 7, 4), date(2026, 7, 4), "festive", "Manual Entry")
        result = compare_entries([], [csv_e])
        self.assertEqual(len(result["csv_only"]), 1)
        self.assertEqual(result["csv_only"][0].name, "Manual Entry")

    def test_empty_inputs(self):
        result = compare_entries([], [])
        self.assertEqual(result["new"], [])
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["existing"], [])
        self.assertEqual(result["csv_only"], [])


# ── TestLoadIcsEntries ─────────────────────────────────────────────────────────

class TestLoadIcsEntries(unittest.TestCase):
    """Tests for _load_ics_entries()."""

    def _load_from_content(self, content):
        path = _write_temp_file(content, suffix=".ics")
        try:
            return _load_ics_entries(path)
        finally:
            os.unlink(path)

    def _make_ics(self, dtstart, dtend, summary, categories=None):
        """Build a minimal ICS file string with one VEVENT."""
        categories_line = ""
        if categories:
            categories_line = "CATEGORIES:{}\n".format(categories)
        return (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "BEGIN:VEVENT\n"
            "DTSTART;VALUE=DATE:{}\n"
            "DTEND;VALUE=DATE:{}\n"
            "SUMMARY:{}\n"
            "{}"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        ).format(dtstart, dtend, summary, categories_line)

    def test_basic_festive_event(self):
        content = self._make_ics("20260101", "20260102", "New Year", "FESTIVE")
        entries = self._load_from_content(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].type, "festive")
        self.assertEqual(entries[0].name, "New Year")
        self.assertEqual(entries[0].start, date(2026, 1, 1))

    def test_vacation_category(self):
        content = self._make_ics("20260801", "20260816", "Summer Vacation", "VACATION")
        entries = self._load_from_content(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].type, "vacation")

    def test_no_category_defaults_festive(self):
        content = self._make_ics("20261225", "20261226", "Christmas")
        entries = self._load_from_content(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].type, "festive")

    def test_multi_day_event(self):
        # DTEND is exclusive: 20260105 means the event ends on 20260104
        content = self._make_ics("20260101", "20260105", "New Year Week")
        entries = self._load_from_content(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].start, date(2026, 1, 1))
        self.assertEqual(entries[0].end, date(2026, 1, 4))

    def test_datetime_format(self):
        # DTSTART with datetime (not DATE) format
        content = (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "BEGIN:VEVENT\n"
            "DTSTART:20260417T000000Z\n"
            "DTEND:20260418T000000Z\n"
            "SUMMARY:Datetime Event\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        entries = self._load_from_content(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].start, date(2026, 4, 17))

    def test_empty_file(self):
        entries = self._load_from_content("")
        self.assertEqual(entries, [])

    def test_ics_line_folding(self):
        # ICS line folding: long lines are split with CRLF + space/tab
        content = (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "BEGIN:VEVENT\n"
            "DTSTART;VALUE=DATE:20260601\n"
            "DTEND;VALUE=DATE:20260602\n"
            "SUMMARY:A Very Long Summary That Gets\n"
            " Folded Across Two Lines\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        entries = self._load_from_content(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "A Very Long Summary That GetsFolded Across Two Lines")

    def test_time_off_category(self):
        content = self._make_ics("20260901", "20260902", "Day Off", "TIME OFF")
        entries = self._load_from_content(content)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].type, "vacation")


# ── TestLoadSpecialDayEntries ──────────────────────────────────────────────────

class TestLoadSpecialDayEntries(unittest.TestCase):
    """Tests for load_special_day_entries() auto-detection."""

    def test_auto_detect_csv(self):
        content = (
            "start_date,end_date,type,name\n"
            "2026-01-01,2026-01-01,festive,New Year\n"
        )
        path = _write_temp_file(content, suffix=".csv")
        try:
            entries = load_special_day_entries(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].name, "New Year")
        finally:
            os.unlink(path)

    def test_auto_detect_ics(self):
        content = (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "BEGIN:VEVENT\n"
            "DTSTART;VALUE=DATE:20261225\n"
            "DTEND;VALUE=DATE:20261226\n"
            "SUMMARY:Christmas\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        path = _write_temp_file(content, suffix=".ics")
        try:
            entries = load_special_day_entries(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].name, "Christmas")
        finally:
            os.unlink(path)


# ── TestEnsureCsvFromIcs ───────────────────────────────────────────────────────

class TestEnsureCsvFromIcs(unittest.TestCase):
    """Tests for ensure_csv_from_ics()."""

    # ── Scenario 1: No existing CSV ────────────────────────────────────────────

    def test_no_existing_csv_creates_file(self):
        """CSV is created at <same_dir>/<same_stem>.csv when none exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")
            expected_csv = os.path.join(tmpdir, "holidays.csv")

            ics_entries = [
                _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year"),
                _make_entry(date(2026, 12, 25), date(2026, 12, 25), "festive", "Christmas"),
            ]

            csv_path, merged = ensure_csv_from_ics(ics_path, ics_entries)

            self.assertEqual(csv_path, expected_csv)
            self.assertTrue(os.path.exists(expected_csv))

    def test_no_existing_csv_contains_all_ics_entries(self):
        """CSV contains all ICS entries when created from scratch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")

            ics_entries = [
                _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year"),
                _make_entry(date(2026, 12, 25), date(2026, 12, 25), "festive", "Christmas"),
            ]

            csv_path, merged = ensure_csv_from_ics(ics_path, ics_entries)

            loaded = _load_csv_entries(csv_path)
            self.assertEqual(len(loaded), 2)
            names = {e.name for e in loaded}
            self.assertIn("New Year", names)
            self.assertIn("Christmas", names)

    def test_no_existing_csv_returned_path_matches(self):
        """Returned csv_path equals the expected sibling path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "calendar.ics")
            expected_csv = os.path.join(tmpdir, "calendar.csv")

            csv_path, _ = ensure_csv_from_ics(ics_path, [])

            self.assertEqual(csv_path, expected_csv)

    def test_no_existing_csv_returned_entries_match_sorted_ics(self):
        """Returned merged_entries equals ICS entries sorted by (start, end)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")

            ics_entries = [
                _make_entry(date(2026, 12, 25), date(2026, 12, 25), "festive", "Christmas"),
                _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year"),
            ]

            _, merged = ensure_csv_from_ics(ics_path, ics_entries)

            starts = [e.start for e in merged]
            self.assertEqual(starts, sorted(starts))
            self.assertEqual(len(merged), 2)

    # ── Scenario 2: CSV already exists, ICS has same entries ──────────────────

    def test_existing_csv_same_entries_no_duplicates(self):
        """No duplicates when ICS entries are identical to existing CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")
            csv_path = os.path.join(tmpdir, "holidays.csv")

            entries = [
                _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year"),
                _make_entry(date(2026, 5, 1), date(2026, 5, 1), "festive", "Labour Day"),
            ]
            save_csv_entries(csv_path, entries)

            _, merged = ensure_csv_from_ics(ics_path, entries)

            self.assertEqual(len(merged), 2)

    def test_existing_csv_same_entries_length_unchanged(self):
        """Returned list length equals original CSV length when entries are identical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")
            csv_path = os.path.join(tmpdir, "holidays.csv")

            entries = [
                _make_entry(date(2026, 3, 19), date(2026, 3, 19), "festive", "St Joseph"),
            ]
            save_csv_entries(csv_path, entries)

            _, merged = ensure_csv_from_ics(ics_path, entries)

            self.assertEqual(len(merged), len(entries))

    # ── Scenario 3: CSV exists, ICS has new entries ────────────────────────────

    def test_existing_csv_with_new_ics_entries_no_duplicate(self):
        """CSV has A+B, ICS has B+C — result is A, B, C with no duplicate B."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")
            csv_path = os.path.join(tmpdir, "holidays.csv")

            entry_a = _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "Entry A")
            entry_b = _make_entry(date(2026, 6, 24), date(2026, 6, 24), "festive", "Entry B")
            entry_c = _make_entry(date(2026, 12, 25), date(2026, 12, 25), "festive", "Entry C")

            save_csv_entries(csv_path, [entry_a, entry_b])

            _, merged = ensure_csv_from_ics(ics_path, [entry_b, entry_c])

            self.assertEqual(len(merged), 3)
            names = {e.name for e in merged}
            self.assertIn("Entry A", names)
            self.assertIn("Entry B", names)
            self.assertIn("Entry C", names)

    def test_existing_csv_with_new_ics_entries_sorted(self):
        """Returned list is sorted by (start, end) after merge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")
            csv_path = os.path.join(tmpdir, "holidays.csv")

            entry_a = _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "Entry A")
            entry_b = _make_entry(date(2026, 6, 24), date(2026, 6, 24), "festive", "Entry B")
            entry_c = _make_entry(date(2026, 12, 25), date(2026, 12, 25), "festive", "Entry C")

            save_csv_entries(csv_path, [entry_a, entry_b])

            _, merged = ensure_csv_from_ics(ics_path, [entry_b, entry_c])

            starts = [e.start for e in merged]
            self.assertEqual(starts, sorted(starts))

    def test_existing_csv_with_new_ics_entries_length_is_three(self):
        """Merged list has exactly 3 entries when CSV has A+B and ICS has B+C."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")
            csv_path = os.path.join(tmpdir, "holidays.csv")

            entry_a = _make_entry(date(2026, 2, 14), date(2026, 2, 14), "festive", "Valentine")
            entry_b = _make_entry(date(2026, 4, 23), date(2026, 4, 23), "festive", "St George")
            entry_c = _make_entry(date(2026, 11, 1), date(2026, 11, 1), "festive", "All Saints")

            save_csv_entries(csv_path, [entry_a, entry_b])

            _, merged = ensure_csv_from_ics(ics_path, [entry_b, entry_c])

            self.assertEqual(len(merged), 3)

    # ── Scenario 4: CSV exists, ICS has only new entries ──────────────────────

    def test_existing_csv_ics_completely_different_entries(self):
        """CSV has A; ICS has B and C — merged CSV contains A, B, C."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")
            csv_path = os.path.join(tmpdir, "holidays.csv")

            entry_a = _make_entry(date(2026, 1, 6), date(2026, 1, 6), "festive", "Epiphany")
            entry_b = _make_entry(date(2026, 8, 15), date(2026, 8, 15), "festive", "Assumption")
            entry_c = _make_entry(date(2026, 10, 12), date(2026, 10, 12), "festive", "Columbus Day")

            save_csv_entries(csv_path, [entry_a])

            _, merged = ensure_csv_from_ics(ics_path, [entry_b, entry_c])

            self.assertEqual(len(merged), 3)
            names = {e.name for e in merged}
            self.assertIn("Epiphany", names)
            self.assertIn("Assumption", names)
            self.assertIn("Columbus Day", names)

    # ── Scenario 5: Existing CSV is corrupt / unreadable ──────────────────────

    def test_corrupt_csv_does_not_raise(self):
        """Function does NOT raise when the existing CSV contains garbage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")
            csv_path = os.path.join(tmpdir, "holidays.csv")

            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("THIS IS NOT A VALID CSV\x00\xff\xfe garbage!!!")

            ics_entries = [
                _make_entry(date(2026, 1, 1), date(2026, 1, 1), "festive", "New Year"),
            ]

            try:
                csv_path_out, merged = ensure_csv_from_ics(ics_path, ics_entries)
            except (OSError, IOError, csv.Error) as exc:  # pragma: no cover
                self.fail("ensure_csv_from_ics raised unexpectedly: {}".format(exc))

    def test_corrupt_csv_overwritten_with_ics_entries(self):
        """CSV is overwritten with ICS entries when existing CSV is corrupt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")
            csv_path = os.path.join(tmpdir, "holidays.csv")

            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("GARBAGE DATA THAT IS NOT VALID CSV CONTENT")

            ics_entries = [
                _make_entry(date(2026, 4, 2), date(2026, 4, 2), "festive", "Easter Thursday"),
                _make_entry(date(2026, 4, 3), date(2026, 4, 3), "festive", "Good Friday"),
            ]

            _, merged = ensure_csv_from_ics(ics_path, ics_entries)

            # The corrupt CSV has no valid rows, so existing is treated as empty.
            # All ICS entries are "new" and should be present in the result.
            self.assertEqual(len(merged), 2)
            names = {e.name for e in merged}
            self.assertIn("Easter Thursday", names)
            self.assertIn("Good Friday", names)

    # ── Scenario 6: ICS entries already sorted ────────────────────────────────

    def test_returned_list_sorted_by_start_end(self):
        """Returned list is always sorted by (start_date, end_date)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")

            # Provide entries in reverse order intentionally
            ics_entries = [
                _make_entry(date(2026, 12, 8), date(2026, 12, 8), "festive", "Immaculate Conception"),
                _make_entry(date(2026, 8, 15), date(2026, 8, 15), "festive", "Assumption"),
                _make_entry(date(2026, 1, 6), date(2026, 1, 6), "festive", "Epiphany"),
            ]

            _, merged = ensure_csv_from_ics(ics_path, ics_entries)

            starts = [e.start for e in merged]
            self.assertEqual(starts, sorted(starts))

    def test_returned_list_sorted_by_end_when_same_start(self):
        """When start dates are equal, entries are sorted by end_date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "holidays.ics")

            same_start = date(2026, 7, 1)
            ics_entries = [
                _make_entry(same_start, date(2026, 7, 5), "vacation", "Long Break"),
                _make_entry(same_start, date(2026, 7, 2), "festive", "Short Break"),
            ]

            _, merged = ensure_csv_from_ics(ics_path, ics_entries)

            self.assertEqual(merged[0].end, date(2026, 7, 2))
            self.assertEqual(merged[1].end, date(2026, 7, 5))

    # ── Scenario 7: Empty ICS entries ─────────────────────────────────────────

    def test_empty_ics_entries_creates_csv(self):
        """CSV file is created even when ICS entries list is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "empty.ics")
            expected_csv = os.path.join(tmpdir, "empty.csv")

            csv_path, merged = ensure_csv_from_ics(ics_path, [])

            self.assertEqual(csv_path, expected_csv)
            self.assertTrue(os.path.exists(expected_csv))

    def test_empty_ics_entries_returns_empty_list(self):
        """Returned entries list is empty when ICS entries is empty and no CSV exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "empty.ics")

            _, merged = ensure_csv_from_ics(ics_path, [])

            self.assertEqual(merged, [])

    def test_empty_ics_entries_csv_has_only_header(self):
        """CSV file contains only the header row when ICS entries is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = os.path.join(tmpdir, "empty.ics")

            csv_path, _ = ensure_csv_from_ics(ics_path, [])

            loaded = _load_csv_entries(csv_path)
            self.assertEqual(loaded, [])


if __name__ == "__main__":
    unittest.main()
