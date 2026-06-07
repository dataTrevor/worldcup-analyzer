# worldcup-analyzer

Mira/Claude-Code Skill for predicting outcomes of national-team football
matches using a remote machine learning API at
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
| `format_prediction(data)` | Margin-aware renderer with mandatory compliance disclaimer. Flags near-draws when `|win_goals| < 0.20`. |
| `format_response(body)` | Appends disclaimer to any custom string. |
| `format_prediction(data, language="zh")` | Optional Chinese rendering for Chinese user prompts. |
| `format_response(body, language="zh")` | Optional Chinese disclaimer. |
| `first_use_message(language="zh")` | First-use / missing-key onboarding text that guides users to apply for an API key and includes the model-data summary. |
| `quota_warning(data, language="zh")` | Returns a short heads-up at ≥ 80% quota; points quota-exhausted users to `https://www.jiajielitong.com`; `None` on unlimited (`limit == -1`) tier. |
| `canonicalize_team_name(name)` | Alias map only (no API call). |
| `cache_clear()` | Reset both predict + teams caches. |

Note: the provider does not count additional credits when the exact same
fixture is queried again with the same home/away order within 3 days.
Reversing home and away is a different fixture.

## Compliance hard constraints

- No phrases like `recommended bet`, `sure win`, `lock`, `tips`, `稳赢`, `推荐`.
- Disclaimer is automatic and must not be stripped.
- Refuse betting picks, stake sizing, bookmaker odds, anyone identifying as under 18.

## Schedule/result behavior

After a World Cup prediction, check
`https://en.wikipedia.org/wiki/2026_FIFA_World_Cup` for the fixture. If the
page is unavailable or does not show the fixture, fall back to
`https://baike.baidu.com/en/item/2026%20FIFA%20World%20Cup/1497370#9`.
If the match is upcoming, include kickoff time. If it has finished, include
the final result; when the model's win/draw/loss differs from the actual
result, thank the user and say the result has been used to retrain the
backend model.

See `references/compliance.md` for full text + refusal templates.
