"""Resilient fetch for the Blackboard (bb.unisr.it) ICS feed.

Connection/timeout failures are treated as transient outages: the caller exits
0 without touching the existing .ics files, so the workflow stays green and the
next run retries. HTTP errors or non-ICS responses mean the feed actually
changed, so the process exits non-zero and the breakage is noticed.
"""

import sys
import time

import requests

REQUEST_TIMEOUT = (10, 30)
MAX_ATTEMPTS = 4
RETRY_DELAY_SECONDS = 5
USER_AGENT = "calendar-filter/1.0 (+https://github.com/albilug/calendar-filter)"


def _validate(text):
    stripped = [line.strip() for line in text.splitlines() if line.strip()]
    if not stripped:
        raise ValueError("empty response")
    if stripped[0].lstrip("\ufeff") != "BEGIN:VCALENDAR":
        raise ValueError("response is not an ICS calendar")
    if "END:VCALENDAR" not in stripped:
        raise ValueError("ICS calendar is incomplete")


def fetch_ics(url):
    """Return the ICS text, retrying transient failures.

    On a persistent transient connection/timeout failure the process exits 0
    (existing files are kept). On a real problem (HTTP error or non-ICS body)
    it exits non-zero so the workflow fails and we get notified.
    """
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            response.encoding = response.encoding or "utf-8"
            text = response.text
            _validate(text)
            return text
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            print(
                f"fetch attempt {attempt}/{MAX_ATTEMPTS} failed: {exc}",
                file=sys.stderr,
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)

    if isinstance(last_error, (requests.ConnectionError, requests.Timeout)):
        print(
            "Transient bb.unisr.it connection failure; keeping existing "
            f"calendars and exiting cleanly: {last_error}",
            file=sys.stderr,
        )
        raise SystemExit(0)

    raise SystemExit(f"Blackboard calendar source problem: {last_error}")
