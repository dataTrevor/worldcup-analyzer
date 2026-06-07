# worldcup-analyzer

Mira/Claude-Code Skill for predicting outcomes of national-team football
matches using a remote regression-model API at
`https://www.jiajielitong.com`. Defaults to the 2026 FIFA World Cup;
`england-premium` is reserved for upcoming API support. Statistical
analysis only — **not** betting advice.

## Layout

```
worldcup-analyzer/
├── SKILL.md                  # Skill manifest + agent instructions
├── README.md                 # This file (human-facing)
├── requirements.txt          # Python deps (httpx preferred, requests fallback)
├── scripts/
│   └── wc_client.py          # HTTP client, cache, formatter, validator
├── references/
│   ├── api.md                # Endpoint reference (/teams/, /predict/)
│   ├── team_names.md         # Canonical 48-team list + alias map
│   └── compliance.md         # HK Cap. 148 refusal templates and rules
└── evals/
    ├── evals.json            # 4 eval cases
    └── run_evals.py          # Local runner — hits the live API
```

## Quick start

```bash
export SOCCER_API_KEY="your_key_here"
export WORLDCUP_API_BASE="https://www.jiajielitong.com"   # optional; this is the default
pip install -r requirements.txt
python3 evals/run_evals.py
```

## What the client gives you

| Function | Purpose |
|---|---|
| `predict_match(home, away, competition="worldcup")` | Outcome + expected goal diff. 6h in-memory TTL cache. |
| `list_teams(competition="worldcup")` | Canonical team list from `GET /matches/teams/`. 12h TTL cache. |
| `validate_team(name, competition)` | `(True, canonical)` or `(False, fuzzy_suggestion)`. Cheap — uses cached team list. |
| `format_prediction(data)` | Margin-aware renderer with mandatory compliance disclaimer. Flags near-draws when `|win_goals| < 0.10`. |
| `format_response(body)` | Appends disclaimer to any custom string. |
| `quota_warning(data)` | Returns a short heads-up at ≥ 80% quota; `None` on unlimited (`limit == -1`) tier. |
| `canonicalize_team_name(name)` | Alias map only (no API call). |
| `cache_clear()` | Reset both predict + teams caches. |

## Compliance hard constraints

- No phrases like `recommended bet`, `sure win`, `lock`, `tips`, `稳赢`, `推荐`.
- Disclaimer is automatic and must not be stripped.
- Refuse betting picks, stake sizing, bookmaker odds, anyone identifying as under 18.

See `references/compliance.md` for full text + refusal templates.
