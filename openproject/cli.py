"""CLI argument parser, validator, and main entry point."""
import argparse
import os
import sys
from datetime import date
from typing import Dict, List, Optional, Tuple

from openproject import theme
from openproject.prompts import prompt_bool
from openproject.dates import parse_date_arg, date_range, hours_to_iso8601
from openproject.special_days import load_special_day_entries, expand_entries
from openproject.client import OpenProjectClient
from openproject.runner import run, print_summary
from openproject.interactive import interactive_mode


_CLI_EPILOG = """\
Flag-based usage examples:
  # Single date
  python3 openproject_time_entry.py \\
    --base-url https://openproject.napptilus.com \\
    --api-key YOUR_API_KEY \\
    --work-package-id 1296 \\
    --user-id 137 \\
    --date 2026-03-12

  # Date range
  python3 openproject_time_entry.py \\
    --base-url https://openproject.napptilus.com \\
    --api-key YOUR_API_KEY \\
    --work-package-id 1296 \\
    --user-id 137 \\
    --start-date 2026-03-01 \\
    --end-date 2026-03-31 \\
    --hours 8 \\
    --activity-id 3 \\
    --comment "Development work"

  # With special days (festives skipped, vacations logged as activity 5)
  python3 openproject_time_entry.py ... \\
    --special-days-file festives.csv \\
    --vacation-activity-id 5

  # Dry-run preview
  python3 openproject_time_entry.py ... --dry-run

  # Environment variables (also pre-fill interactive prompts):
  export OPENPROJECT_BASE_URL=https://openproject.napptilus.com
  export OPENPROJECT_API_KEY=your_token_here
"""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Log time entries in OpenProject.\n"
            "Run with no arguments to start the interactive session."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_CLI_EPILOG,
    )

    conn = parser.add_argument_group("Connection")
    conn.add_argument("--base-url", default=os.environ.get("OPENPROJECT_BASE_URL"),
                      metavar="URL",
                      help="Instance base URL (or set OPENPROJECT_BASE_URL env var).")
    conn.add_argument("--api-key",  default=os.environ.get("OPENPROJECT_API_KEY"),
                      metavar="TOKEN",
                      help="API access token (or set OPENPROJECT_API_KEY env var).")
    conn.add_argument("--insecure", action="store_true",
                      default=os.environ.get("OPENPROJECT_INSECURE", "0").strip() == "1",
                      help="Skip SSL certificate verification (for self-signed certs)."
                           " Or set OPENPROJECT_INSECURE=1.")

    entry = parser.add_argument_group("Time entry details")
    entry.add_argument("--work-package-id", type=int, default=None,   metavar="ID")
    entry.add_argument("--user-id",         type=int, default=None,   metavar="ID",
                       help="User ID. Auto-detected from API key if omitted.")
    entry.add_argument("--activity-id",     type=int, default=3,      metavar="ID")
    entry.add_argument("--hours",           type=float, default=8.0,  metavar="N")
    entry.add_argument("--comment",         default="",               metavar="TEXT")

    date_group = parser.add_argument_group("Date selection (choose one mode)")
    mode = date_group.add_mutually_exclusive_group(required=False)
    mode.add_argument("--date",       type=parse_date_arg, metavar="YYYY-MM-DD")
    mode.add_argument("--start-date", type=parse_date_arg, metavar="YYYY-MM-DD")
    parser.add_argument("--end-date", type=parse_date_arg, metavar="YYYY-MM-DD")

    special = parser.add_argument_group("Special days")
    special.add_argument(
        "--special-days-file", metavar="PATH",
        help="CSV or ICS file containing festives and vacations. "
             "CSV (read/write) is preferred; ICS is read-only.",
    )
    special.add_argument(
        "--festive-activity-id", type=int, default=None, metavar="ID",
        help="Activity ID to use for festive days. If omitted, festive days are skipped.",
    )
    special.add_argument(
        "--vacation-activity-id", type=int, default=None, metavar="ID",
        help="Activity ID to use for vacation days. If omitted, vacation days are skipped.",
    )

    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--monke", action="store_true",
        help="Enable monkey-themed output (or set MONKE_THEME=1).",
    )

    return parser


def validate_flag_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not args.base_url:
        parser.error("--base-url is required (or set OPENPROJECT_BASE_URL).")
    if not args.api_key:
        parser.error("--api-key is required (or set OPENPROJECT_API_KEY).")
    if args.work_package_id is None:
        parser.error("--work-package-id is required in flag mode.")
    if not args.date and not args.start_date:
        parser.error("--date or --start-date is required in flag mode.")
    if args.start_date and not args.end_date:
        parser.error("--end-date is required when --start-date is provided.")
    if args.end_date and not args.start_date:
        parser.error("--start-date is required when --end-date is provided.")
    if args.start_date and args.end_date and args.start_date > args.end_date:
        parser.error("--start-date must be ≤ --end-date.")
    if args.hours <= 0:
        parser.error("--hours must be a positive number.")


def main() -> None:
    parser = build_arg_parser()
    args   = parser.parse_args()

    # Propagate monke theme via set_monke so all modules see the updated value
    if args.monke:
        theme.set_monke(True)

    if args.work_package_id is None:
        interactive_mode(
            insecure=args.insecure,
            special_days_file=args.special_days_file if hasattr(args, "special_days_file") else None,
        )
        return

    validate_flag_args(args, parser)

    # Resolve user ID (auto-detect if not provided)
    client  = OpenProjectClient(args.base_url, args.api_key, insecure=args.insecure)
    user_id = args.user_id
    if user_id is None:
        try:
            me      = client.get_current_user()
            user_id = me.get("id")
            if not user_id:
                raise RuntimeError("Empty user ID in response.")
            theme.log_ok(theme._t(f"🍌 Auto-detected user: {me.get('name')}  (ID: {user_id})", f"Auto-detected user: {me.get('name')}  (ID: {user_id})"))
        except RuntimeError as e:
            theme.log_error(theme._t("🙊 Error: could not auto-detect user ID, monke!", "Error: could not auto-detect user ID:") + f" {e}")
            theme.log_error(theme._t("🙊 Provide --user-id explicitly, monke!", "Provide --user-id explicitly."))
            sys.exit(1)

    if args.date:
        candidates = [args.date]
    else:
        candidates = date_range(args.start_date, args.end_date)

    # Load special days file if provided
    special_days: Dict[date, Tuple[str, str]] = {}
    if args.special_days_file:
        try:
            entries      = load_special_day_entries(args.special_days_file)
            special_days = expand_entries(entries)
            theme.log_info(
                f"Special days  : {len(entries)} entry/entries "
                f"from {args.special_days_file}"
            )
        except (OSError, IOError, ValueError) as exc:
            theme.log_error(theme._t(
                f"🙊 Could not load special days file: {exc}",
                f"Could not load special days file: {exc}"
            ))
            sys.exit(1)

    theme.log_section(theme._t("🐵 Monke Time Logger — OpenProject API v3 🍌", "OpenProject Time Entry Logger"))
    if args.insecure:
        theme.log_error(theme._t(
            "🙊 SSL verification disabled — connection is not fully secure.",
            "SSL verification disabled — connection is not fully secure.",
        ))
    theme.log_info(f"Base URL      : {args.base_url}")
    theme.log_info(f"Work Package  : #{args.work_package_id}")
    theme.log_info(f"User ID       : {user_id}")
    theme.log_info(f"Activity ID   : {args.activity_id}")
    theme.log_info(f"Hours/day     : {args.hours}h  →  {hours_to_iso8601(args.hours)}")
    theme.log_info(f"Comment       : '{args.comment}'" if args.comment else "Comment       : (none)")
    theme.log_info(f"Dates         : {candidates[0]} → {candidates[-1]}  ({len(candidates)} day(s))")
    if special_days:
        festive_count  = sum(1 for t, _ in special_days.values() if t == "festive")
        vacation_count = sum(1 for t, _ in special_days.values() if t == "vacation")
        theme.log_info(
            f"Special days  : {festive_count} festive day(s), "
            f"{vacation_count} vacation day(s) in loaded file"
        )
        if args.festive_activity_id:
            theme.log_info(f"Festive act.  : #{args.festive_activity_id}")
        else:
            theme.log_info("Festive act.  : skip")
        if args.vacation_activity_id:
            theme.log_info(f"Vacation act. : #{args.vacation_activity_id}")
        else:
            theme.log_info("Vacation act. : skip")

    stats = run(
        client=client,
        work_package_id=args.work_package_id,
        user_id=user_id,
        activity_id=args.activity_id,
        hours=args.hours,
        comment=args.comment,
        candidates=candidates,
        dry_run=args.dry_run,
        special_days=special_days,
        festive_activity_id=args.festive_activity_id,
        vacation_activity_id=args.vacation_activity_id,
    )
    print_summary(stats, args.dry_run)

    if args.dry_run and stats["created"] > 0:
        go_real = prompt_bool(
            theme._t("🍌 Looks good — run for real?", "Looks good — execute for real?"),
            default=True,
        )
        if go_real:
            stats = run(
                client=client,
                work_package_id=args.work_package_id,
                user_id=user_id,
                activity_id=args.activity_id,
                hours=args.hours,
                comment=args.comment,
                candidates=candidates,
                dry_run=False,
                special_days=special_days,
                festive_activity_id=args.festive_activity_id,
                vacation_activity_id=args.vacation_activity_id,
            )
            print_summary(stats, dry_run=False)

    if stats["failed"]:
        sys.exit(1)
