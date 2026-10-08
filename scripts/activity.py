"""The activity card: a year of contributions, the totals and the streaks.

    GITHUB_TOKEN=... python scripts/activity.py     (or with `gh` logged in)

Our own, in moncef.net's design, instead of a third-party stats service: the
contribution calendar comes from GitHub's GraphQL API for every year since the
account opened, and the card is drawn light and dark into assets/. The
workflow in .github/workflows/activity.yml runs this every day and commits the
card when it changed.
"""
import datetime as dt, json, os, subprocess, urllib.request
from build import (ORANGE, THEMES, W, cross, embed, esc, fam, measure, oklch, svg, write)

USER = "modecode22"

# The site's orange ramp for the heatmap; the first step is an empty day.
P = {k: oklch(*v) for k, v in {
    100: (0.94, 0.05, 38), 200: (0.88, 0.1, 38), 300: (0.8, 0.15, 38), 400: (0.72, 0.19, 38),
    500: (0.66, 0.22, 38), 700: (0.49, 0.18, 38), 800: (0.42, 0.15, 38), 900: (0.35, 0.115, 38),
}.items()}
RAMP = {
    "light": [THEMES["light"]["rule"], P[200], P[300], P[500], P[700]],
    "dark": [THEMES["dark"]["rule"], P[900], P[700], P[500], P[300]],
}


def token():
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def graphql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        body = json.load(res)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]


CALENDAR = """query($login:String!,$from:DateTime,$to:DateTime){user(login:$login){createdAt
contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""


def days():
    """Every day since the account opened, date -> count."""
    first = graphql(CALENDAR, login=USER)["user"]
    created = dt.date.fromisoformat(first["createdAt"][:10])
    today = dt.datetime.now(dt.timezone.utc).date()
    counts = {}
    start = created
    while start <= today:
        end = min(start.replace(year=start.year + 1) - dt.timedelta(days=1), today)
        data = graphql(CALENDAR, login=USER, **{"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"})
        for week in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                counts[dt.date.fromisoformat(d["date"])] = d["contributionCount"]
        start = end + dt.timedelta(days=1)
    return {d: c for d, c in counts.items() if created <= d <= today}, created, today


def streaks(counts, today):
    ordered = sorted(counts)
    best, run, best_end = 0, 0, None
    for d in ordered:
        run = run + 1 if counts[d] else 0
        if run > best:
            best, best_end = run, d
    # Today still counts as open: a streak alive yesterday is alive until midnight.
    current, d = 0, today if counts.get(today) else today - dt.timedelta(days=1)
    while counts.get(d):
        current += 1
        d -= dt.timedelta(days=1)
    best_start = best_end - dt.timedelta(days=best - 1) if best_end else None
    return current, best, best_start, best_end


def month(d):
    return d.strftime("%b %Y")


def card(theme, counts, created, today):
    t, ramp = THEMES[theme], RAMP[theme]
    pad, cell, gap = 64, 16, 4.2
    total = sum(counts.values())
    current, best, best_start, best_end = streaks(counts, today)

    # The last 53 weeks, Sunday to Saturday, as GitHub draws them.
    end = today
    start = end - dt.timedelta(days=end.weekday() + 1 + 52 * 7) if end.weekday() != 6 else end - dt.timedelta(days=52 * 7)
    year = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    seen = sorted(c for d in year if (c := counts.get(d, 0)) > 0)
    def level(c):
        if not c or not seen:
            return 0
        q = [seen[int(len(seen) * f) - 1] for f in (0.25, 0.5, 0.75)]
        return 1 if c <= q[0] else 2 if c <= q[1] else 3 if c <= q[2] else 4

    label = "ACTIVITY ON GITHUB"
    updated = f"UPDATED {today.strftime('%b %d').upper()}"
    stats = [
        (f"{total:,}", f"CONTRIBUTIONS SINCE {created.year}"),
        (f"{current} {'day' if current == 1 else 'days'}", "CURRENT STREAK"),
        (f"{best} days", f"LONGEST · {month(best_start).upper()} TO {month(best_end).upper()}" if best_end else "LONGEST STREAK"),
    ]
    top, grid_top = 70, 128
    grid_h = 7 * cell + 6 * gap
    stats_y = grid_top + grid_h + 96
    height = stats_y + 64

    parts = [
        f'<clipPath id="panel"><rect width="{W}" height="{height}" rx="21"/></clipPath><g clip-path="url(#panel)">',
        f'<rect width="{W}" height="{height}" fill="{t["ground"]}"/>',
        f'<text x="{pad}" y="{top}" style="{fam("mono")}" font-size="17" letter-spacing="1.6" fill="{t["mute"]}">{label}</text>',
        f'<text x="{W - pad}" y="{top}" text-anchor="end" style="{fam("mono")}" font-size="17" letter-spacing="1.6" fill="{t["mute"]}">{updated}</text>',
    ]
    months_used = ""
    last_month = None
    for i, d in enumerate(year):
        col, row = (d - start).days // 7, (d.weekday() + 1) % 7
        x, y = pad + col * (cell + gap), grid_top + row * (cell + gap)
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3.5" fill="{ramp[level(counts.get(d, 0))]}"/>')
        if row == 0 and d.month != last_month and col < 51:
            name = d.strftime("%b")
            months_used += name
            parts.append(f'<text x="{x:.1f}" y="{grid_top - 14}" style="{fam("mono")}" font-size="14" fill="{t["mute"]}">{name}</text>')
            last_month = d.month
    # The rule under the grid, crossed at its ends like the site's acts.
    rule_y = grid_top + grid_h + 34
    parts.append(f'<path d="M{pad} {rule_y}H{W - pad}" stroke="{t["rule"]}" stroke-width="1.5"/>')
    parts += [cross(pad, rule_y, t["cross"], 7), cross(W - pad, rule_y, t["cross"], 7)]
    col_w = (W - 2 * pad) / 3
    for i, (value, caption) in enumerate(stats):
        x = pad + i * col_w
        color = ORANGE if i == 1 else t["ink"]
        parts.append(f'<text x="{x:.1f}" y="{stats_y}" style="{fam("display")}" font-size="46" fill="{color}">{esc(value)}</text>')
        parts.append(f'<text x="{x:.1f}" y="{stats_y + 34}" style="{fam("mono")}" font-size="14" letter-spacing="1.2" fill="{t["mute"]}">{esc(caption)}</text>')
    parts.append("</g>")
    parts.append(f'<rect x=".75" y=".75" width="{W - 1.5}" height="{height - 1.5}" rx="20.5" fill="none" stroke="{t["rule"]}" stroke-width="1.5"/>')

    used = {
        "display": "".join(v for v, _ in stats),
        "mono": label + updated + months_used + "".join(c for _, c in stats),
    }
    alt = f"{total:,} contributions since {created.year}, current streak {current} days, longest streak {best} days"
    return svg(height, embed(used), parts, alt)


if __name__ == "__main__":
    counts, created, today = days()
    for theme in THEMES:
        write(f"activity-{theme}.svg", card(theme, counts, created, today))
    print(f"{sum(counts.values())} contributions, {len(counts)} days")
