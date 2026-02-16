#!/usr/bin/env python3
"""Parse the 2-Year Bible Reading Plan PDF and produce structured JSON.

Also contains calendar-scheduling logic for assigning entries to weekday dates,
skipping weekends, US federal holidays, and personal dates.
"""

import json
import os
import re
from datetime import date, timedelta

import pdfplumber

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_PDF_PATH = os.path.join(
    _PROJECT_ROOT, "2-Year-Bible-Reading-Plan_LisaNotes.com_.pdf"
)
_JSON_PATH = os.path.join(_SCRIPT_DIR, "reading_plan.json")

# ---------------------------------------------------------------------------
# Abbreviation map: PDF abbreviation -> book directory slug
# ---------------------------------------------------------------------------
ABBREV_MAP = {
    "Gen": "genesis",
    "Ex": "exodus",
    "Lev": "leviticus",
    "Num": "numbers",
    "Deut": "deuteronomy",
    "Josh": "joshua",
    "Judg": "judges",
    "Ruth": "ruth",
    "1 Sam": "1samuel",
    "2 Sam": "2samuel",
    "1 Ki": "1kings",
    "2 Ki": "2kings",
    "1 Chr": "1chronicles",
    "2 Chr": "2chronicles",
    "Ezra": "ezra",
    "Neh": "nehemiah",
    "Est": "esther",
    "Job": "job",
    "Ps": "psalms",
    "Prov": "proverbs",
    "Eccl": "ecclesiastes",
    "Song": "songofsolomon",
    "Is": "isaiah",
    "Jer": "jeremiah",
    "Lam": "lamentations",
    "Eze": "ezekiel",
    "Dan": "daniel",
    "Hos": "hosea",
    "Joel": "joel",
    "Amos": "amos",
    "Obad": "obadiah",
    "Jonah": "jonah",
    "Mic": "micah",
    "Nah": "nahum",
    "Habak": "habakkuk",
    "Zeph": "zephaniah",
    "Hag": "haggai",
    "Zech": "zechariah",
    "Mal": "malachi",
    "Matt": "matthew",
    "Mt": "matthew",
    "Mark": "mark",
    "Mk": "mark",
    "Luke": "luke",
    "John": "john",
    "Acts": "acts",
    "Rom": "romans",
    "1 Cor": "1corinthians",
    "2 Cor": "2corinthians",
    "Gal": "galatians",
    "Eph": "ephesians",
    "Phil": "philippians",
    "Col": "colossians",
    "1 Thess": "1thessalonians",
    "2 Thess": "2thessalonians",
    "1 Tim": "1timothy",
    "2 Tim": "2timothy",
    "Tit": "titus",
    "Philm": "philemon",
    "Heb": "hebrews",
    "James": "james",
    "1 Pet": "1peter",
    "2 Pet": "2peter",
    "1 John": "1john",
    "2 John": "2john",
    "3 John": "3john",
    "Jude": "jude",
    "Rev": "revelation",
}

# Sorted longest-first for greedy matching
_SORTED_ABBREVS = sorted(ABBREV_MAP.keys(), key=len, reverse=True)

# Chapter counts per book directory
_CHAPTER_COUNTS = {
    "genesis": 50, "exodus": 40, "leviticus": 27, "numbers": 36,
    "deuteronomy": 34, "joshua": 24, "judges": 21, "ruth": 4,
    "1samuel": 31, "2samuel": 24, "1kings": 22, "2kings": 25,
    "1chronicles": 29, "2chronicles": 36, "ezra": 10, "nehemiah": 13,
    "esther": 10, "job": 42, "psalms": 150, "proverbs": 31,
    "ecclesiastes": 12, "songofsolomon": 8, "isaiah": 66, "jeremiah": 52,
    "lamentations": 5, "ezekiel": 48, "daniel": 12, "hosea": 14,
    "joel": 3, "amos": 9, "obadiah": 1, "jonah": 4, "micah": 7,
    "nahum": 3, "habakkuk": 3, "zephaniah": 3, "haggai": 2,
    "zechariah": 14, "malachi": 4, "matthew": 28, "mark": 16,
    "luke": 24, "john": 21, "acts": 28, "romans": 16,
    "1corinthians": 16, "2corinthians": 13, "galatians": 6,
    "ephesians": 6, "philippians": 4, "colossians": 4,
    "1thessalonians": 5, "2thessalonians": 3, "1timothy": 6,
    "2timothy": 4, "titus": 3, "philemon": 1, "hebrews": 13,
    "james": 5, "1peter": 5, "2peter": 3, "1john": 5, "2john": 1,
    "3john": 1, "jude": 1, "revelation": 22,
}


# ---------------------------------------------------------------------------
# Entry parsing
# ---------------------------------------------------------------------------

def _match_book_abbrev(text):
    """Match a book abbreviation at the start of text.

    Returns (abbrev, book_dir, rest_of_string) or (None, None, text).
    """
    for abbrev in _SORTED_ABBREVS:
        if text.startswith(abbrev):
            rest = text[len(abbrev):]
            # Ensure we matched a complete token (next char is space, digit, dash, or end)
            if rest and rest[0].isalpha():
                continue
            return abbrev, ABBREV_MAP[abbrev], rest.strip()
    return None, None, text


def parse_entry(raw):
    """Parse a single reading-plan entry into a list of segment dicts.

    Each segment: {"book_dir": str, "start_ch": int, "end_ch": int}
    Returns None for markers like "END OF OT".
    """
    raw = raw.strip()
    if not raw or raw in ("END OF OT", "END OF NT"):
        return None

    # Handle combined entries with "/" (e.g., "Mt 28/Mk 16")
    if "/" in raw:
        parts = raw.split("/")
        segments = []
        for part in parts:
            segs = parse_entry(part.strip())
            if segs:
                segments.extend(segs)
        return segments

    # Match the first book abbreviation
    abbrev1, book_dir1, rest1 = _match_book_abbrev(raw)
    if abbrev1 is None:
        print(f"  WARNING: Could not parse entry: {raw!r}")
        return None

    # Check for multi-book range: rest starts with "-" then another book name
    # e.g., "2 John-3 John" → rest1 = "-3 John" after matching "2 John"
    if rest1.startswith("-"):
        possible_rest = rest1[1:].strip()
        abbrev2, book_dir2, rest2 = _match_book_abbrev(possible_rest)
        if abbrev2 is not None:
            # Multi-book range — each book gets its full chapter span
            end2 = int(rest2) if rest2 and rest2.isdigit() else _CHAPTER_COUNTS.get(book_dir2, 1)
            return [
                {"book_dir": book_dir1, "start_ch": 1, "end_ch": _CHAPTER_COUNTS.get(book_dir1, 1)},
                {"book_dir": book_dir2, "start_ch": 1, "end_ch": end2},
            ]

    # No chapter specified — entire book (single-chapter books like Obadiah)
    if not rest1:
        total = _CHAPTER_COUNTS.get(book_dir1, 1)
        return [{"book_dir": book_dir1, "start_ch": 1, "end_ch": total}]

    # Parse chapter range: "1-3", "1", "33-4", "120-134"
    ch_match = re.match(r"^(\d+)(?:-(\d+))?$", rest1)
    if ch_match:
        start_ch = int(ch_match.group(1))
        if ch_match.group(2):
            end_ch = int(ch_match.group(2))
            # Handle truncated ranges: "33-4" means 33-34
            if end_ch < start_ch:
                start_str = str(start_ch)
                end_str = str(end_ch)
                prefix = start_str[: len(start_str) - len(end_str)]
                end_ch = int(prefix + end_str)
        else:
            end_ch = start_ch
        return [{"book_dir": book_dir1, "start_ch": start_ch, "end_ch": end_ch}]

    print(f"  WARNING: Could not parse chapters in: {raw!r} (rest={rest1!r})")
    return None


def extract_entries_from_pdf(pdf_path):
    """Extract reading plan entries from the PDF table.

    Returns list of {"index": int, "raw": str, "segments": [...]}.
    """
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        table = page.extract_table()

    if not table:
        raise RuntimeError("Could not extract table from PDF")

    num_cols = len(table[0]) if table else 0
    entries = []
    idx = 0

    # Read column by column (left→right), row by row (top→bottom).
    # Each cell may contain multiple entries separated by newlines.
    for col in range(num_cols):
        for row in range(len(table)):
            cell = table[row][col]
            if cell is None or not cell.strip():
                continue
            # Split cell into individual lines (entries)
            for line in cell.split("\n"):
                line = line.strip()
                if not line or line in ("END OF OT", "END OF NT"):
                    continue

                segments = parse_entry(line)
                if segments is not None:
                    entries.append({
                        "index": idx,
                        "raw": line,
                        "segments": segments,
                    })
                    idx += 1

    return entries


# ---------------------------------------------------------------------------
# Calendar scheduling
# ---------------------------------------------------------------------------

_holiday_cache = {}


def _nth_weekday(year, month, weekday, n):
    """Find the nth occurrence of a weekday (0=Mon) in a given month."""
    first = date(year, month, 1)
    days_ahead = weekday - first.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_occurrence = first + timedelta(days=days_ahead)
    return first_occurrence + timedelta(weeks=n - 1)


def _last_weekday(year, month, weekday):
    """Find the last occurrence of a weekday (0=Mon) in a given month."""
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    days_back = last_day.weekday() - weekday
    if days_back < 0:
        days_back += 7
    return last_day - timedelta(days=days_back)


def _get_holidays(year):
    """Compute US federal holidays (observed dates) for a given year."""
    holidays = set()

    # Fixed holidays — with weekend observation rules
    fixed = [
        date(year, 1, 1),    # New Year's Day
        date(year, 7, 4),    # Independence Day
        date(year, 11, 11),  # Veterans Day
        date(year, 12, 25),  # Christmas
    ]
    for d in fixed:
        if d.weekday() == 5:      # Saturday → observe Friday
            holidays.add(d - timedelta(days=1))
        elif d.weekday() == 6:    # Sunday → observe Monday
            holidays.add(d + timedelta(days=1))
        else:
            holidays.add(d)

    # Floating holidays
    holidays.add(_nth_weekday(year, 1, 0, 3))    # MLK Day: 3rd Mon Jan
    holidays.add(_nth_weekday(year, 2, 0, 3))    # Presidents' Day: 3rd Mon Feb
    holidays.add(_last_weekday(year, 5, 0))       # Memorial Day: last Mon May
    holidays.add(_nth_weekday(year, 9, 0, 1))     # Labor Day: 1st Mon Sep
    holidays.add(_nth_weekday(year, 10, 0, 2))    # Columbus Day: 2nd Mon Oct

    thanksgiving = _nth_weekday(year, 11, 3, 4)   # Thanksgiving: 4th Thu Nov
    holidays.add(thanksgiving)
    holidays.add(thanksgiving + timedelta(days=1)) # Day after Thanksgiving

    return holidays


def _is_holiday(d):
    year = d.year
    if year not in _holiday_cache:
        _holiday_cache[year] = _get_holidays(year)
    return d in _holiday_cache[year]


# Personal skip dates (month, day) — applied every year
_PERSONAL_SKIPS = {(2, 24), (2, 27), (3, 6), (6, 23)}


def _is_available(d):
    """Return True if a date is available for a reading assignment."""
    if d.weekday() >= 5:  # Saturday or Sunday
        return False
    if (d.month, d.day) in _PERSONAL_SKIPS:
        return False
    if _is_holiday(d):
        return False
    return True


def schedule_plan(entries, start_date):
    """Assign a calendar date to each reading-plan entry.

    Returns a new list of dicts enriched with date/month/label info.
    """
    scheduled = []
    current = start_date

    for entry in entries:
        while not _is_available(current):
            current += timedelta(days=1)

        month_key = current.strftime("%B %Y")
        day_label = current.strftime("%a, %b ") + str(current.day)
        date_str = current.isoformat()

        scheduled.append({
            **entry,
            "date": date_str,
            "month_key": month_key,
            "day_label": day_label,
        })
        current += timedelta(days=1)

    return scheduled


def build_plan_endpoints(scheduled_entries):
    """Build a lookup of chapter endpoints → plan anchor IDs.

    Returns {(book_dir, end_ch): [anchor_id, ...]}
    """
    endpoints = {}
    for entry in scheduled_entries:
        anchor = f"rp-{entry['date']}"
        for seg in entry["segments"]:
            key = (seg["book_dir"], seg["end_ch"])
            endpoints.setdefault(key, []).append(anchor)
    return endpoints


# ---------------------------------------------------------------------------
# CLI — standalone testing
# ---------------------------------------------------------------------------

def main():
    if os.path.isfile(_JSON_PATH):
        print(f"Loading cached plan from {_JSON_PATH}")
        with open(_JSON_PATH, "r", encoding="utf-8") as f:
            entries = json.load(f)
    else:
        print(f"Parsing PDF: {_PDF_PATH}")
        entries = extract_entries_from_pdf(_PDF_PATH)
        with open(_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        print(f"Wrote {len(entries)} entries to {_JSON_PATH}")

    print(f"\nTotal entries: {len(entries)}")
    print(f"First: {entries[0]}")
    print(f"Last:  {entries[-1]}")

    # Quick schedule test
    from datetime import date as date_cls
    scheduled = schedule_plan(entries, date_cls(2026, 3, 2))
    print(f"\nSchedule spans {scheduled[0]['date']} to {scheduled[-1]['date']}")

    endpoints = build_plan_endpoints(scheduled)
    print(f"Endpoint chapters: {len(endpoints)}")

    # Verify no weekends or holidays in schedule
    for e in scheduled:
        d = date_cls.fromisoformat(e["date"])
        assert d.weekday() < 5, f"Weekend date: {d}"
        assert not _is_holiday(d), f"Holiday date: {d}"
        assert (d.month, d.day) not in _PERSONAL_SKIPS, f"Personal skip: {d}"
    print("All dates valid (no weekends/holidays/personal skips)")


if __name__ == "__main__":
    main()
