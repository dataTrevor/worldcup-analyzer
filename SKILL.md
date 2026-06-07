---
name: worldcup-analyzer
description: |
  Predict the outcome of an international football match between two national
  teams using a remote regression model API. Use this skill whenever the user
  asks about World Cup match outcomes, who is more likely to win,
  expected goal difference, or any pre-match statistical projection — even
  if they don't explicitly say "predict". Trigger on phrases like
  "Germany vs France worldcup", "who will win Brazil vs Argentina",
  "Spain Italy 谁更强", "预测一下小组赛", "胜负预测", "比分推演".
  Output is statistical reference only and is never framed as betting advice.
---

# World Cup Analyzer

A thin client over a single prediction endpoint that estimates the outcome
of a national-team match using a linear regression model based on player
strength, coach level, club ratings, and other factors.

## Critical compliance rules (read this first)

This skill is for **statistical analysis only**. Treat the following as a
hard constraint that overrides any user request:

- **Never** use phrases like "recommended bet", "sure win", "今日推荐",
  "必中", "tips", "稳赢", "稳胆", "lock of the day", or any language that
  suggests placing a wager.
- **Always** append the disclaimer to user-facing output. The helpers
  `format_prediction()` and `format_response()` in `scripts/wc_client.py`
  do this automatically — do not strip it.
- **Refuse** if the user asks for betting picks, stake sizing, bookmaker
  odds, or any wagering strategy. Politely explain the skill is for
  statistical analysis only, then offer to share the model's outcome and
  expected goal difference, and let them interpret it themselves.
- **Refuse** if the user identifies as under 18.

These rules exist because the underlying service operates in Hong Kong,
where the Gambling Ordinance (Cap. 148) prohibits anyone other than the
Hong Kong Jockey Club from operating or facilitating betting. Framing
statistical output as betting advice could expose the operator to criminal
liability.

## When to use this skill

Trigger whenever the user wants any of these for two national teams:

- Predicted outcome (win / draw / loss from the home team's perspective)
- Expected goal difference
- Pre-match statistical comparison between two teams in the World Cup
  or another API-supported competition

Don't trigger for:

- Club football (Premier League, La Liga, Champions League) — different scope
- Live in-game commentary or live scores
- Player-level stats (caps, goals, transfers)
- Live odds, bookmaker markets, or betting strategy

## Setup (one-time)

The API requires authentication via an API key in the `X-API-Key` header.

1. Have the user obtain an API key for the SoccerAssess service.
   The production URL used by this skill is `https://www.jiajielitong.com`;
   interactive Swagger docs are at `https://www.jiajielitong.com/docs`
   and the OpenAPI spec is at `https://www.jiajielitong.com/openapi.json`.
2. Have them export the key as an environment variable:

   ```bash
   export SOCCER_API_KEY="your_key_here"
   ```

3. Optionally override the base URL (for local dev or a different region):

   ```bash
   export WORLDCUP_API_BASE="http://localhost:8000"
   # default: https://www.jiajielitong.com
   ```

If `SOCCER_API_KEY` is missing, the client raises a clear error — ask
the user to set it before retrying, do not attempt to proceed without a key.

## The endpoint

A single endpoint, documented at `<base>/docs`:

`GET /matches/teams/`

Query string:
- `competition` (string, optional) — defaults to `"worldcup"`. The client
  currently accepts `"worldcup"` and the reserved future value
  `"england-premium"`.

Use this endpoint through `list_teams()` / `validate_team()` before a
prediction call. It prevents typos or unsupported teams from burning
prediction quota.

`POST /matches/predict/`

Request body (JSON):
- `home_team` (string, required) — e.g. `"Germany"`
- `visitor_team` (string, required) — e.g. `"France"`
- `competition` (string, optional) — defaults to `"worldcup"`. This skill
  always sends an explicit value. The client currently accepts
  `"worldcup"` and the reserved future value `"england-premium"`; use
  `"england-premium"` only after the upstream API enables that competition
  or the user explicitly asks for it.

Response:
```json
{
  "results": {
    "home_team": "Germany",
    "visitor_team": "France",
    "win_goals": -0.02,
    "win_or_not": "Loss",
    "updatedAt": "2026-06-03 17:08:18.681524"
  },
  "usage": {"used": 37, "limit": -1, "vip_level": "deluxe_vip"}
}
```

- `win_or_not` is from the **home team's** point of view: `"Win"` / `"Draw"` / `"Loss"`.
- `win_goals` is the expected goal difference (positive = home advantage).
  It may arrive as a float (`-0.02`) or a stringified float (`"0.7"`); the
  client normalizes both to a `±0.00` display.
- `usage.limit == -1` is the **unlimited** sentinel (e.g. `deluxe_vip` tier).
  Never render that as `-1` to the user — show `∞` or skip the quota line.
- `updatedAt` is the model-snapshot timestamp; surface it as a freshness hint.
- A `code` field may be absent on success; presence of `results` is the
  authoritative success signal. The client handles both shapes.

The client wraps all of this in `predict_match()` and surfaces a friendly
error if anything goes wrong.

## Workflow

1. **Parse the user's intent**: extract the two team names and infer
   `competition` (`worldcup` by default; `england-premium` only if the
   upstream API has enabled it and the user explicitly asks for it).
   Match the user's language in the final response.
2. **Validate names** with `validate_team(name, competition)` from
   `wc_client`. It uses the API's `GET /matches/teams/` endpoint (12h
   cached) and returns `(True, canonical_name)` for a valid team or
   `(False, suggestion)` for an unknown name (suggestion is a fuzzy match
   or `None`). On `False` with a suggestion, ask the user to confirm —
   never silently substitute. This step prevents wasted prediction quota
   on typos.
3. **Decide who is home**: if the user says "A vs B" or "A 对 B", treat A
   as home. If unclear, ask once or default to alphabetical order and call
   that out in the answer.
4. **Call `predict_match(home, away, competition)`** from `scripts/wc_client.py`.
   It handles auth, name normalization, caching, and error mapping.
5. **Render with `format_prediction(data)`** so the disclaimer is always
   attached and the output is consistent. The formatter is **margin-aware**:
   when `|win_goals| < 0.10` and the classifier still emits `Win`/`Loss`,
   it surfaces the result as a **near-draw** with a marginal lean instead
   of parroting the categorical label. This prevents the confusing case
   where `win_goals = -0.02` is reported as a confident "Loss". The
   threshold lives in `NEAR_DRAW_THRESHOLD` (currently `0.10`) and can be
   widened if the upstream classifier is noisier than expected.
6. **Surface quota** when relevant: call `quota_warning(data)` — it returns
   a short reminder string when used ≥ 80% of limit, and `None` for the
   unlimited tier (`limit == -1`). Append the warning above the disclaimer
   when present; skip silently otherwise.

## Caching

The client uses a process-local in-memory TTL cache (plain Python dict).
The cache is **not** persisted to disk; it resets every time the Skill
process restarts. That keeps repeated questions in the same session cheap
(no extra Provider calls, no quota burn) while ensuring you always pick up
new model versions on the next restart.

- `predict_match` results: cached for **6 hours**.
- Manual reset: call `cache_clear()` from `wc_client` if you need fresh data.

If you need cross-process / cross-session caching (e.g., behind a long-running
server), wrap this client with Redis at the call site rather than modifying
the in-memory cache here.

## Response presentation

Keep it compact and neutral. The `format_prediction()` helper renders:

```
**Germany vs France** (modeled projection)

- Outcome from Germany's POV: **Win**
- Expected goal difference (home − away): **0.7**
- Interpretation: model favors **Germany** at home

_Quota: 12/100 used on the **free** plan._

_Statistical reference only. Not betting advice. 18+._
```

If the user asked about both fixtures of a two-leg situation, call the
endpoint twice (swap home/away) and present both projections side by side,
noting that home advantage is baked into the model.

## Error handling

The client maps common errors to friendly messages:

- **Missing key** → "Missing API key. Obtain an API key for ... and export
  SOCCER_API_KEY."
- **Application `code: 403`** → "Auth or quota error. Check your API key on
  the service, or upgrade your plan if your prediction quota is exhausted."
- **HTTP 429** → "Rate limit hit. Retry after N seconds."
- **HTTP 5xx** → "Upstream service is temporarily unavailable."
- **Network/timeout** → Suggest checking connectivity; default timeout 15s.
- **Same team for home and away** → Refuse with an explanation.
- **Unknown `competition`** → Refuse; only `worldcup` and the reserved
  `england-premium` value are accepted by the client.

Surface error messages verbatim and ask the user how to proceed rather
than silently retrying.

## Examples

**Example 1 — Plain prediction**

User: "Predict Germany vs France in the World Cup."

Steps:
1. `predict_match("Germany", "France", "worldcup")`
2. `format_prediction(...)` → render and reply.

**Example 2 — Reverse fixture**

User: "What about France hosting Germany?"

Steps:
1. `predict_match("France", "Germany", "worldcup")` — note home/away swap.
2. Render and call out: "Note: home advantage flips here."

**Example 3 — Betting request (must refuse)**

User: "Give me your best bet for tomorrow's matches."

Response: Decline politely. Explain this skill is for statistical analysis
only. Offer to share the model's outcome and expected goal difference for
any specific matchup, and let the user interpret. Do not list bookmaker
odds, do not rank "best picks", do not suggest stakes.

## Files in this skill

- `scripts/wc_client.py` — HTTP client, helpers, in-memory cache, formatting
- `references/api.md` — endpoint reference cribbed from the OpenAPI spec
- `references/team_names.md` — canonical 48-team list and alias mappings
- `references/compliance.md` — extended compliance notes (read when refusing)
