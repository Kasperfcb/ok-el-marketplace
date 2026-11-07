"""Low-frequency client for OK's unofficial Min OK web API.

Use only with an account you own. Cookies are held in RAM.
No raw login data or personal API responses are logged.
"""
from __future__ import annotations

import json
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from .discovery import find_agreement_numbers

BASE = "https://www.ok.dk"
LOGIN_PAGE = BASE + "/min-ok-forside/login"
LOGIN_API = BASE + "/min-ok-forside/login/authenticate"
DATA_PAGE = BASE + "/min-ok-forside/el-overblik/forbrug"
DATA_API = DATA_PAGE + "/GetData"
COMPARE_API = DATA_PAGE + "/GetDataComparison"


class OKAPIError(RuntimeError):
    pass


class OKClient:
    def __init__(self):
        self.cookies = CookieJar()
        self._opener = build_opener(HTTPCookieProcessor(self.cookies))
        self._logged_in = False

    def _post(self, endpoint: str, payload: dict[str, Any], *, referer: str) -> Any:
        request = Request(
            endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": BASE,
                "Referer": referer,
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
            },
        )
        try:
            with self._opener.open(request, timeout=35) as response:
                raw = response.read()
        except HTTPError as exc:
            raise OKAPIError(f"OK afviste {endpoint.split('/')[-1]} (HTTP {exc.code})") from None
        except (URLError, TimeoutError):
            raise OKAPIError("Netværksfejl til OK – kontrollér forbindelsen") from None
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise OKAPIError("OK svarede ikke med JSON; session udløbet eller API ændret") from None

    def login(self, email: str, password: str) -> None:
        try:
            with self._opener.open(Request(LOGIN_PAGE, headers={"User-Agent": "Mozilla/5.0"}), timeout=20):
                pass
        except (HTTPError, URLError, TimeoutError):
            pass
        result = self._post(LOGIN_API, {
            "returnUrl": None,
            "values": {"email": email, "password": password, "persist": "true"},
        }, referer=LOGIN_PAGE)
        if not isinstance(result, dict) or result.get("loginStatus") != "Valid":
            raise OKAPIError("Login blev ikke godkendt. Kontrollér login hos OK.")
        self._logged_in = True

    def _require_login(self) -> None:
        if not self._logged_in:
            raise OKAPIError("Du skal logge ind først")

    def discover_agreement_numbers(self) -> list[int]:
        """Look for explicit agreement IDs on authenticated OK pages.

        This is experimental: it works only if OK includes a labelled ID in
        page HTML. Never infer the ID from customer numbers or cookie values.
        """
        self._require_login()
        found: set[int] = set()
        for url in (DATA_PAGE, BASE + "/min-ok-forside"):
            request = Request(
                url,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36",
                },
            )
            try:
                with self._opener.open(request, timeout=20) as response:
                    if "text/html" not in response.headers.get("Content-Type", "").lower():
                        continue
                    html = response.read(3_000_000).decode("utf-8", errors="replace")
            except (HTTPError, URLError, TimeoutError):
                continue
            found.update(find_agreement_numbers(html))
            if len(found) > 1:
                break
        return sorted(found)

    def get_data(self, agreement: int, *, period: str, start: str, end: str, display_type: int) -> Any:
        self._require_login()
        if period not in ("HOUR", "DAY", "YEAR") or display_type not in (0, 1):
            raise ValueError("Ugyldig periode eller display_type")
        return self._post(DATA_API, {
            "aftalenr": agreement,
            "periode": period,
            "fromDate": start,
            "toDate": end,
            "elForbrugDisplayType": display_type,
        }, referer=DATA_PAGE)

    def get_comparison(self, agreement: int, *, period: str, years: list[int]) -> Any:
        self._require_login()
        if period not in ("MONTH", "QUARTER"):
            raise ValueError("Comparison kræver MONTH eller QUARTER")
        return self._post(COMPARE_API, {
            "aftalenr": agreement, "periode": period, "years": years,
        }, referer=DATA_PAGE)
