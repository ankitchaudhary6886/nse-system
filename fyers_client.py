"""Fyers API v3 client for NSE market data (dependency-free).

WHY A HAND-WRITTEN CLIENT
-------------------------
The official SDK (``fyers-apiv3``) pulls ``aiohttp``; installing it on this
laptop fails to build a wheel, and this project only needs three read-only
endpoints (history / quotes / depth) plus the OAuth code exchange.  Nothing
here can place, modify, or cancel an order: this is a *data* client for a
non-trading app.

AUTH FLOW (one time per day, Fyers tokens expire at ~06:00 IST)
---------------------------------------------------------------
1. ``python fyers_client.py login-url``  -> open the printed URL in a browser.
2. Log in with the Fyers account and approve the app.
3. The browser is redirected to the registered redirect URI with an
   ``auth_code`` query parameter. Copy that value (or the whole URL).
4. ``python fyers_client.py exchange --code <auth_code>``
   (``exchange`` with no --code prompts for a pasted value).
5. The access token is stored in ``data/fyers_token.json`` (gitignored).
   Every later command reads it automatically.

ENDPOINTS USED (verified against the official SDK source, 2026-10-18)
---------------------------------------------------------------------
    API  https://api-t1.fyers.in/api/v3
        /generate-authcode      (login URL)
        /validate-authcode      (POST auth_code -> access_token)
        /profile                /marketStatus
        /screeners/config       /screeners/query   (entitlement dependent)
    DATA https://api-t1.fyers.in/data
        /history   /quotes   /depth
    Auth header: ``"<app_id>:<access_token>"`` plus ``version: 3``.

RATE LIMITS (documented): 10 req/s, 200 req/min, 100k req/day. This client
defaults to 8 req/s / 180 req/min and raises ``FyersRateLimitError`` instead
of hammering the broker. Retries happen only for 429 and network errors.

PROVENANCE: every fetched payload keeps the broker's raw JSON so a later
audit can prove what the broker actually said; normalized columns are
derived from that raw payload and never invented.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TOKEN_FILE = DATA_DIR / "fyers_token.json"
ENV_FILE = ROOT / ".env"

API_BASE = "https://api-t1.fyers.in/api/v3"
DATA_BASE = "https://api-t1.fyers.in/data"
SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/NSE_CM.csv"
# Refresh-token flow: POST body {grant_type:"refresh_token", appIdHash,
# refresh_token, pin}. It requires the Fyers PIN, which is why FYERS_PIN is an
# optional .env value: without it the daily OAuth login stays manual.
REFRESH_ENDPOINT = "/validate-refresh-token"

DEFAULT_REDIRECT_URI = "https://fyers.in"
DEFAULT_STATE = "nse_system"

# NSE index tickers differ from cash-equity tickers. Add entries here, never
# guess inside call sites.
INDEX_MAP = {
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "NIFTY": "NSE:NIFTY50-INDEX",
    "^NSEI": "NSE:NIFTY50-INDEX",
    "NIFTYBANK": "NSE:NIFTYBANK-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "NIFTY500": "NSE:NIFTY500-INDEX",
    "NIFTYMIDCAP100": "NSE:NIFTYMIDCAP100-INDEX",
    "NIFTYSMLCAP100": "NSE:NIFTYSMALLCAP100-INDEX",
}

IST_OFFSET = dt.timedelta(hours=5, minutes=30)


class FyersError(RuntimeError):
    """Broker returned an error envelope or an unusable HTTP response."""

    def __init__(self, message: str, code: Optional[int] = None,
                 http_status: Optional[int] = None,
                 payload: Optional[dict] = None):
        self.code = code
        self.http_status = http_status
        self.payload = payload
        super().__init__(message)


class FyersAuthError(FyersError):
    """Token missing, expired, or auth code rejected: re-run the login flow."""


class FyersRateLimitError(FyersError):
    """Local call budget exhausted (we refuse to exceed the broker limit)."""


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------
def load_env_file(path: Path = ENV_FILE) -> int:
    """Load KEY=VALUE pairs from .env without overwriting real env vars.

    python-dotenv is a declared dependency but the manual fallback keeps this
    module usable from a bare python if the venv is incomplete.
    """
    if not path.is_file():
        return 0
    loaded = 0
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


load_env_file()


def credentials() -> Dict[str, str]:
    """Broker app credentials from the environment (after .env load)."""
    return {
        "app_id": os.environ.get("FYERS_APP_ID", "").strip(),
        "secret_id": os.environ.get("FYERS_SECRET_ID", "").strip(),
        "redirect_uri": (os.environ.get("FYERS_REDIRECT_URI")
                         or DEFAULT_REDIRECT_URI).strip(),
    }


def app_id_hash(app_id: str, secret_id: str) -> str:
    """SHA-256 of ``app_id:secret_id`` exactly as the broker validates it."""
    if not app_id or not secret_id:
        raise FyersAuthError("FYERS_APP_ID and FYERS_SECRET_ID are required")
    return hashlib.sha256(f"{app_id}:{secret_id}".encode()).hexdigest()


def build_auth_url(app_id: Optional[str] = None,
                   redirect_uri: Optional[str] = None,
                   state: str = DEFAULT_STATE) -> str:
    conf = credentials()
    app_id = app_id or conf["app_id"]
    if not app_id:
        raise FyersAuthError("FYERS_APP_ID is not configured (.env)")
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri or conf["redirect_uri"],
        "response_type": "code",
        "state": state,
    }
    return f"{API_BASE}/generate-authcode?{urllib.parse.urlencode(params)}"


def extract_auth_code(value: str) -> str:
    """Accept a bare auth_code or a full redirected URL and return the code."""
    text = (value or "").strip()
    if not text:
        raise FyersAuthError("empty auth code")
    if "auth_code=" in text:
        query = urllib.parse.urlparse(text).query
        code = urllib.parse.parse_qs(query).get("auth_code", [""])[0]
        if code:
            return code.strip()
    if "code=" in text and "://" in text:
        query = urllib.parse.urlparse(text).query
        code = urllib.parse.parse_qs(query).get("code", [""])[0]
        if code:
            return code.strip()
    return text


# ---------------------------------------------------------------------------
# symbol mapping
# ---------------------------------------------------------------------------
def to_fyers_symbol(symbol: str) -> str:
    """``SBIN`` -> ``NSE:SBIN-EQ``; existing ``NSE:...`` passes through."""
    text = str(symbol or "").strip().upper()
    if not text:
        raise ValueError("empty symbol")
    if ":" in text:
        return text
    if text in INDEX_MAP:
        return INDEX_MAP[text]
    return f"NSE:{text}-EQ"


def from_fyers_symbol(ticker: str) -> str:
    """``NSE:SBIN-EQ`` -> ``SBIN`` (keeps non-EQ tickers readable)."""
    text = str(ticker or "").strip().upper()
    if ":" in text:
        text = text.split(":", 1)[1]
    if text.endswith("-EQ"):
        return text[:-3]
    return text


# ---------------------------------------------------------------------------
# token store
# ---------------------------------------------------------------------------
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def next_token_expiry(now: Optional[dt.datetime] = None) -> dt.datetime:
    """Fyers access tokens die at ~06:00 IST the next calendar day.

    We store a 05:55 IST expiry so the client stops using a token five minutes
    before the broker does. Returned and stored values are timezone-aware IST.
    """
    now_ist = now or dt.datetime.now(IST)
    if now_ist.tzinfo is None:
        now_ist = now_ist.replace(tzinfo=IST)
    else:
        now_ist = now_ist.astimezone(IST)
    expiry = now_ist.replace(hour=5, minute=55, second=0, microsecond=0)
    if expiry <= now_ist:
        expiry += dt.timedelta(days=1)
    return expiry


class TokenStore:
    """Reads/writes data/fyers_token.json (gitignored by ``data/*token*``)."""

    def __init__(self, path: Path = TOKEN_FILE):
        self.path = Path(path)

    def load(self) -> Optional[dict]:
        if not self.path.is_file():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def access_token(self) -> Optional[str]:
        data = self.load() or {}
        token = (data.get("access_token") or "").strip()
        return token or None

    def expired(self) -> bool:
        data = self.load() or {}
        expires = data.get("expires_at")
        if not expires:
            return False  # unknown expiry: let the broker decide
        try:
            moment = dt.datetime.fromisoformat(str(expires))
        except ValueError:
            return False
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=IST)
        return moment <= dt.datetime.now(IST)

    def save(self, access_token: str, refresh_token: str = "",
             profile: Optional[dict] = None) -> dict:
        if not access_token:
            raise FyersAuthError("refusing to store an empty access token")
        now = dt.datetime.now(IST)
        payload = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "issued_at": now.isoformat(timespec="seconds"),
            "expires_at": next_token_expiry().isoformat(timespec="seconds"),
            "profile": (profile or {}).get("data")
                        if isinstance(profile, dict) else None,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass

    def status(self) -> dict:
        data = self.load() or {}
        return {
            "token_file": str(self.path),
            "present": bool(data.get("access_token")),
            "refresh_present": bool(data.get("refresh_token")),
            "issued_at": data.get("issued_at"),
            "expires_at": data.get("expires_at"),
            "expired": self.expired() if data else None,
        }


# ---------------------------------------------------------------------------
# rate limiting
# ---------------------------------------------------------------------------
class RateLimiter:
    """Sliding-window limiter: per-minute cap is checked before per-second."""

    def __init__(self, max_per_sec: int = 8, max_per_min: int = 180,
                 sleep=time.sleep, clock=time.monotonic):
        self.max_per_sec = max(1, int(max_per_sec))
        self.max_per_min = max(1, int(max_per_min))
        self._sleep = sleep
        self._clock = clock
        self._calls: List[float] = []

    def _trim(self, now: float) -> None:
        cutoff = now - 60.0
        self._calls = [t for t in self._calls if t > cutoff]

    def acquire(self) -> None:
        now = self._clock()
        self._trim(now)
        # Bounded retries: if the injected sleep does not advance the injected
        # clock (a test bug, or a platform where sleep is a no-op), fail loudly
        # instead of spinning forever.
        for _ in range(1000):
            per_min = len(self._calls)
            if per_min >= self.max_per_min:
                wait = 60.0 - (now - self._calls[0]) + 0.01
                self._sleep(max(wait, 0.01))
                now = self._clock()
                self._trim(now)
                continue
            recent = [t for t in self._calls if t > now - 1.0]
            if len(recent) >= self.max_per_sec:
                self._sleep(max(1.0 - (now - recent[0]) + 0.01, 0.01))
                now = self._clock()
                self._trim(now)
                continue
            self._calls.append(now)
            return
        raise FyersRateLimitError(
            "local rate limiter could not obtain a slot (clock/sleep not "
            "advancing)")


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------
def _candle_rows(payload: Any) -> List[list]:
    if not isinstance(payload, dict):
        raise FyersError("history payload is not a JSON object", payload=payload)
    rows = payload.get("candles")
    if rows is None and isinstance(payload.get("data"), dict):
        rows = payload["data"].get("candles")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise FyersError("history payload 'candles' is not a list", payload=payload)
    return rows


class FyersClient:
    """Minimal read-only client. One instance per process is enough."""

    def __init__(self, app_id: Optional[str] = None,
                 access_token: Optional[str] = None,
                 token_store: Optional[TokenStore] = None,
                 session: Optional[requests.Session] = None,
                 timeout: int = 20,
                 max_per_sec: int = 8, max_per_min: int = 180,
                 retries: int = 2,
                 sleep=time.sleep, clock=time.monotonic):
        conf = credentials()
        self.app_id = (app_id or conf["app_id"]).strip()
        self.token_store = token_store or TokenStore()
        self.token = (access_token
                      or os.environ.get("FYERS_ACCESS_TOKEN", "").strip()
                      or self.token_store.access_token() or "")
        self._session = session or requests.Session()
        self.timeout = timeout
        self.retries = max(0, int(retries))
        self._sleep = sleep
        self._limiter = RateLimiter(max_per_sec, max_per_min, sleep=sleep,
                                    clock=clock)
        self._token_failure: Optional[str] = None

    # -- low level ---------------------------------------------------------
    def _headers(self) -> dict:
        if not self.token:
            raise FyersAuthError(
                "no Fyers access token: run 'python fyers_client.py login-url' "
                "then 'python fyers_client.py exchange --code <auth_code>'")
        return {
            "Authorization": f"{self.app_id}:{self.token}",
            "Content-Type": "application/json",
            "version": "3",
        }

    def _request(self, method: str, url: str, params: Optional[dict] = None,
                 body: Optional[dict] = None,
                 require_auth: bool = True) -> dict:
        headers = (self._headers() if require_auth else
                   {"Content-Type": "application/json", "version": "3"})
        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            self._limiter.acquire()
            try:
                if method.upper() == "GET":
                    response = self._session.get(
                        url, headers=headers, params=params,
                        timeout=self.timeout)
                else:
                    response = self._session.post(
                        url, headers=headers, json=body,
                        timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retries:
                    self._sleep(1.0 * (attempt + 1))
                    continue
                raise FyersError(f"network error calling {url}: {exc}") from exc

            status = getattr(response, "status_code", 0)
            try:
                payload = response.json()
            except ValueError:
                payload = {"raw": getattr(response, "text", "")}

            if status == 429 or (isinstance(payload, dict)
                                 and payload.get("code") == -429):
                last_error = FyersRateLimitError(
                    "broker rate limit hit", code=-429, http_status=status,
                    payload=payload if isinstance(payload, dict) else None)
                if attempt < self.retries:
                    self._sleep(2.0 * (attempt + 1))
                    continue
                raise last_error

            if status >= 500:
                last_error = FyersError(
                    f"broker server error HTTP {status}",
                    http_status=status,
                    payload=payload if isinstance(payload, dict) else None)
                if attempt < self.retries:
                    self._sleep(1.5 * (attempt + 1))
                    continue
                raise last_error

            if status == 401 or status == 403 or (
                    isinstance(payload, dict) and payload.get("code") in (-16, -17)):
                self._token_failure = "invalid or expired access token"
                message = (payload.get("message") if isinstance(payload, dict)
                           else None) or "token invalid or expired"
                raise FyersAuthError(
                    f"{message} (HTTP {status}). Re-run the login flow.",
                    code=(payload.get("code") if isinstance(payload, dict) else None),
                    http_status=status,
                    payload=payload if isinstance(payload, dict) else None)

            if status >= 400:
                message = (payload.get("message") if isinstance(payload, dict)
                           else None) or f"HTTP {status}"
                raise FyersError(
                    f"{message} (HTTP {status})",
                    code=(payload.get("code") if isinstance(payload, dict) else None),
                    http_status=status,
                    payload=payload if isinstance(payload, dict) else None)

            if not isinstance(payload, dict):
                raise FyersError(f"unexpected non-object response from {url}")
            if payload.get("s") == "error":
                code = payload.get("code")
                if code in (-16, -17):
                    self._token_failure = str(payload.get("message"))
                    raise FyersAuthError(
                        f"{payload.get('message')}", code=code,
                        http_status=status, payload=payload)
                raise FyersError(str(payload.get("message") or "broker error"),
                                 code=code, http_status=status, payload=payload)
            return payload
        raise last_error or FyersError("request failed")

    # -- account / status --------------------------------------------------
    def profile(self) -> dict:
        return self._request("GET", f"{API_BASE}/profile")

    def market_status(self) -> dict:
        return self._request("GET", f"{DATA_BASE}/marketStatus")

    def is_token_valid(self) -> bool:
        try:
            profile = self.profile()
            return profile.get("s") == "ok" and bool(profile.get("data"))
        except FyersError:
            return False

    def refresh_access_token(self, pin: Optional[str] = None) -> dict:
        """Renew the access token WITHOUT a browser, using the stored refresh
        token + the Fyers PIN.

        Fyers' documented refresh flow needs the account PIN, so FYERS_PIN must
        be present in .env (gitignored) for this to work. When it succeeds the
        daily browser login becomes unnecessary until the refresh token itself
        expires (Fyers documents ~15 days), and the scheduler can renew it
        automatically every morning.
        """
        stored = self.token_store.load() or {}
        refresh_token = (stored.get("refresh_token") or "").strip()
        if not refresh_token:
            raise FyersAuthError(
                "no refresh_token stored — do the browser login once first")
        conf = credentials()
        pin = (pin if pin is not None
               else os.environ.get("FYERS_PIN", "")).strip()
        if not pin:
            raise FyersAuthError(
                "FYERS_PIN is not configured — add it to .env to enable "
                "automatic token refresh")
        body = {
            "grant_type": "refresh_token",
            "appIdHash": app_id_hash(self.app_id or conf["app_id"],
                                     conf["secret_id"]),
            "refresh_token": refresh_token,
            "pin": pin,
        }
        payload = self._request("POST", API_BASE + REFRESH_ENDPOINT,
                                body=body, require_auth=False)
        token = payload.get("access_token") or ""
        if not token:
            raise FyersAuthError("refresh endpoint returned no access_token")
        saved = self.token_store.save(
            token, payload.get("refresh_token") or refresh_token)
        self.token = token
        return {"ok": True, "refreshed": True,
                "expires_at": saved.get("expires_at")}

    # -- market data -------------------------------------------------------
    def history_candles(self, symbol: str, resolution: str = "1D",
                        range_from: Optional[str] = None,
                        range_to: Optional[str] = None,
                        cont_flag: int = 1) -> List[list]:
        """One /history request. Returns ``[[epoch, o, h, l, c, v], ...]``."""
        today = dt.datetime.now(IST).date()
        params = {
            "symbol": to_fyers_symbol(symbol),
            "resolution": resolution,
            "date_format": "1",
            "range_from": str(range_from or (today - dt.timedelta(days=30))),
            "range_to": str(range_to or today),
            "cont_flag": str(cont_flag),
        }
        payload = self._request("GET", f"{DATA_BASE}/history", params=params)
        return _candle_rows(payload)

    def history_range(self, symbol: str, start: str, end: Optional[str] = None,
                      resolution: str = "1D", chunk_days: int = 300) -> List[list]:
        """Chunked history fetch; broker request ranges are bounded."""
        end_date = dt.date.fromisoformat(str(end or dt.date.today()))
        start_date = dt.date.fromisoformat(str(start))
        if start_date > end_date:
            return []
        rows: List[list] = []
        cursor = start_date
        while cursor <= end_date:
            stop = min(cursor + dt.timedelta(days=chunk_days - 1), end_date)
            rows.extend(self.history_candles(
                symbol, resolution=resolution,
                range_from=cursor.isoformat(), range_to=stop.isoformat()))
            cursor = stop + dt.timedelta(days=1)
        return rows

    def quotes(self, symbols: Sequence[str]) -> Dict[str, dict]:
        """Normalized quote snapshot keyed by project symbol.

        Fyers caps a quotes call at 50 symbols. The raw ``v`` payload is kept
        so unknown/new broker fields are never silently lost.
        """
        symbols = [str(s) for s in symbols if str(s).strip()]
        if not symbols:
            return {}
        tickers = [to_fyers_symbol(s) for s in symbols]
        # Key the result by the symbol the caller asked for, not by the reverse
        # of the broker ticker: NIFTY50 would otherwise come back as
        # "NIFTY50-INDEX" and BAJAJ_AUTO as "BAJAJ-AUTO", breaking joins.
        requested = {to_fyers_symbol(s): s for s in symbols}
        out: Dict[str, dict] = {}
        for i in range(0, len(tickers), 50):
            batch = tickers[i:i + 50]
            payload = self._request("GET", f"{DATA_BASE}/quotes",
                                    params={"symbols": ",".join(batch)})
            for item in payload.get("d") or []:
                if not isinstance(item, dict):
                    continue
                ticker = item.get("n") or item.get("symbol") or ""
                values = item.get("v") if isinstance(item.get("v"), dict) else {}
                if item.get("s") not in (None, "ok") or not values:
                    continue
                key = requested.get(ticker) or from_fyers_symbol(ticker)
                quote = _normalize_quote(ticker, values)
                quote["symbol"] = key
                out[key] = quote
        return out

    def depth(self, symbol: str) -> dict:
        payload = self._request("GET", f"{DATA_BASE}/depth",
                                params={"symbol": to_fyers_symbol(symbol),
                                        "ohlcv_flag": "1"})
        return payload

    # -- screeners (entitlement dependent; probe before trusting) ----------
    def screeners_config(self) -> dict:
        return self._request("GET", f"{API_BASE}/screeners/config")

    def screeners_query(self, screener: str, universe: str = "NSE_CM",
                        fields: str = "", order_by: str = "",
                        order: str = "DESC") -> dict:
        body = {"screener": screener, "universe": universe, "fields": fields,
                "order_by": order_by, "order": order}
        return self._request("POST", f"{API_BASE}/screeners/query", body=body)

    # -- symbol master -----------------------------------------------------
    def symbol_master_text(self, url: str = SYMBOL_MASTER_URL) -> str:
        """Public CSV of the NSE cash segment (no auth needed)."""
        response = self._session.get(
            url, timeout=self.timeout,
            headers={"User-Agent": "nse-system/1.0 (+data-ingest)"})
        response.raise_for_status()
        return response.text


def _normalize_quote(ticker: str, v: dict) -> dict:
    def pick(*keys):
        for key in keys:
            value = v.get(key)
            if value is not None and value != "":
                return value
        return None

    ltp = pick("lp", "ltp", "last_price")
    prev = pick("prev_close_price", "prevClose", "close")
    change = pick("ch", "change")
    change_pct = pick("chp", "change_percent")
    bid = pick("bid", "best_bid")
    ask = pick("ask", "best_ask")
    spread = pick("spread")
    if spread is None and bid is not None and ask is not None:
        try:
            spread = round(float(ask) - float(bid), 4)
        except (TypeError, ValueError):
            spread = None
    return {
        "ticker": ticker,
        "ltp": ltp,
        "prev_close": prev,
        "open": pick("o", "open", "open_price"),
        "high": pick("h", "high", "high_price"),
        "low": pick("l", "low", "low_price"),
        "close": pick("c", "close", "close_price"),
        "volume": pick("v", "vol", "volume"),
        "change": change,
        "change_pct": change_pct,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "raw": dict(v),
    }


def parse_symbol_master(text: str) -> List[dict]:
    """Parse the public NSE cash-segment CSV into normalized rows.

    The CSV has no header. Columns observed 2026-10-18 (1-based):
      1 fyToken, 2 name, 5 tickSize, 6 ISIN, 8 last update date,
      10 ticker ``NSE:SBIN-EQ``, 11 lot size, 14 display symbol.
    Instead of trusting positions only, the ticker and ISIN columns are
    detected by content so a broker column reshuffle cannot mis-map symbols.
    """
    rows: List[dict] = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 10:
            continue
        ticker_field = next((p for p in parts if p.startswith("NSE:")), None)
        if not ticker_field:
            continue
        isin = next((p for p in parts if re.fullmatch(r"INE[0-9A-Z]{9}", p)
                     or re.fullmatch(r"INF[0-9A-Z]{9}", p)), None)
        dates = [p for p in parts if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p)]
        try:
            fy_token = int(parts[0])
        except (TypeError, ValueError):
            fy_token = None
        try:
            tick_size = float(parts[4]) if parts[4] else None
        except (TypeError, ValueError):
            tick_size = None
        try:
            lot_size = float(parts[10]) if len(parts) > 10 and parts[10] else None
        except (TypeError, ValueError):
            lot_size = None
        name = parts[1] if len(parts) > 1 else None
        display = parts[13] if len(parts) > 13 and parts[13] else None
        symbol = from_fyers_symbol(ticker_field)
        if not symbol:
            continue
        rows.append({
            "symbol": symbol,
            "ticker": ticker_field,
            "name": name or display,
            "isin": isin,
            "fy_token": fy_token,
            "lot_size": lot_size,
            "tick_size": tick_size,
            "exchange": ticker_field.split(":", 1)[0],
            "segment": "CM",
            "source_updated": dates[0] if dates else None,
            "raw": line,
        })
    return rows


def _fmt_candles(candles: Iterable[list]) -> List[dict]:
    out = []
    for row in candles or []:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            continue
        try:
            epoch = int(float(row[0]))
            o, h, l, c, v = (float(row[1]), float(row[2]), float(row[3]),
                             float(row[4]), float(row[5]))
        except (TypeError, ValueError):
            continue
        # Bound the epoch (2000-01-01 .. 2100-01-01) before datetime arithmetic:
        # a millisecond timestamp or a garbage value must be skipped, not crash
        # the whole symbol (timedelta can raise OverflowError).
        if not (946684800 <= epoch <= 4102444800):
            continue
        try:
            date = (dt.datetime(1970, 1, 1) + dt.timedelta(seconds=epoch)
                    + IST_OFFSET).date().isoformat()
        except (OverflowError, OSError, ValueError):
            continue
        out.append({"date": date, "open": o, "high": h, "low": l,
                    "close": c, "volume": v})
    return out


# ---------------------------------------------------------------------------
# CLI: auth + diagnostics only. Data ingestion lives in ingest_fyers.py.
# ---------------------------------------------------------------------------
def _cmd_status(client: FyersClient) -> int:
    conf = credentials()
    store = client.token_store.status()
    print("credentials:", "app_id=" + (conf["app_id"] or "MISSING"),
          "secret=" + ("set" if conf["secret_id"] else "MISSING"),
          "redirect=" + conf["redirect_uri"])
    print("token:", json.dumps(store, indent=2))
    if not store["present"]:
        print("\nNo token. Run: python fyers_client.py login-url")
        return 1
    try:
        profile = client.profile()
        data = profile.get("data") or {}
        print("profile: ok —", data.get("display_name") or data.get("name")
              or "(name hidden)")
    except FyersError as exc:
        print("profile: FAILED —", exc)
        return 2
    try:
        print("marketStatus:", json.dumps(client.market_status())[:300])
    except FyersError as exc:
        print("marketStatus: FAILED —", exc)
    return 0


def exchange_code(code: str, store: Optional[TokenStore] = None,
                  client: Optional[FyersClient] = None) -> dict:
    """Exchange an auth code for a token; API-safe (returns no token value).

    Used by the terminal UI save-login button. Never raises: returns
    {ok, expires_at, profile} or {ok: False, error, code}.
    """
    conf = credentials()
    if not conf["app_id"] or not conf["secret_id"]:
        return {"ok": False, "error": "FYERS_APP_ID/SECRET_ID not configured"}
    try:
        digest = app_id_hash(conf["app_id"], conf["secret_id"])
    except FyersAuthError as exc:
        return {"ok": False, "error": str(exc)}
    client = client or FyersClient(app_id=conf["app_id"], access_token="")
    try:
        response = client._request(
            "POST", f"{API_BASE}/validate-authcode",
            body={"grant_type": "authorization_code", "appIdHash": digest,
                  "code": extract_auth_code(code)},
            require_auth=False)
    except FyersError as exc:
        return {"ok": False, "error": str(exc), "code": exc.code}
    token = response.get("access_token") or ""
    if not token:
        return {"ok": False, "error": "no access_token in broker response"}
    saved = (store or TokenStore()).save(
        token, response.get("refresh_token") or "")
    client.token = token
    profile = ""
    try:
        data = (client.profile().get("data") or {})
        profile = data.get("display_name") or data.get("name") or ""
    except FyersError:
        pass
    return {"ok": True, "expires_at": saved.get("expires_at"),
            "profile": profile}


def _cmd_exchange(code: str, client: Optional[FyersClient] = None,
                  store: Optional[TokenStore] = None) -> int:
    conf = credentials()
    if not conf["app_id"] or not conf["secret_id"]:
        print("FYERS_APP_ID / FYERS_SECRET_ID are not configured (.env)",
              file=sys.stderr)
        return 2
    client = client or FyersClient(app_id=conf["app_id"], access_token="")
    try:
        digest = app_id_hash(conf["app_id"], conf["secret_id"])
    except FyersAuthError as exc:
        print(f"credentials incomplete: {exc}", file=sys.stderr)
        return 2
    body = {
        "grant_type": "authorization_code",
        "appIdHash": digest,
        "code": extract_auth_code(code),
    }
    try:
        response = client._request("POST", f"{API_BASE}/validate-authcode",
                                   body=body, require_auth=False)
    except FyersError as exc:
        print("token exchange FAILED:", exc, f"(code={exc.code})")
        print("Hints: auth codes are single-use and short-lived; if the code "
              "is rejected, rerun login-url. If the broker says the app hash "
              "is invalid, verify FYERS_SECRET_ID (O vs 0 ambiguity).")
        return 2
    token = response.get("access_token") or ""
    if not token:
        print("token exchange returned no access_token:", response)
        return 2
    save = (store or TokenStore()).save(
        token, response.get("refresh_token") or "")
    client.token = token
    print("token stored:", save["expires_at"], "IST")
    try:
        profile = client.profile()
        data = profile.get("data") or {}
        print("profile:", data.get("display_name") or data.get("name") or "ok")
    except FyersError as exc:
        print("profile check FAILED —", exc)
    return 0


def _cmd_screeners(client: FyersClient) -> int:
    try:
        config = client.screeners_config()
        print(json.dumps(config, indent=2)[:4000])
        return 0
    except FyersError as exc:
        print("screeners unavailable:", exc, f"(code={exc.code})")
        return 2


def _cmd_probe(client: FyersClient, symbol: str) -> int:
    today = dt.datetime.now(IST).date()
    candles = client.history_candles(
        symbol, range_from=(today - dt.timedelta(days=15)).isoformat(),
        range_to=today.isoformat())
    rows = _fmt_candles(candles)
    print(f"{to_fyers_symbol(symbol)}: {len(rows)} candles in the last 15 days")
    for row in rows[-5:]:
        print(" ", row)
    try:
        print("quote:", json.dumps(client.quotes([symbol]).get(symbol, {}))[:500])
    except FyersError as exc:
        print("quote FAILED —", exc)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"

    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if cmd == "login-url":
        print(build_auth_url())
        print("\nOpen the URL, approve the app, then copy the auth_code "
              "parameter from the redirected URL.")
        return 0
    if cmd == "exchange":
        code = ""
        if "--code" in argv:
            index = argv.index("--code")
            code = argv[index + 1] if index + 1 < len(argv) else ""
            if not code or code.startswith("--"):
                print("--code needs an auth_code value", file=sys.stderr)
                return 64
        else:
            code = input("Paste the auth_code (or the full redirect URL): ")
        return _cmd_exchange(code)
    if cmd == "clear":
        TokenStore().clear()
        print("token file removed")
        return 0
    if cmd == "refresh":
        try:
            result = FyersClient().refresh_access_token()
            print(json.dumps(result, indent=2))
            return 0
        except FyersError as exc:
            print("token refresh FAILED:", exc, f"(code={exc.code})")
            print("Refresh needs FYERS_PIN in .env plus a stored refresh_token "
                  "from one browser login. Otherwise redo login-url/exchange.")
            return 2
    client = FyersClient()
    if cmd == "status":
        if client.token_store.expired():
            print("WARNING: stored token is past its expiry; re-run login.")
        return _cmd_status(client)
    if cmd == "screeners":
        return _cmd_screeners(client)
    if cmd == "probe":
        symbol = argv[1] if len(argv) > 1 else "SBIN"
        return _cmd_probe(client, symbol)
    print(f"unknown command: {cmd}", file=sys.stderr)
    print("commands: login-url | exchange [--code X] | refresh | status | "
          "probe [SYMBOL] | screeners | clear", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
