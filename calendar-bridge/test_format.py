"""Unit tests for the when-formatter. Run on the VM / any Python env:
    pip install tzdata && python -m pytest test_format.py -q
(The container running this repo's Claude session has no Python, so these are
executed on the VM, not in that container.)
"""
import datetime
from zoneinfo import ZoneInfo

from bridge import format_when

TZ = ZoneInfo("Australia/Perth")
NOW = datetime.datetime(2026, 10, 17, 9, 0, tzinfo=TZ)  # Fri 17 Oct


def at(y, m, d, hh=0, mm=0):
    return datetime.datetime(y, m, d, hh, mm, tzinfo=TZ)


def test_timed_today():
    assert format_when(at(2026, 10, 17, 18, 30), NOW, False) == "Today 18:30"


def test_timed_tomorrow():
    assert format_when(at(2026, 10, 18, 9, 0), NOW, False) == "Tomorrow 09:00"


def test_timed_thisweek():
    assert format_when(at(2026, 10, 19, 9, 0), NOW, False) == "Sun 09:00"


def test_timed_far():
    assert format_when(at(2026, 10, 30, 9, 0), NOW, False) == "30 Oct 09:00"


def test_allday_today():
    assert format_when(at(2026, 10, 17), NOW, True) == "Today"


def test_allday_far():
    assert format_when(at(2026, 10, 20), NOW, True) == "Mon 20 Oct"
