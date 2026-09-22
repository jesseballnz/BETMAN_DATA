#!/usr/bin/env python3
"""Fetch TAB NZ affiliate racing event payloads as JSONL.

The output is one full `/racing/events/{id}` payload per line. Loading is handled
separately by `load_tab_event_payloads.sql` so the raw source records remain
auditable and re-runnable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.tab.co.nz/affiliates/v1"
EVENT_PARAMS = {
    "with_money_tracker": "true",
    "with_big_bets": "true",
    "with_biggest_bet": "true",
    "with_tote_trends_data": "true",
    "present_overlay": "false",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD")
    parser.add_argument(
        "--reconcile-targets",
        help="Optional TSV of event_id, country, race_date for exact historical rechecks",
    )
    parser.add_argument("--countries", default="NZ,AUS,HK", help="Comma-separated country codes")
    parser.add_argument("--type", default="T", help="TAB racing type filter")
    parser.add_argument("--race-types", default="T", help="Comma-separated event payload race types to write")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--workers", type=int, default=12, help="Concurrent event fetches")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retries per request")
    parser.add_argument("--limit", type=int, default=200, help="Meetings page size")
    return parser.parse_args()


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def headers() -> dict[str, str]:
    from_header = (
        os.environ.get("TAB_PUBLIC_FROM")
        or os.environ.get("TAB_AFFILIATE_FROM")
        or os.environ.get("BETMAN_CONTACT_EMAIL")
        or "ai@betman.co.nz"
    )
    out = {
        "User-Agent": os.environ.get("TAB_USER_AGENT") or "betman-data-backfill/1.0",
        "From": from_header,
        "X-Partner": os.environ.get("TAB_PUBLIC_PARTNER") or os.environ.get("TAB_AFFILIATE_PARTNER") or "BETMAN",
    }
    partner_id = os.environ.get("TAB_PUBLIC_PARTNER_ID") or os.environ.get("TAB_AFFILIATE_PARTNER_ID")
    if partner_id:
        out["X-Partner-ID"] = partner_id
    return out


def get_json(path: str, params: dict[str, Any], retries: int) -> dict[str, Any]:
    base_url = (os.environ.get("TAB_PUBLIC_API_BASE_URL") or os.environ.get("TAB_AFFILIATE_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    url = f"{base_url}{path}?{urlencode(params)}" if params else f"{base_url}{path}"
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=headers())
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"GET failed after retries: {url}: {last_error}")


def list_events_for_day(
    day: date, country: str, race_type: str, limit: int, retries: int
) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    offset = 0
    while True:
        payload = get_json(
            "/racing/meetings",
            {
                "country": country,
                "type": race_type,
                "date_from": day.isoformat(),
                "date_to": day.isoformat(),
                "limit": str(limit),
                "offset": str(offset),
            },
            retries,
        )
        meetings = ((payload.get("data") or {}).get("meetings")) or []
        for meeting in meetings:
            for race in meeting.get("races") or []:
                event_id = race.get("id")
                if event_id:
                    events.append(
                        {
                            "event_id": str(event_id),
                            "status": str(race.get("status") or ""),
                        }
                    )
        if len(meetings) < limit:
            break
        offset += limit
    return events


def load_reconcile_targets(path: str | None) -> list[tuple[str, str, date]]:
    if not path:
        return []
    targets: list[tuple[str, str, date]] = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"invalid reconcile target on line {number}")
        event_id, country, race_date = parts
        targets.append((event_id, country.upper(), datetime.strptime(race_date, "%Y-%m-%d").date()))
    return targets


def fetch_event(event_id: str, retries: int) -> dict[str, Any]:
    return get_json(f"/racing/events/{event_id}", EVENT_PARAMS, retries)


def main() -> int:
    args = parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    countries = [item.strip().upper() for item in args.countries.split(",") if item.strip()]
    allowed_race_types = {item.strip().upper() for item in args.race_types.split(",") if item.strip()}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    event_ids: list[str] = []
    listing_statuses: dict[str, str] = {}
    for day in daterange(start, end):
        for country in countries:
            events = list_events_for_day(day, country, args.type, args.limit, args.retries)
            for event in events:
                event_ids.append(event["event_id"])
                listing_statuses[event["event_id"]] = event["status"]
            print(f"{day} {country}: {len(events)} races", file=sys.stderr, flush=True)

    targets = load_reconcile_targets(args.reconcile_targets)
    target_groups = sorted({(country, race_date) for _, country, race_date in targets})
    target_ids = {event_id for event_id, _, _ in targets}
    for country, race_date in target_groups:
        events = list_events_for_day(race_date, country, args.type, args.limit, args.retries)
        for event in events:
            if event["event_id"] in target_ids:
                listing_statuses[event["event_id"]] = event["status"]
        print(
            f"reconcile {race_date} {country}: {len(events)} listed races",
            file=sys.stderr,
            flush=True,
        )
    event_ids.extend(event_id for event_id, _, _ in targets)

    seen: set[str] = set()
    unique_ids = [event_id for event_id in event_ids if not (event_id in seen or seen.add(event_id))]
    print(f"Fetching {len(unique_ids)} unique events", file=sys.stderr, flush=True)

    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {pool.submit(fetch_event, event_id, args.retries): event_id for event_id in unique_ids}
            for future in as_completed(futures):
                event_id = futures[future]
                try:
                    payload = future.result()
                except Exception as exc:
                    listing_status = listing_statuses.get(event_id, "")
                    if listing_status.lower() != "abandoned":
                        print(f"ERROR {event_id}: {exc}", file=sys.stderr, flush=True)
                        continue
                    # TAB can remove an abandoned event-detail document while
                    # retaining its authoritative status in the meeting list.
                    # Emit a status-only envelope; the loader merges it with
                    # the last retained full source payload instead of erasing it.
                    payload = {
                        "_betman_status_only": True,
                        "data": {"race": {"event_id": event_id, "type": "T"}},
                    }
                    print(
                        f"Using listing-only abandoned status for {event_id}: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
                race_type = (((payload.get("data") or {}).get("race") or {}).get("type") or "").upper()
                if allowed_race_types and race_type not in allowed_race_types:
                    continue
                # Persist the source-capture time inside the auditable JSONL so
                # a retry of the same file cannot manufacture a new market tick.
                payload["_betman_fetched_at"] = datetime.now(timezone.utc).isoformat()
                listing_status = listing_statuses.get(event_id)
                if listing_status:
                    # The meetings listing is authoritative for cancellations.
                    # Some event-detail payloads remain incorrectly Open after
                    # the whole card has been abandoned.
                    payload["_betman_listing_race_status"] = listing_status
                fh.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
                written += 1
                if written % 250 == 0:
                    print(f"Fetched {written}/{len(unique_ids)}", file=sys.stderr, flush=True)

    print(f"Wrote {written} events to {out_path}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
