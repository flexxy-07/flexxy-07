#!/usr/bin/env python3
"""Generate a monochrome contribution heatmap from a public GitHub profile."""
from __future__ import annotations

import html
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ContributionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: dict[date, tuple[int, int]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "rect":
            return
        values = dict(attrs)
        raw_date = values.get("data-date")
        if not raw_date:
            return
        try:
            day = date.fromisoformat(raw_date)
            level = int(values.get("data-level") or 0)
            count = int(values.get("data-count") or 0)
        except (TypeError, ValueError):
            return
        self.days[day] = (max(0, min(level, 4)), max(0, count))


def get_calendar(username: str) -> dict[date, tuple[int, int]]:
    url = f"https://github.com/users/{username}/contributions"
    request = Request(url, headers={"User-Agent": "flexxy-07-profile-art/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            page = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not retrieve public contribution data: {exc}") from exc

    parser = ContributionParser()
    parser.feed(page)
    if not parser.days:
        # GitHub's accessible labels still expose a date and contribution count if
        # its SVG markup changes; this fallback keeps the scraper failure explicit.
        pairs = re.findall(r"data-date=\"(\d{4}-\d{2}-\d{2})\"[^>]*data-level=\"(\d)\"", page)
        for raw_date, raw_level in pairs:
            parser.days[date.fromisoformat(raw_date)] = (int(raw_level), 0)
    if not parser.days:
        raise RuntimeError("GitHub returned no contribution-calendar day cells; inspect the upstream HTML markup.")
    return parser.days


def month_label(day: date) -> str:
    return day.strftime("%b")


def render(username: str, data: dict[date, tuple[int, int]]) -> str:
    ordered = sorted(data)
    first = ordered[0] - timedelta(days=ordered[0].weekday())
    last = ordered[-1]
    palette = ["#161b22", "#30363d", "#484f58", "#6e7681", "#c9d1d9"]
    cell, gap, left, top = 12, 4, 34, 34
    total_weeks = ((last - first).days // 7) + 1
    width = max(888, left + total_weeks * (cell + gap) + 20)
    height = 158
    total = sum(count for _, count in data.values())
    cells: list[str] = []
    labels: list[str] = []
    for day in ordered:
        if day.day == 1:
            week = (day - first).days // 7
            labels.append(f'<text class="lbl" x="{left + week * (cell + gap)}" y="18">{month_label(day)}</text>')
    for day, (level, count) in sorted(data.items()):
        week = (day - first).days // 7
        weekday = day.weekday()
        x = left + week * (cell + gap)
        y = top + weekday * (cell + gap)
        delay = min(week * 0.018 + weekday * 0.006, 1.2)
        tip = f"{count} contributions on {day.isoformat()}"
        cells.append(
            f'<rect class="day" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{palette[level]}" style="animation-delay:{delay:.3f}s"><title>{html.escape(tip)}</title></rect>'
        )
    weekdays = ''.join(
        f'<text class="lbl" x="2" y="{top + i * (cell + gap) + 10}">{name}</text>'
        for i, name in enumerate(["Mon", "", "Wed", "", "Fri", "", ""])
        if name
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{html.escape(username)} GitHub contributions</title>
<desc id="desc">{total} contributions represented as a monochrome daily activity heatmap.</desc>
<style>
  .lbl {{ fill:#7d8590; font:600 12px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif; }}
  .day {{ opacity:0; transform-box:fill-box; transform-origin:center; animation:pop .45s ease-out forwards; }}
  @keyframes pop {{ 0%{{opacity:0;transform:scale(.35)}} 70%{{opacity:1;transform:scale(1.08)}} 100%{{opacity:1;transform:scale(1)}} }}
  @media (prefers-reduced-motion: reduce) {{ .day {{ opacity:1; animation:none; }} }}
</style>
<rect width="100%" height="100%" rx="8" fill="#0d1117"/>
<text class="lbl" x="{left}" y="18">{total} contributions in the last year · {html.escape(username)}</text>
{''.join(labels)}{weekdays}{''.join(cells)}
</svg>'''


def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else "flexxy-07"
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("contrib-heatmap.svg")
    try:
        calendar = get_calendar(username)
        output.write_text(render(username, calendar), encoding="utf-8")
    except (RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {output} using {len(calendar)} contribution days for {username}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
