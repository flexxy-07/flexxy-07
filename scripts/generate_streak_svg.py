#!/usr/bin/env python3
"""Generate a monochrome contribution heatmap from a public GitHub profile."""
from __future__ import annotations

import html
import re
import sys
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ContributionParser(HTMLParser):
    """Parse GitHub's current HTML contribution calendar.

    GitHub renders each day as a <td data-date=... data-level=...> and exposes
    the exact contribution count in a separate <tool-tip for="cell-id"> tag.
    Older SVG-style rect.day markup is supported as well.
    """

    def __init__(self) -> None:
        super().__init__()
        self.days: dict[date, tuple[int, int]] = {}
        self._cell_ids: dict[str, date] = {}
        self._explicit_count_days: set[date] = set()
        self._tooltip_counts: dict[str, int] = {}
        self._active_tooltip_id: str | None = None
        self._active_tooltip_text: list[str] = []

    @staticmethod
    def _safe_int(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value.replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = dict(attrs)

        if tag in {"rect", "td"}:
            raw_date = values.get("data-date")
            if raw_date:
                try:
                    day = date.fromisoformat(raw_date)
                    level_value = self._safe_int(values.get("data-level"))
                    if level_value is None:
                        return
                    level = max(0, min(level_value, 4))
                    count_value = self._safe_int(values.get("data-count"))
                    count = max(0, count_value or 0)
                    self.days[day] = (level, count)
                    if count_value is not None:
                        self._explicit_count_days.add(day)
                    cell_id = values.get("id")
                    if tag == "td" and cell_id:
                        self._cell_ids[cell_id] = day
                except ValueError:
                    return

        elif tag == "tool-tip":
            self._active_tooltip_id = values.get("for")
            self._active_tooltip_text = []

    def handle_data(self, data: str) -> None:
        if self._active_tooltip_id:
            self._active_tooltip_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "tool-tip" or not self._active_tooltip_id:
            return

        tooltip_text = " ".join(self._active_tooltip_text)
        match = re.search(r"\b([\d,]+)\s+contributions?\b", tooltip_text, re.IGNORECASE)
        if match:
            self._tooltip_counts[self._active_tooltip_id] = int(match.group(1).replace(",", ""))
        elif re.search(r"\bno contributions?\b", tooltip_text, re.IGNORECASE):
            self._tooltip_counts[self._active_tooltip_id] = 0

        self._active_tooltip_id = None
        self._active_tooltip_text = []

    def finalize(self) -> None:
        for cell_id, day in self._cell_ids.items():
            if cell_id in self._tooltip_counts:
                level, _ = self.days[day]
                self.days[day] = (level, self._tooltip_counts[cell_id])
                self._explicit_count_days.add(day)

        # Never silently show zero for active days if GitHub changed tooltip markup.
        unresolved_active = [
            day.isoformat()
            for day, (level, _count) in self.days.items()
            if level > 0 and day not in self._explicit_count_days
        ]
        if unresolved_active:
            sample = ", ".join(unresolved_active[:3])
            raise RuntimeError(
                "GitHub returned active contribution days but their counts could not "
                f"be read from tooltips (for example: {sample}). The graph was not overwritten."
            )


def get_calendar(username: str) -> dict[date, tuple[int, int]]:
    url = f"https://github.com/users/{username}/contributions"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; flexxy-07-profile-art/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            page = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not retrieve public contribution data: {exc}") from exc

    parser = ContributionParser()
    parser.feed(page)
    parser.close()

    # Fallback for GitHub's older SVG calendar markup. It contains real levels;
    # counts are only accepted when data-count is actually present.
    if not parser.days:
        pairs = re.findall(
            r'<(?:td|rect)\b([^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*)>',
            page,
            re.IGNORECASE,
        )
        for attrs_text, raw_date in pairs:
            level_match = re.search(r'data-level="(\d)"', attrs_text)
            count_match = re.search(r'data-count="([\d,]+)"', attrs_text)
            if not level_match:
                continue
            count = int(count_match.group(1).replace(",", "")) if count_match else 0
            parser.days[date.fromisoformat(raw_date)] = (min(int(level_match.group(1)), 4), count)
            if count_match:
                parser._explicit_count_days.add(date.fromisoformat(raw_date))

    parser.finalize()
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
    total = sum(count for _, count in calendar.values())
    active_days = sum(1 for level, _ in calendar.values() if level > 0)
    print(f"Wrote {output} using {len(calendar)} days, {active_days} active days, and {total} contributions for {username}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
