"""Unit tests for openproject.runner module."""
import io
import sys
import unittest
from datetime import date

from openproject.runner import run, print_summary


# ── Mock client ────────────────────────────────────────────────────────────────

class MockClient:
    """Records calls and returns configurable fake responses."""

    def __init__(self):
        self.created = []       # list of dicts with kwargs passed to create_time_entry
        self.existing = {}      # dict[date, list] — return existing entries per date

    def get_existing_entries_for_date(self, user_id, spent_on):
        return self.existing.get(spent_on, [])

    def create_time_entry(self, work_package_id, user_id, activity_id, spent_on, hours, comment):
        self.created.append({
            "work_package_id": work_package_id,
            "user_id": user_id,
            "activity_id": activity_id,
            "spent_on": spent_on,
            "hours": hours,
            "comment": comment,
        })
        return {"id": len(self.created)}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(candidates, client=None, special_days=None, dry_run=False,
         festive_activity_id=None, vacation_activity_id=None,
         activity_id=3, hours=8.0):
    """Convenience wrapper around run() with sensible defaults."""
    if client is None:
        client = MockClient()
    return run(
        client=client,
        work_package_id=100,
        user_id=1,
        activity_id=activity_id,
        hours=hours,
        comment="test",
        candidates=candidates,
        dry_run=dry_run,
        special_days=special_days,
        festive_activity_id=festive_activity_id,
        vacation_activity_id=vacation_activity_id,
    )


# ── 2026 reference dates ───────────────────────────────────────────────────────
# 2026-04-18 Saturday, 2026-04-19 Sunday, 2026-04-20 Monday (weekday)

SAT = date(2026, 4, 18)   # Saturday
SUN = date(2026, 4, 19)   # Sunday
MON = date(2026, 4, 20)   # Monday (weekday)
TUE = date(2026, 4, 21)   # Tuesday (weekday)


# ══════════════════════════════════════════════════════════════════════════════
# TestRunWeekendSkip
# ══════════════════════════════════════════════════════════════════════════════

class TestRunWeekendSkip(unittest.TestCase):

    def test_saturday_skipped(self):
        stats = _run([SAT])
        self.assertEqual(stats["skipped_weekend"], 1)
        self.assertEqual(stats["created"], 0)

    def test_sunday_skipped(self):
        stats = _run([SUN])
        self.assertEqual(stats["skipped_weekend"], 1)
        self.assertEqual(stats["created"], 0)

    def test_weekday_not_skipped(self):
        stats = _run([MON])
        self.assertEqual(stats["skipped_weekend"], 0)
        self.assertEqual(stats["created"], 1)


# ══════════════════════════════════════════════════════════════════════════════
# TestRunExistingEntries
# ══════════════════════════════════════════════════════════════════════════════

class TestRunExistingEntries(unittest.TestCase):

    def test_existing_entry_skipped(self):
        client = MockClient()
        client.existing[MON] = [{"hours": "PT8H"}]
        stats = _run([MON], client=client)
        self.assertEqual(stats["skipped_existing"], 1)
        self.assertEqual(stats["created"], 0)
        self.assertEqual(len(client.created), 0)

    def test_no_existing_proceeds(self):
        client = MockClient()
        client.existing[MON] = []
        stats = _run([MON], client=client)
        self.assertEqual(stats["skipped_existing"], 0)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(len(client.created), 1)


# ══════════════════════════════════════════════════════════════════════════════
# TestRunSpecialDays
# ══════════════════════════════════════════════════════════════════════════════

class TestRunSpecialDays(unittest.TestCase):

    def test_festive_skipped_no_activity(self):
        sd = {MON: ("festive", "Public Holiday")}
        stats = _run([MON], special_days=sd, festive_activity_id=None)
        self.assertEqual(stats["skipped_festive"], 1)
        self.assertEqual(stats["created"], 0)

    def test_vacation_skipped_no_activity(self):
        sd = {MON: ("vacation", "Annual Leave")}
        stats = _run([MON], special_days=sd, vacation_activity_id=None)
        self.assertEqual(stats["skipped_vacation"], 1)
        self.assertEqual(stats["created"], 0)

    def test_festive_with_activity_override(self):
        client = MockClient()
        sd = {MON: ("festive", "Public Holiday")}
        stats = _run([MON], client=client, special_days=sd, festive_activity_id=5)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["skipped_festive"], 0)
        self.assertEqual(client.created[0]["activity_id"], 5)

    def test_vacation_with_activity_override(self):
        client = MockClient()
        sd = {MON: ("vacation", "Annual Leave")}
        stats = _run([MON], client=client, special_days=sd, vacation_activity_id=7)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["skipped_vacation"], 0)
        self.assertEqual(client.created[0]["activity_id"], 7)

    def test_normal_day_uses_regular_activity(self):
        client = MockClient()
        stats = _run([MON], client=client, activity_id=3)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(client.created[0]["activity_id"], 3)

    def test_special_day_checked_before_weekend(self):
        """A Saturday that is also a festive day should be counted as skipped_festive,
        not skipped_weekend, because the special day check runs first in run()."""
        sd = {SAT: ("festive", "Holiday on Saturday")}
        stats = _run([SAT], special_days=sd, festive_activity_id=None)
        self.assertEqual(stats["skipped_festive"], 1)
        self.assertEqual(stats["skipped_weekend"], 0)


# ══════════════════════════════════════════════════════════════════════════════
# TestRunDryRun
# ══════════════════════════════════════════════════════════════════════════════

class TestRunDryRun(unittest.TestCase):

    def test_dry_run_no_api_calls(self):
        client = MockClient()
        stats = _run([MON], client=client, dry_run=True)
        self.assertEqual(len(client.created), 0)
        self.assertGreater(stats["created"], 0)

    def test_dry_run_counts_created(self):
        client = MockClient()
        stats = _run([MON], client=client, dry_run=True)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(len(client.created), 0)


# ══════════════════════════════════════════════════════════════════════════════
# TestRunFailedEntry
# ══════════════════════════════════════════════════════════════════════════════

class _ErrorOnCreateClient(MockClient):
    """Raises RuntimeError on create_time_entry."""

    def create_time_entry(self, **kwargs):
        raise RuntimeError("API exploded")


class _ErrorOnCheckClient(MockClient):
    """Raises RuntimeError on get_existing_entries_for_date."""

    def get_existing_entries_for_date(self, user_id, spent_on):
        raise RuntimeError("Check failed")


class TestRunFailedEntry(unittest.TestCase):

    def test_api_error_counted(self):
        client = _ErrorOnCreateClient()
        stats = _run([MON], client=client)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["created"], 0)

    def test_check_error_counted(self):
        client = _ErrorOnCheckClient()
        stats = _run([MON], client=client)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["created"], 0)


# ══════════════════════════════════════════════════════════════════════════════
# TestRunStats
# ══════════════════════════════════════════════════════════════════════════════

class TestRunStats(unittest.TestCase):

    def test_stats_keys_present(self):
        stats = _run([MON])
        expected_keys = {
            "created",
            "skipped_weekend",
            "skipped_existing",
            "skipped_festive",
            "skipped_vacation",
            "failed",
        }
        self.assertEqual(set(stats.keys()), expected_keys)

    def test_multiple_dates_stats(self):
        """Mixed range: weekday, weekend, existing, festive (skipped), vacation (logged)."""
        # MON  → normal weekday → created
        # TUE  → existing entry → skipped_existing
        # SAT  → weekend → skipped_weekend
        # WED  → festive, no override → skipped_festive
        # THU  → vacation, with override → created
        WED = date(2026, 4, 22)
        THU = date(2026, 4, 23)

        client = MockClient()
        client.existing[TUE] = [{"hours": "PT8H"}]

        sd = {
            WED: ("festive", "Local Holiday"),
            THU: ("vacation", "Annual Leave"),
        }

        stats = _run(
            [MON, TUE, SAT, WED, THU],
            client=client,
            special_days=sd,
            festive_activity_id=None,
            vacation_activity_id=7,
        )

        self.assertEqual(stats["created"], 2)           # MON + THU
        self.assertEqual(stats["skipped_weekend"], 1)   # SAT
        self.assertEqual(stats["skipped_existing"], 1)  # TUE
        self.assertEqual(stats["skipped_festive"], 1)   # WED
        self.assertEqual(stats["skipped_vacation"], 0)  # THU was logged (override)
        self.assertEqual(stats["failed"], 0)


# ══════════════════════════════════════════════════════════════════════════════
# TestPrintSummary
# ══════════════════════════════════════════════════════════════════════════════

class TestPrintSummary(unittest.TestCase):
    """Smoke tests for print_summary — verifies it runs without error and
    produces output containing the key counts."""

    def _capture(self, stats, dry_run=False):
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            print_summary(stats, dry_run=dry_run)
        finally:
            sys.stdout = old_stdout
        return buf.getvalue()

    def _make_stats(self, created=0, skipped_weekend=0, skipped_existing=0,
                    skipped_festive=0, skipped_vacation=0, failed=0):
        return {
            "created": created,
            "skipped_weekend": skipped_weekend,
            "skipped_existing": skipped_existing,
            "skipped_festive": skipped_festive,
            "skipped_vacation": skipped_vacation,
            "failed": failed,
        }

    def test_print_summary_runs_without_error(self):
        stats = self._make_stats(created=3, skipped_weekend=2)
        output = self._capture(stats)
        self.assertIsInstance(output, str)
        self.assertGreater(len(output), 0)

    def test_print_summary_shows_created_count(self):
        stats = self._make_stats(created=5)
        output = self._capture(stats)
        self.assertIn("5", output)

    def test_print_summary_dry_run_label(self):
        stats = self._make_stats(created=2)
        output = self._capture(stats, dry_run=True)
        self.assertIn("Would log", output)

    def test_print_summary_festive_shown_when_nonzero(self):
        stats = self._make_stats(skipped_festive=3)
        output = self._capture(stats)
        self.assertIn("3", output)

    def test_print_summary_vacation_shown_when_nonzero(self):
        stats = self._make_stats(skipped_vacation=2)
        output = self._capture(stats)
        self.assertIn("2", output)

    def test_print_summary_failed_shown_when_nonzero(self):
        stats = self._make_stats(failed=1)
        output = self._capture(stats)
        self.assertIn("1", output)


if __name__ == "__main__":
    unittest.main()
