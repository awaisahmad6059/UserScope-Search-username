"""UserScope phone intelligence.

A completely free, API-key-free phone number analyzer and local history.
Number parsing/validation/formatting/carrier/geo is done offline with the
open-source ``phonenumbers`` library (libphonenumber data shipped locally).

The only optional network call is a raw DuckDuckGo HTML scrape of the
number when the user explicitly opts in (no key, no account, no API).

This module is self-contained: it does not touch the ``userscope`` engine.
"""

import json
import pathlib
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import phonenumbers
from phonenumbers import carrier, geocoder
from phonenumbers import timezone as pn_timezone
from phonenumbers.phonenumberutil import (
    number_type as pn_number_type,
    PhoneNumberType,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
HISTORY_FILE = ROOT / "results" / "phone_history.json"
HISTORY_LIMIT = 50

_TYPE_NAMES = {
    PhoneNumberType.MOBILE: "mobile",
    PhoneNumberType.FIXED_LINE: "fixed line",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed line / mobile",
    PhoneNumberType.TOLL_FREE: "toll free",
    PhoneNumberType.PREMIUM_RATE: "premium rate",
    PhoneNumberType.VOIP: "voip",
    PhoneNumberType.VOICEMAIL: "voicemail",
    PhoneNumberType.PAGER: "pager",
}

class PhoneLookup:
    """Validates and describes phone numbers without any paid service."""

    _lock = threading.RLock()

    # ------------------------------------------------------------------ API

    def lookup(self, raw):
        """Analyze ``raw`` and return a plain dict for the UI.

        Never raises for bad input; the result carries ``valid``/``possible``
        flags plus whatever the offline library can tell us.
        """
        raw = (raw or "").strip()
        num = self._parse_number(raw)
        if num is None:
            return {
                "ok": True,
                "valid": False,
                "possible": False,
                "error": "Not a phone number.",
                "query": raw,
                "when": self._now(),
            }

        type_ = pn_number_type(num)
        tz = list(pn_timezone.time_zones_for_number(num)) or []
        try:
            geo = geocoder.description_for_valid_number(num, "en")
        except Exception:
            geo = None
        try:
            carrier_name = carrier.name_for_number(num, "en")
        except Exception:
            carrier_name = None

        result = {
            "ok": True,
            "valid": phonenumbers.is_valid_number(num),
            "possible": phonenumbers.is_possible_number(num),
            "query": raw,
            "country_code": num.country_code,
            "national_number": str(num.national_number),
            "region": phonenumbers.region_code_for_number(num),
            "region_name": self._region_name(num),
            "phone_type": _TYPE_NAMES.get(type_, "unknown"),
            "formats": self._formats(num),
            "timezones": tz,
            "geo": geo,
            "carrier": carrier_name,
            "national_significant": phonenumbers.national_significant_number(num),
            "when": self._now(),
            "local_time": self._local_time(tz),
        }
        return result

    def web_search(self, raw, limit=8):
        """Optional free web visibility check via DuckDuckGo HTML (no key).

        Returns a list of {title, url, snippet}. Network failures are
        swallowed and reported as an empty list - the UI marks it "no
        public hits / search blocked".
        """
        num = self._parse_number(raw)
        if num is None:
            return []
        number = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        query = '"%s" -business -prices' % number.replace("+", "")
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", "ignore")
        except Exception:
            return []

        links, seen = [], set()
        for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
            href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
            href = urllib.parse.unquote(re.sub(r"^.*?uddg=([^&]+).*$", r"\1", href))
            if not href.startswith("http"):
                continue
            if href in seen:
                continue
            seen.add(href)
            snip = ""
            sm = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html[m.end():], re.S)
            if sm:
                snip = re.sub(r"<[^>]+>", "", sm.group(1)).strip()
            links.append({"title": title or "Untitled result", "url": href, "snippet": snip})
            if len(links) >= limit:
                break
        return links

    # ------------------------------------------------------------- history

    def add_history(self, record):
        """Persist a lookup (minus heavy web payload) to the local history file."""
        item = {k: v for k, v in record.items() if k != "web"}
        with self._lock:
            items = self.history()
            items = [it for it in items if it.get("query") != item.get("query") or it.get("when") != item.get("when")]
            items.insert(0, item)
            del items[HISTORY_LIMIT:]
            self._write(items)

    def history(self):
        with self._lock:
            try:
                data = json.loads(HISTORY_FILE.read_text("utf-8"))
                return data if isinstance(data, list) else []
            except Exception:
                return []

    def clear_history(self):
        with self._lock:
            self._write([])

    # ------------------------------------------------------------------ utils

    def _write(self, items):
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(
            json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _parse_number(raw):
        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            if raw.startswith("+"):
                return phonenumbers.parse(raw, None)
            return phonenumbers.parse(raw, "PK")
        except phonenumbers.NumberParseException:
            return None

    @staticmethod
    def _formats(num):
        it = phonenumbers.PhoneNumberFormat
        return {
            "e164": phonenumbers.format_number(num, it.E164),
            "intl": phonenumbers.format_number(num, it.INTERNATIONAL),
            "national": phonenumbers.format_number(num, it.NATIONAL),
            "rfc3966": phonenumbers.format_number(num, it.RFC3966),
        }

    @staticmethod
    def _region_name(num):
        region = phonenumbers.region_code_for_number(num)
        if not region:
            return None
        try:
            import pycountry  # noqa: F401
            return pycountry.countries.get(alpha_2=region).name
        except Exception:
            return region

    @staticmethod
    def _local_time(timezones):
        tz = timezones[0] if timezones else "UTC"
        try:
            import zoneinfo
            return datetime.now(zoneinfo.ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M %Z")
        except Exception:
            return None