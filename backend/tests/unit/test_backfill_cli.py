"""The backfill script must be safe by default: it only writes with --apply."""

from __future__ import annotations

import pytest

from scripts import backfill_job_cache_descriptions as backfill


def test_default_invocation_is_a_dry_run() -> None:
    args = backfill.parse_args([])
    assert args.apply is False


def test_apply_flag_enables_writes() -> None:
    assert backfill.parse_args(["--apply"]).apply is True


def test_dry_run_flag_is_still_accepted_and_does_not_write() -> None:
    assert backfill.parse_args(["--dry-run"]).apply is False


def test_dry_run_and_apply_conflict() -> None:
    with pytest.raises(SystemExit):
        backfill.parse_args(["--dry-run", "--apply"])


def test_other_options_pass_through() -> None:
    args = backfill.parse_args(["--limit", "5", "--batch-size", "10", "--career-job-cache", "--all"])
    assert (args.limit, args.batch_size, args.career_job_cache, args.all) == (5, 10, True, True)
