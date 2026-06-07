# World Cup Analyzer API — endpoint reference

Base URL (production): `https://www.jiajielitong.com`
Base URL (local dev): `http://localhost:8000`
Interactive OpenAPI docs: `<base>/docs`
OpenAPI JSON: `<base>/openapi.json`
Auth: `X-API-Key: <your_key>` (every request)

The default production hostname is `https://www.jiajielitong.com`.
Override via `WORLDCUP_API_BASE` env var for local dev or staging.

## `GET /matches/teams/`

Return the list of supported national teams for a competition. Use this to
validate user-supplied team names **before** calling `/matches/predict/`,
so typos don't burn prediction quota.

### Query string

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `competition` | string | ✗ | `"worldcup"` | `"worldcup"`; `"england-premium"` is reserved for future support |

### Response

```json
{
  "competition": "worldcup",
  "teams": [
    "Algeria", "Argentina", "Australia", "...", "Uzbekistan"
  ]
}
```

The client wraps this in `list_teams(competition)` with a **12-hour
in-memory cache** (longer than the 6h predict cache, since rosters change
much less often). Pair it with `validate_team(name, competition)` which
returns `(True, canonical_name)` or `(False, fuzzy_suggestion)`.

### Curl example

```bash
curl -X GET 'https://www.jiajielitong.com/matches/teams/?competition=worldcup' \
  -H 'X-API-Key: your_key'
```

## `POST /matches/predict/`

Predict the outcome of a match between two national teams. The model is a
linear regression using player strength, coach level, club ratings, and
other factors.

### Request body (JSON)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `home_team` | string | ✓ | — | e.g. `"Germany"`, `"Argentina"` |
| `visitor_team` | string | ✓ | — | e.g. `"France"`, `"Brazil"` |
| `competition` | string | ✗ | `"worldcup"` | `"worldcup"`; `"england-premium"` is reserved for future support |

This skill defaults `competition` to `"worldcup"` since the host project is
about the 2026 World Cup. The client always sends an explicit
`competition` value. `england-premium` is accepted by the client as a
reserved future value and should be used only after the upstream API enables
that competition.

### Response

```json
{
  "results": {
    "home_team": "Germany",
    "visitor_team": "France",
    "win_goals": -0.02,
    "win_or_not": "Loss",
    "updatedAt": "2026-06-03 17:08:18.681524"
  },
  "usage": {
    "used": 37,
    "limit": -1,
    "vip_level": "deluxe_vip"
  }
}
```

| Field | Meaning |
|---|---|
| `code` | Optional. Absent on success in current API; when present, `200` = success, `403` = auth/quota error. Treat presence of `results` as the authoritative success signal. |
| `results.win_goals` | Expected goal difference (home minus away). Positive = home advantage. May be a float (`-0.02`) or stringified float (`"0.7"`). |
| `results.win_or_not` | `"Win"` / `"Draw"` / `"Loss"`, **from the home team's POV**. |
| `results.updatedAt` | Model-snapshot timestamp. Useful as a freshness hint. |
| `usage.used` | Predictions consumed by the current key. |
| `usage.limit` | Total quota on the current plan. **`-1` means unlimited** (e.g. `deluxe_vip`); never render as `-1` to users. |
| `usage.vip_level` | Plan tier (`free`, `pro`, `deluxe_vip`, etc.). |

### Curl example

```bash
curl -X POST 'https://www.jiajielitong.com/matches/predict/' \
  -H 'X-API-Key: your_key' \
  -H 'Content-Type: application/json' \
  -d '{
    "home_team": "Germany",
    "visitor_team": "France",
    "competition": "worldcup"
  }'
```

### Error cases

The API may return:

- HTTP `200` with `code: 403` — auth failure (bad/missing key) **or** quota
  exhausted. The error message in `message` / `error` distinguishes them.
- HTTP `429` — rate limit; honor `Retry-After`.
- HTTP `5xx` — upstream issue; retry with backoff.
- HTTP `404` — wrong path; verify `WORLDCUP_API_BASE`.
