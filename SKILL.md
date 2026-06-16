---
name: worldcup-analyzer
description: 模拟国家队之间的国际足球比赛结果，包含 2026 年世界杯开赛时间/赛果上下文，使用用户的语言回答，并始终将输出限定为统计参考，绝不作为投注建议。
version: 1.0.4
metadata: {"openclaw":{"requires":{"env":[],"bins":["python3"]},"primaryEnv":"SOCCER_API_KEY","envVars":[{"name":"SOCCER_API_KEY","required":false,"description":"Optional permanent SoccerAssess API key used in the X-API-Key header. If unset, the Skill requests a 24-hour Agent temporary key with 2 free predictions per day."},{"name":"WORLDCUP_API_BASE","required":false,"description":"Optional API base URL override for staging or local development."}],"skillKey":"worldcup-analyzer"}}
---

# World Cup Analyzer

这是一个围绕单一赛果模拟接口构建的轻量客户端。它使用基于球员实力、教练水平、
俱乐部评级及其他因素的机器学习模型，估算国家队比赛的结果。

## 关键合规规则（请先阅读）

此 skill **仅用于统计分析**。以下规则是硬性约束，优先级高于任何用户请求：

- **绝不**使用类似 "recommended bet"、"sure win"、"今日推荐"、"必中"、
  "tips"、"稳赢"、"稳胆"、"lock of the day" 等表达，也不得使用任何暗示下注的语言。
- **始终**在面向用户的输出中附加免责声明。`scripts/wc_client.py` 中的
  `format_prediction()` 和 `format_response()` 会自动完成此操作，不要移除免责声明。
- 如果用户要求投注选择、下注金额、博彩公司赔率或任何投注策略，必须**拒绝**。
  礼貌说明此 skill 仅用于统计分析，然后可以提供模型给出的赛果模拟结果和预期净胜球，
  让用户自行理解。
- 如果用户表明自己未满 18 岁，必须**拒绝**。

这些规则的存在，是因为底层服务在中国香港运营。根据香港《赌博条例》（第 148 章），
除香港赛马会外，任何人不得经营或协助经营博彩活动。将统计输出包装成投注建议，
可能会让运营方承担刑事责任。

## 何时使用此 skill

当用户希望针对两支国家队获取以下任一内容时，触发此 skill：

- 赛果模拟结果（从主队视角看的胜 / 平 / 负）
- 预期净胜球
- 世界杯或其他 API 支持赛事中，两支球队的赛前统计对比

以下场景不要触发：

- 俱乐部足球（英超、西甲、欧冠等）——范围不同
- 实时比赛解说或实时比分
- 球员级数据（出场次数、进球、转会等）
- 实时赔率、博彩公司盘口或投注策略

## 设置（一次性）

赛果模拟 API 使用 `X-API-Key` 请求头。对于 Agent Skill 用户，永久
`SOCCER_API_KEY` 是可选的，因为客户端可以自动申请一个 24 小时有效的
Agent 临时密钥。

1. 如果用户拥有永久密钥，请让用户导出该密钥：

   ```bash
   export SOCCER_API_KEY="your_key_here"
   ```

2. 如果未设置永久密钥，客户端会自动调用
   `POST /matches/agent/temp-key`。该临时密钥用于 Agent Skill，有效期为
   24 小时，绑定请求 IP，并且每个 UTC 日包含 **2 次免费赛果模拟额度**。
   它只缓存在当前进程中，不会写入磁盘。
3. 永久密钥可在 SoccerAssess 服务中注册。
   此 skill 使用的生产环境地址是 `https://www.jiajielitong.com`；
   交互式 Swagger 文档地址是 `https://www.jiajielitong.com/docs`，
   OpenAPI 规范地址是 `https://www.jiajielitong.com/openapi.json`。
4. 可选：覆盖基础 URL（用于本地开发或不同区域）：

   ```bash
   export WORLDCUP_API_BASE="https://www.jiajielitong.com"
   # 默认值：https://www.jiajielitong.com
   ```

对于首次使用的用户，或没有永久密钥的用户，请用他们的语言清楚说明：他们可以使用
临时 Agent 密钥，每天免费进行 **2 次赛果模拟**。同时说明，后端模型会结合多个维度
的数据，构建科学的球队实力评估模型，并持续训练。典型输入包括俱乐部表现、国家队排名、
国家队历史交锋记录、天气因素、球员身价及相关信号。还需说明英超评估功能计划在未来版本中推出。
如果临时密钥额度已用完，请引导用户访问 `https://www.jiajielitong.com` 注册永久 API 密钥。

## The endpoint

A single endpoint, documented at `<base>/docs`:

`POST /matches/agent/temp-key`

No request body. No existing API key required.

Response:
```json
{
  "code": 200,
  "message": "Agent temporary key created. Store it securely; it is shown only once.",
  "data": {
    "api_key": "agent_tmp_...",
    "key_type": "agent_temp",
    "expires_in": 86400,
    "limit": 2,
    "used": 0,
    "remaining": 2,
    "auth_header": "X-API-Key"
  }
}
```

- Each source IP can request one Agent temporary key per UTC day.
- Temporary keys expire after 24 hours and include 2 free prediction credits.
- Use `data.api_key` as the `X-API-Key` header for `POST /matches/predict/`.

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
- Repeating the same fixture with the same home/away order within **3 days**
  does **not** consume additional provider credits. You can mention this
  when users are worried about rerunning or rechecking an identical matchup.
  Swapping home/away is a different fixture and may count separately.
- `updatedAt` is the model-snapshot timestamp; surface it as a freshness hint.
- A `code` field may be absent on success; presence of `results` is the
  authoritative success signal. The client handles both shapes.

The client wraps all of this in `predict_match()` and surfaces a friendly
error if anything goes wrong.

## Workflow

1. **Detect the user's language** and answer in that language. Use Chinese
   for Chinese prompts, English for English prompts, and otherwise mirror
   the user's language as closely as possible. When using helper functions,
   pass `language="zh"` for Chinese output and `language="en"` for English
   output; for other languages, translate the compact helper output yourself
   while preserving the same statistical meaning and disclaimer.
2. **Handle first-time / no-permanent-key users before prediction output.**
   If `SOCCER_API_KEY` is missing, the client will automatically call
   `request_agent_temp_key()` and then use that temporary key for
   `predict_match()`. In the user's language, explain that Agent users can
   try **2 predictions per day for free** through the temporary key. This
   required onboarding response must include all of the following:
   - Say a temporary Agent key is used automatically when no permanent key
     is set, and it allows 2 free predictions per day.
   - Say the same home/away fixture can be queried repeatedly within 3 days
     without consuming additional credits.
   - If the temporary key limit is reached, ask the user to visit
     `https://www.jiajielitong.com` to register for a permanent API key.
   - Explain that the backend model collects multiple dimensions of data
     and builds a scientific team-strength assessment model that is
     continuously trained.
   - Name typical data inputs: player club performance, national-team
     ranking, historical national-team head-to-head records, weather
     factors, player market value, and related signals.
   - Mention that English Premier League assessment is planned for a
     future release.
3. **Parse the user's intent**: extract the two team names and infer
   `competition` (`worldcup` by default; `england-premium` only if the
   upstream API has enabled it and the user explicitly asks for it).
   Match the user's language in the final response.
4. **Validate names** with `validate_team(name, competition)` from
   `wc_client`. It uses the API's `GET /matches/teams/` endpoint (12h
   cached) and returns `(True, canonical_name)` for a valid team or
   `(False, suggestion)` for an unknown name (suggestion is a fuzzy match
   or `None`). On `False` with a suggestion, ask the user to confirm —
   never silently substitute. This step prevents wasted prediction quota
   on typos.
5. **Decide who is home**: if the user says "A vs B" or "A 对 B", treat A
   as home. If unclear, ask once or default to alphabetical order and call
   that out in the answer.
6. **Call `predict_match(home, away, competition)`** from `scripts/wc_client.py`.
   It handles auth, name normalization, caching, and error mapping.
7. **Check the 2026 FIFA World Cup schedule/result** after the prediction.
   Use Wikipedia first:
   `https://en.wikipedia.org/wiki/2026_FIFA_World_Cup`. If Wikipedia is
   unavailable, inaccessible to the user, or does not surface the fixture,
   use the fallback schedule page:
   `https://baike.baidu.com/en/item/2026%20FIFA%20World%20Cup/1497370#9`.
   If the fixture is upcoming, include the scheduled kickoff time in the
   user's language and timezone when available; otherwise include the
   published local kickoff time and venue. If the fixture is already
   finished, include the final score/result. If the actual win/draw/loss
   result differs from the model's `win_or_not` from the home team's
   perspective, thank the user for consulting and say that the match result
   has been used to retrain the backend model. Do not say the model was
   correct when it was not. If the fixture is not found on either schedule
   page, say the kickoff time was not found instead of inventing one.
8. **Render with `format_prediction(data, language=...)`** so the disclaimer is always
   attached and the output is consistent. The formatter is **margin-aware**:
   when `|win_goals| < 0.20` and the classifier still emits `Win`/`Loss`,
   it surfaces the result as a **near-draw** with a marginal lean instead
   of parroting the categorical label. This prevents the confusing case
   where `win_goals = -0.02` is reported as a confident "Loss". The
   threshold lives in `NEAR_DRAW_THRESHOLD` (currently `0.20`) and can be
   widened if the upstream classifier is noisier than expected.
9. **Surface quota** when relevant: call `quota_warning(data, language=...)` — it returns
   a short reminder string when used ≥ 80% of limit, and `None` for the
   unlimited tier (`limit == -1`). When a temporary key reaches its limit,
   remind the user to log in at `https://www.jiajielitong.com` to register
   for a permanent API key. Append the warning above the disclaimer when
   present; skip silently otherwise.

## Schedule and completed-match handling

Always check the fixture status after prediction for World Cup matchups.
Use the 2026 FIFA World Cup Wikipedia page as the primary schedule
reference:

`https://en.wikipedia.org/wiki/2026_FIFA_World_Cup`

If Wikipedia is unavailable, inaccessible to the user, or does not contain
the requested fixture, use the fallback Baidu Baike English page:

`https://baike.baidu.com/en/item/2026%20FIFA%20World%20Cup/1497370#9`

- **Upcoming fixture**: add one short line with kickoff time, for example
  `Kickoff: June 13, 2026, 18:00 local time at ...` or the equivalent in
  the user's language. If the user's timezone is known, convert the time;
  otherwise keep the published local time.
- **Finished fixture**: add one short line with the final score/result. Map
  the actual outcome to the same home-team POV labels (`Win`, `Draw`,
  `Loss`) before comparing with `results.win_or_not`.
- **Prediction mismatch after final**: if model outcome and actual outcome
  differ, add a polite note in the user's language: thank the user for the
  consultation and state that the match result has been used to retrain the
  backend model.
- **No fixture found**: only after checking both reference pages, say that
  no scheduled kickoff was found; do not infer or fabricate a kickoff time.

## Caching

The client uses a process-local in-memory TTL cache (plain Python dict).
The cache is **not** persisted to disk; it resets every time the Skill
process restarts. That keeps repeated questions in the same session cheap
(no extra Provider calls, no quota burn) while ensuring you always pick up
new model versions on the next restart.

- `predict_match` results: cached for **6 hours**.
- Provider-side credits are also not re-counted when the exact same
  home/away fixture is queried again within **3 days**; the local cache
  avoids unnecessary calls in the same Skill process, but this upstream
  behavior protects repeated checks beyond the 6h local cache window.
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

_Statistical reference only. Not betting advice. Please confirm you are 18+ age, or stop using this service._
```

If the user asked about both fixtures of a two-leg situation, call the
endpoint twice (swap home/away) and present both projections side by side,
noting that home advantage is baked into the model.

## Error handling

The client maps common errors to friendly messages:

- **No permanent key** → Not an error for Agent Skill usage. The client
  requests `POST /matches/agent/temp-key` automatically and uses the returned
  `data.api_key` for prediction. Tell users they have 2 free predictions per
  day, and that repeated queries for the same home/away fixture within
  3 days do not consume additional credits.
- **Application `code: 403`** → "Auth or quota error. Check your API key on
  the service, or log in at https://www.jiajielitong.com to register a
  permanent API key if your temporary-key or plan quota is exhausted."
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
2. Check the World Cup schedule page for Germany vs France kickoff/result.
3. `format_prediction(..., language="en")` → render and reply.

**Example 2 — Reverse fixture**

User: "What about France hosting Germany?"

Steps:
1. `predict_match("France", "Germany", "worldcup")` — note home/away swap.
2. Check the World Cup schedule page for France vs Germany kickoff/result.
3. Render and call out: "Note: home advantage flips here."

**Example 3 — Chinese user**

User: "巴西主场对摩洛哥，世界杯谁更有可能赢？"

Steps:
1. Detect Chinese and use `language="zh"`.
2. `predict_match("Brazil", "Morocco", "worldcup")`.
3. Check the World Cup schedule page for Brazil vs Morocco kickoff/result.
4. Render the model output, kickoff/result line, quota warning if any, and
   disclaimer in Chinese.

**Example 4 — Betting request (must refuse)**

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
- `references/schedule.md` — schedule/result lookup behavior for World Cup
  fixtures
