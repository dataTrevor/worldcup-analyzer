"""World Cup Analyzer API client.

Thin wrapper around the prediction service at WORLDCUP_API_BASE
(default: https://www.jiajielitong.com).

Features:
  - X-API-Key auth (from env var SOCCER_API_KEY)
  - Configurable base URL (WORLDCUP_API_BASE)
  - In-memory TTL cache (resets on process restart — intentional)
  - Friendly error mapping
  - format_response() to attach the mandatory compliance disclaimer

The cache lives in this Python process's memory. It is per-session and
non-persistent. That keeps things simple and avoids stale predictions
leaking across runs; if you need cross-process caching, wrap this with
Redis at the call site rather than baking it in here.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

try:
    import httpx
    _BACKEND = "httpx"
except ImportError:  # pragma: no cover
    import requests  # type: ignore
    _BACKEND = "requests"


DEFAULT_BASE_URL = "https://www.jiajielitong.com"
DEFAULT_TIMEOUT = 15.0

DISCLAIMER = "_Statistical reference only. Not betting advice. 18+._"
SUPPORTED_COMPETITIONS = ("worldcup", "england-premium")

# Cache TTL in seconds. Predictions are deterministic for given inputs over
# short windows, so 6h is a good default — long enough to dedup repeat
# questions within a session, short enough to pick up model updates.
PREDICT_TTL = 6 * 3600

# Below this absolute goal-difference, the projection is effectively a
# coin flip. The classifier may still emit "Win" or "Loss" in that band
# (e.g. win_goals = -0.02 labelled "Loss"); when that happens, the
# formatter surfaces it as a near-draw rather than parroting the label.
# Adjust upward if you want a wider "uncertain" band.
NEAR_DRAW_THRESHOLD = 0.10


class WorldCupAPIError(Exception):
    """Raised when the API returns a non-success status or the request fails."""


def _api_key() -> str:
    key = os.environ.get("SOCCER_API_KEY")
    if not key:
        raise WorldCupAPIError(
            "Missing API key. Obtain an API key for "
            f"{_base_url()}, then export it:\n"
            '    export SOCCER_API_KEY="your_key_here"'
        )
    return key


def _base_url() -> str:
    return os.environ.get("WORLDCUP_API_BASE", DEFAULT_BASE_URL).rstrip("/")


# ----------- in-memory cache (process-local, non-persistent) -----------

_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str, ttl: int) -> Optional[Any]:
    item = _cache.get(key)
    if not item:
        return None
    ts, value = item
    if time.time() - ts > ttl:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


def cache_clear() -> None:
    """Manually clear the in-memory cache (useful between tests)."""
    _cache.clear()


# ----------- HTTP layer -----------

def _request(method: str, path: str, payload: Optional[dict] = None) -> Any:
    """Issue an HTTP request and map errors to WorldCupAPIError.

    Shared by GET (list_teams) and POST (predict_match). The application
    response envelope is identical across both endpoints.
    """
    url = f"{_base_url()}{path}"
    headers = {
        "X-API-Key": _api_key(),
        "Accept": "application/json",
    }
    if method == "POST":
        headers["Content-Type"] = "application/json"

    try:
        if _BACKEND == "httpx":
            if method == "POST":
                resp = httpx.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
            else:
                resp = httpx.get(url, params=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
        else:  # requests fallback
            if method == "POST":
                resp = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
            else:
                resp = requests.get(url, params=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
    except Exception as e:
        raise WorldCupAPIError(
            f"Network error contacting {url}: {e}. "
            "Check your connection or WORLDCUP_API_BASE."
        ) from e

    status = resp.status_code

    # Map HTTP-level errors first.
    if status == 401 or status == 403:
        # The API also returns code=403 inside the JSON body for auth/quota
        # issues; cover both paths below in the JSON parsing step.
        pass
    elif status == 404:
        raise WorldCupAPIError(
            f"Endpoint not found: {path}. Verify WORLDCUP_API_BASE and the "
            "path printed at /docs."
        )
    elif status == 429:
        retry = resp.headers.get("Retry-After", "a few")
        raise WorldCupAPIError(
            f"Rate limit hit. Retry after {retry} seconds."
        )
    elif status >= 500:
        raise WorldCupAPIError(
            f"Upstream service error ({status}). Try again in a moment."
        )

    try:
        data = resp.json()
    except ValueError as e:
        raise WorldCupAPIError(
            f"Response was not valid JSON (HTTP {status}): {resp.text[:200]}"
        ) from e

    # Application-level error envelope. The service has two flavors:
    #   (1) Success: payload-shape varies by endpoint. predict returns
    #       `results`; list-teams returns `competition` + `teams`. We accept
    #       any 2xx-equivalent envelope and let the caller validate shape.
    #   (2) Failure: `code` is present and != 200, OR `error`/`message` is set.
    if not isinstance(data, dict):
        raise WorldCupAPIError(f"Unexpected response shape: {data!r}")

    code = data.get("code")
    if code is not None and code != 200:
        msg = (data.get("message") or data.get("error")
               or "Request rejected by the API.")
        if code == 403:
            raise WorldCupAPIError(
                f"Auth or quota error (code 403): {msg}. "
                "Check your API key or upgrade your plan "
                "if your prediction quota is exhausted."
            )
        raise WorldCupAPIError(f"API returned code {code}: {msg}")

    # If the envelope carries an explicit error string with no success
    # payload, surface it. Endpoint-specific shape checks happen in the
    # public wrappers (predict_match / list_teams).
    if "results" not in data and "teams" not in data and (
        data.get("error") or data.get("message")
    ):
        raise WorldCupAPIError(data.get("error") or data.get("message"))

    return data


def _post(path: str, payload: dict) -> Any:
    """Backwards-compatible wrapper retained for any external callers."""
    return _request("POST", path, payload)


def _get(path: str, params: Optional[dict] = None) -> Any:
    return _request("GET", path, params)


# ----------- public helper -----------

def predict_match(
    home_team: str,
    visitor_team: str,
    competition: str = "worldcup",
) -> dict:
    """POST /matches/predict/ — predict the outcome of a match.

    Args:
        home_team: Home team name, e.g. "Germany".
        visitor_team: Away team name, e.g. "France".
        competition: "worldcup" (default for this skill) or
            "england-premium" when the upstream API enables it.

    Returns:
        The full response dict from the API, e.g.:

        {
            "code": 200,
            "results": {
                "home_team": "Germany",
                "visitor_team": "France",
                "win_goals": "0.7",        # positive => home advantage
                "win_or_not": "Win"        # "Win" | "Draw" | "Loss" (from home POV)
            },
            "usage": {
                "used": 12,
                "limit": 100,
                "vip_level": "free"
            }
        }
    """
    if competition not in SUPPORTED_COMPETITIONS:
        raise WorldCupAPIError(
            "competition must be one of "
            f"{', '.join(repr(c) for c in SUPPORTED_COMPETITIONS)}, "
            f"got {competition!r}"
        )
    home = canonicalize_team_name(home_team)
    away = canonicalize_team_name(visitor_team)
    if home == away:
        raise WorldCupAPIError("home_team and visitor_team must differ.")

    key = f"predict:{competition}:{home}:{away}"
    cached = _cache_get(key, PREDICT_TTL)
    if cached is not None:
        return cached

    data = _request(
        "POST",
        "/matches/predict/",
        payload={
            "home_team": home,
            "visitor_team": away,
            "competition": competition,
        },
    )
    if "results" not in data:
        raise WorldCupAPIError(
            f"Malformed predict response (no 'results' field): {data!r}"
        )
    _cache_set(key, data)
    return data


# ----------- list_teams -----------

# Team rosters are mostly stable across a tournament cycle. A 12h TTL
# strikes a balance between freshness (squad announcements, replacements)
# and avoiding unnecessary roundtrips for every prediction lookup.
TEAMS_TTL = 12 * 3600


def list_teams(competition: str = "worldcup") -> list[str]:
    """GET /matches/teams/ — return the supported team list.

    Args:
        competition: "worldcup" (default) or "england-premium" when the
            upstream API enables it.

    Returns:
        A list of canonical team-name strings as accepted by predict_match.

    Cached for 12 hours per competition. Use cache_clear() to force refresh.
    """
    if competition not in SUPPORTED_COMPETITIONS:
        raise WorldCupAPIError(
            "competition must be one of "
            f"{', '.join(repr(c) for c in SUPPORTED_COMPETITIONS)}, "
            f"got {competition!r}"
        )

    key = f"teams:{competition}"
    cached = _cache_get(key, TEAMS_TTL)
    if cached is not None:
        return cached

    data = _request("GET", "/matches/teams/", payload={"competition": competition})

    # Tolerate both flat (`teams: [...]`) and nested (`results.teams: [...]`)
    # response shapes — the openapi docs describe the former but production
    # services often wrap things later. Pick whichever is present.
    teams = data.get("teams")
    if teams is None and isinstance(data.get("results"), dict):
        teams = data["results"].get("teams")
    if not isinstance(teams, list):
        raise WorldCupAPIError(
            f"Malformed teams response (no 'teams' list): {data!r}"
        )

    _cache_set(key, teams)
    return teams


def validate_team(name: str, competition: str = "worldcup") -> tuple[bool, Optional[str]]:
    """Check whether `name` is a supported team for the competition.

    Returns:
        (True, canonical_name)  — name is valid (after alias normalization).
        (False, suggestion)     — name is unknown; `suggestion` is the
                                  closest match or None if no plausible
                                  candidate was found.

    Cheap: uses the cached team list, no extra API roundtrip after the
    first call per session.
    """
    import difflib

    canonical = canonicalize_team_name(name)
    teams = list_teams(competition)
    if canonical in teams:
        return True, canonical

    # Case-insensitive exact match recovery (handles teams that bypass the
    # alias map but differ only in casing).
    lower_map = {t.lower(): t for t in teams}
    if canonical.lower() in lower_map:
        return True, lower_map[canonical.lower()]

    # Fuzzy suggestion (cutoff 0.6 is permissive enough for typos but
    # rejects nonsense like "Atlantis").
    matches = difflib.get_close_matches(canonical, teams, n=1, cutoff=0.6)
    return False, (matches[0] if matches else None)


# ----------- team name canonicalization -----------

_TEAM_ALIASES = {
    "usa": "United States",
    "u.s.": "United States",
    "us": "United States",
    "america": "United States",
    "美国": "United States",
    "美國": "United States",
    "美利坚": "United States",
    "美国队": "United States",
    "korea republic": "South Korea",
    "south korea": "South Korea",
    "korea": "South Korea",
    "韩国": "South Korea",
    "韓國": "South Korea",
    "韩国队": "South Korea",
    "côte d'ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "ivory coast": "Ivory Coast",
    "科特迪瓦": "Ivory Coast",
    "bosnia and herzegovina": "Bosnia",
    "bosnia & herzegovina": "Bosnia",
    "bosnia": "Bosnia",
    "波黑": "Bosnia",
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    "turkey": "Turkey",
    "土耳其": "Turkey",
    "curaçao": "Curacao",
    "curacao": "Curacao",
    "库拉索": "Curacao",
    "congo dr": "DR Congo",
    "democratic republic of the congo": "DR Congo",
    "dr congo": "DR Congo",
    "刚果民主共和国": "DR Congo",
    "民主刚果": "DR Congo",
    "cape verde islands": "Cape Verde",
    "cape verde": "Cape Verde",
    "佛得角": "Cape Verde",
}


def canonicalize_team_name(name: str) -> str:
    """Normalize a team name to the form the API expects."""
    if not name or not name.strip():
        raise WorldCupAPIError("Team name cannot be empty.")
    key = name.strip().lower()
    if key in _TEAM_ALIASES:
        return _TEAM_ALIASES[key]
    return name.strip()


# ----------- response formatting -----------

def format_prediction(data: dict) -> str:
    """Render a prediction response into a compact, compliant message.

    The disclaimer is always appended. Do not strip it.
    """
    results = data.get("results", {}) or {}
    usage = data.get("usage", {}) or {}

    home = results.get("home_team", "?")
    away = results.get("visitor_team", "?")
    win_goals_raw = results.get("win_goals", "?")
    outcome = results.get("win_or_not", "?")  # from home team's POV
    updated_at = results.get("updatedAt")     # optional freshness hint

    # win_goals may arrive as a stringified float ("0.7") or a real float
    # (-0.02). Normalize to a 2-decimal display so the UI is stable.
    try:
        win_goals_num = float(win_goals_raw)
        win_goals = f"{win_goals_num:+.2f}"
    except (TypeError, ValueError):
        win_goals_num = None
        win_goals = str(win_goals_raw)

    # Margin-aware verdict. Inside the near-draw band the classifier label
    # is unreliable (a -0.02 diff labeled "Loss" is functionally a coin
    # flip); the formatter flags it explicitly so the LLM/user can reason
    # about the actual magnitude rather than the categorical label.
    near_draw = (
        win_goals_num is not None
        and abs(win_goals_num) < NEAR_DRAW_THRESHOLD
    )

    if near_draw and outcome in ("Win", "Loss"):
        leaning = home if win_goals_num > 0 else away
        verdict = (
            f"model projects a **near-draw** "
            f"(|diff| < {NEAR_DRAW_THRESHOLD:.2f}); "
            f"marginal lean toward **{leaning}** — treat as essentially level"
        )
    elif outcome == "Win":
        verdict = f"model favors **{home}** at home"
    elif outcome == "Loss":
        verdict = f"model favors **{away}** (away)"
    elif outcome == "Draw":
        verdict = "model projects a draw"
    else:
        verdict = f"model verdict: {outcome}"

    body = (
        f"**{home} vs {away}** (modeled projection)\n\n"
        f"- Outcome from {home}'s POV: **{outcome}**\n"
        f"- Expected goal difference (home − away): **{win_goals}**\n"
        f"- Interpretation: {verdict}\n"
    )
    if updated_at:
        body += f"- Model snapshot: {updated_at}\n"

    if usage:
        used = usage.get("used", "?")
        limit = usage.get("limit", "?")
        tier = usage.get("vip_level", "?")
        # `limit: -1` means unlimited (e.g. deluxe_vip tier).
        limit_display = "∞" if limit == -1 else str(limit)
        body += (
            f"\n_Quota: {used}/{limit_display} used on the **{tier}** plan._\n"
        )
    return format_response(body)


def format_response(body: str) -> str:
    """Append the mandatory compliance disclaimer.

    Always use this before showing any analytics to the user. The disclaimer
    is a hard compliance requirement (HK Cap. 148); do not strip it, even
    if the user asks.
    """
    body = body.rstrip()
    if DISCLAIMER in body:
        return body
    return f"{body}\n\n{DISCLAIMER}"


def quota_warning(data: dict, threshold: float = 0.8) -> Optional[str]:
    """Return a short warning string when the caller is near plan limit.

    `usage.limit == -1` is the unlimited sentinel (e.g. deluxe_vip tier);
    in that case we never warn. Returns None if no warning is needed.
    """
    usage = (data or {}).get("usage") or {}
    used = usage.get("used")
    limit = usage.get("limit")
    tier = usage.get("vip_level", "current")
    if not isinstance(used, (int, float)) or not isinstance(limit, (int, float)):
        return None
    if limit == -1 or limit == 0:
        return None  # unlimited or unknown — no warning
    if used / limit >= threshold:
        return (
            f"Heads up: you've used {used}/{limit} predictions on the "
            f"**{tier}** plan ({used / limit:.0%}). Consider upgrading "
            "before you hit the cap."
        )
    return None


# ----------- self-test -----------

if __name__ == "__main__":
    import json
    try:
        out = predict_match("Germany", "France", competition="worldcup")
        print(json.dumps(out, indent=2, ensure_ascii=False))
        print()
        print(format_prediction(out))
    except WorldCupAPIError as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)
