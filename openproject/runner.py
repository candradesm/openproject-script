"""Core runner shared by both interactive and flag-based modes."""
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from openproject.theme import (
    _t, _c,
    log_ok, log_skip, log_error, log_dry, log_section,
    GREEN, YELLOW, RED,
)
from openproject.dates import is_weekend, _parse_iso_duration, hours_to_iso8601
from openproject.client import OpenProjectClient


def run(
    client: OpenProjectClient,
    work_package_id: int,
    user_id: int,
    activity_id: int,
    hours: float,
    comment: str,
    candidates: List[date],
    dry_run: bool,
    special_days: Optional[Dict[date, Tuple[str, str]]] = None,
    festive_activity_id:  Optional[int] = None,
    vacation_activity_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute the time-entry logging loop for the given dates.
    Returns a stats dict so callers can inspect results.
    """
    if dry_run:
        _dry_msg = _t("DRY-RUN MODE — no bananzas will be created (yet).", "DRY-RUN — no entries will be created.")
        log_dry(_dry_msg)

    stats = {
        "created": 0,
        "skipped_weekend":  0,
        "skipped_existing": 0,
        "skipped_festive":  0,
        "skipped_vacation": 0,
        "failed": 0,
    }

    log_section(_t("🍌 Processing dates:", "Processing dates:"))

    sd = special_days or {}

    for d in candidates:
        date_str = d.isoformat()

        # ── Special day check (before weekend) ────────────────────────────────
        if d in sd:
            day_type, day_name = sd[d]
            activity_override = (
                festive_activity_id  if day_type == "festive"  else
                vacation_activity_id
            )
            if activity_override is None:
                log_skip(
                    f"{date_str}  ({d.strftime('%A')}) — "
                    f"{day_type}: {day_name}, skipping."
                )
                stats[f"skipped_{day_type}"] += 1
                continue
            # Use the override activity for this date
            effective_activity_id = activity_override
        else:
            effective_activity_id = activity_id

        # ── Weekend check ──────────────────────────────────────────────────────
        if is_weekend(d):
            _wknd = _t("🌴 weekend, this monke is chilling.", "weekend, skipping.")
            log_skip(f"{date_str}  ({d.strftime('%A')}) — {_wknd}")
            stats["skipped_weekend"] += 1
            continue

        # ── Existing entries check ─────────────────────────────────────────────
        try:
            existing = client.get_existing_entries_for_date(user_id, d)
        except RuntimeError as e:
            _chk_fail = _t("🙊 failed to check existing entries:", "failed to check existing entries:")
            log_error(f"{date_str} — {_chk_fail} {e}")
            stats["failed"] += 1
            continue

        if existing:
            total_h  = sum(_parse_iso_duration(e.get("hours", "PT0H")) for e in existing)
            _already = _t("🙈 already has", "already has")
            log_skip(
                f"{date_str} — {_already} {len(existing)} entry/entries "
                f"({total_h:.1f}h total), skipping."
            )
            stats["skipped_existing"] += 1
            continue

        # ── Create entry ───────────────────────────────────────────────────────
        if dry_run:
            _would = _t("🍌 would log", "would log")
            log_dry(f"{date_str} — {_would} {hours}h on work package #{work_package_id}.")
            stats["created"] += 1
            continue

        try:
            created = client.create_time_entry(
                work_package_id=work_package_id,
                user_id=user_id,
                activity_id=effective_activity_id,
                spent_on=d,
                hours=hours,
                comment=comment,
            )
            _logged = _t("🍌 bananza logged! Entry #", "created entry #")
            log_ok(f"{date_str} — {_logged}{created.get('id', '?')}  ({hours}h).")
            stats["created"] += 1
        except RuntimeError as e:
            _log_fail = _t("🙊 failed to log entry:", "failed to log entry:")
            log_error(f"{date_str} — {_log_fail} {e}")
            stats["failed"] += 1

    return stats


def print_summary(stats: Dict[str, Any], dry_run: bool) -> None:
    action_label = "Would log  " if dry_run else "Logged     "
    log_section(_t("🍌 Bananza Report:", "Summary:"))
    print(f"  {_t('🍌', _c(GREEN, '✔'))}  {action_label}      : {stats['created']}")
    print(f"  {_t('🌴', _c(YELLOW, '⏭'))}  Skipped (weekend)  : {stats['skipped_weekend']}")
    print(f"  {_t('🙈', _c(YELLOW, '⏭'))}  Skipped (existing) : {stats['skipped_existing']}")
    if stats.get("skipped_festive"):
        print(f"  {_t('🎉', _c(YELLOW, '⏭'))}  Skipped (festive)  : {stats['skipped_festive']}")
    if stats.get("skipped_vacation"):
        print(f"  {_t('🏖', _c(YELLOW, '⏭'))}  Skipped (vacation) : {stats['skipped_vacation']}")
    if stats["failed"]:
        print(f"  {_t('🙊', _c(RED, '✘'))}  Failed             : {stats['failed']}")
    print()
