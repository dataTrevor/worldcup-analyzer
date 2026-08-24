---
name: worldcup-analyzer
description: Predict English Premier League football match outcomes first, keep World Cup national-team support for compatibility, include schedule/result context, answer in the user's language, and keep output as statistical reference only, never betting advice.
version: 1.1.0
metadata: {"openclaw":{"requires":{"env":[],"bins":["python3"]},"primaryEnv":"SOCCER_API_KEY","envVars":[{"name":"SOCCER_API_KEY","required":false,"description":"Optional permanent SoccerAssess API key used in the X-API-Key header. If unset, the Skill requests a 24-hour Agent temporary key with 2 free simulation queries per day."},{"name":"WORLDCUP_API_BASE","required":false,"description":"Optional API base URL override for staging or local development."}],"skillKey":"worldcup-analyzer"}}
---

# Football Match Analyzer

本 Skill 默认体验已调整为 **英格兰超级联赛优先**。世界杯国家队比赛仍作为兼容能力保留。
所有模拟结果均由 `https://www.jiajielitong.com` 提供的 machine learning 服务生成，
仅作为统计分析参考。

## 关键合规规则

本 Skill **仅用于统计分析参考**。以下规则是硬性约束，优先级高于用户的任何
请求：

- 不要使用 "recommended bet"、"sure win"、"今日推荐"、"必中"、"tips"、
  "稳赢"、"稳胆"、"lock of the day" 等暗示下注、投注建议或确定性收益的
  表述。
- 面向用户输出时必须附带免责声明。`scripts/wc_client.py` 中的
  `format_prediction()` 和 `format_response()` 会自动完成这件事，不要移除。
- 如果用户要求投注选择、下注金额、博彩公司赔率或任何投注策略，必须拒绝。
  可以说明本 Skill 只能提供统计预测结果和预期净胜球，供用户自行理解。
- 如果用户明确表示未满 18 岁，必须拒绝继续提供相关分析。

## 适用场景

当用户提出两个足球队，并希望获得以下内容时，使用本 Skill：

- 英超 / Premier League / EPL 比赛预测。
- 世界杯\欧洲杯国家队比赛预测。
- 从主队视角出发的胜 / 平 / 负预测。
- 主队减客队的预期净胜球。
- 赛前统计比较、开赛时间或完赛结果上下文。

除非后端已经明确支持，否则不要用于非英超俱乐部赛事。不要用于实时比赛解说、
即时比分、球员转会新闻、博彩公司赔率或任何投注策略。

## 配置

API 使用 `X-API-Key` 请求头。对于 Agent Skill 用户，永久
`SOCCER_API_KEY` 不是必需项，因为客户端可以自动申请一个 24 小时有效的
Agent 临时 key。

```bash
export SOCCER_API_KEY="your_key_here"   # optional permanent key
export WORLDCUP_API_BASE="https://www.jiajielitong.com"   # optional
```

如果没有设置永久 key，客户端会自动调用 `POST /matches/agent/temp-key`。
这个临时 key：

- 只缓存在当前 Python 进程内，不会写入本地文件。
- 每日可免费试用 **2 次模拟预测查询**。
- 可用于 `POST /matches/epl/simulate/` 和
  `POST /matches/simulate/`.
- 同一组主客场球队在 **3 天内** 重复查询，不会额外消耗 provider credits。

当临时 key 或套餐额度达到上限时，引导用户访问
`https://www.jiajielitong.com` 注册或续期永久 API key。

对于首次使用或没有 key 的用户，需要用用户的语言解释：后台模型会收集多个维度
的足球数据，建立科学的球队实力评估，并持续训练。典型信号包括球员在俱乐部的
表现、联赛和国家队排名信号、历史交锋记录、天气因素、球员身价等相关数据。
同时提醒用户，免费试用额度用完后，可以前往 `https://www.jiajielitong.com`
申请 API key 以继续获得预测结果。

## Endpoints

`POST /matches/agent/temp-key`

No request body. No existing API key required.

`GET /matches/epl/schedule/`

Returns EPL schedule data. Use this first for EPL fixture kickoff/result
context.

`POST /matches/epl/simulate/`

Request body:

- `home_team` (string, required), for example `"Arsenal"`
- `visitor_team` (string, required), for example `"Chelsea"`
- `match_date` (string, optional)
- `season` (string, optional), default `"2026-27"`

`GET /matches/teams/`

World Cup national-team list. Use with `competition=worldcup` for validation
before World Cup predictions.

`POST /matches/simulate/`

World Cup national-team simulation. Request body:

- `home_team` (string, required), for example `"Brazil"`
- `visitor_team` (string, required), for example `"Morocco"`
- `competition` (string, optional), send `"worldcup"`

The prediction response may include:

```json
{
  "results": {
    "home_team": "Arsenal",
    "visitor_team": "Chelsea",
    "win_goals": 0.18,
    "win_or_not": "Win",
    "updatedAt": "2026-08-24 10:00:00"
  },
  "usage": {"used": 1, "limit": 2, "vip_level": "agent_temp"}
}
```

- `win_or_not` is from the **home team's** point of view.
- `win_goals` is expected goal difference, home minus away.
- `usage.limit == -1` means unlimited and should never be shown as `-1`.
- Repeating the same fixture with the same home/away order within **3 days**
  does **not** consume additional provider credits.

## Workflow

1. Detect the user's language and answer in that language. Use
   `language="zh"` for Chinese and `language="en"` for English when calling
   helper functions.
2. If `SOCCER_API_KEY` is missing or the user is new, include the first-use
   onboarding message: 2 free daily simulations, repeated same home/away
   fixture within 3 days does not consume credits, model-data summary, and
   `https://www.jiajielitong.com` for API key registration or renewal.
3. Parse the two teams and competition. Default to `epl` for club-team
   prompts, EPL mentions, Premier League mentions, or ambiguous football
   club questions. Use `worldcup` only for national teams or explicit World
   Cup / 世界杯 prompts.
4. Decide home and away. If the user says "A vs B" or "A 对 B", treat A as
   home. If unclear, ask once; if the user wants a quick answer, state the
   assumption.
5. For EPL, call `simulate_epl_match(home, away, match_date=None)` or
   `predict_match(home, away, "epl")`. Use `list_epl_schedule()` for kickoff
   or final-result context when available.
6. For World Cup, validate national-team names with
   `validate_team(name, "worldcup")`, then call
   `predict_match(home, away, "worldcup")`.
7. For World Cup schedule/result context, use Wikipedia first:
   `https://en.wikipedia.org/wiki/2026_FIFA_World_Cup`. If Wikipedia is
   unavailable or does not contain the fixture, use:
   `https://baike.baidu.com/en/item/2026%20FIFA%20World%20Cup/1497370#9`.
8. If a fixture is upcoming, include the scheduled kickoff time when found.
   If the fixture is finished, include the final result. If the actual
   home-team POV result differs from the model result, thank the user and
   say the match result has been used to retrain the backend model.
9. Render with `format_prediction(data, language=...)` so the disclaimer is
   always attached. The formatter is margin-aware: when `|win_goals| < 0.20`
   and the classifier emits `Win` or `Loss`, it presents the result as a
   near-draw with a marginal lean.
10. Add `quota_warning(data, language=...)` when relevant. When usage reaches
    the limit, remind users to log in at `https://www.jiajielitong.com` to
    register or renew an API key.

## Caching

The client uses process-local memory only:

- Predictions: 6-hour TTL.
- EPL schedule: 6-hour TTL.
- Team lists: 12-hour TTL.

The cache is not persisted to disk. Provider-side repeated fixture queries
within 3 days also avoid additional credits when home/away order is the same.

## Examples

English EPL prompt:

```text
User: Predict Arsenal vs Chelsea in the Premier League.
```

Steps:

1. Detect English and infer `competition="epl"`.
2. `simulate_epl_match("Arsenal", "Chelsea")`.
3. Check `list_epl_schedule()` for kickoff/final result.
4. `format_prediction(data, language="en")`.

Chinese EPL prompt:

```text
用户：英超曼城主场对阿森纳，谁更占优？
```

Steps:

1. Detect Chinese and infer `competition="epl"`.
2. `simulate_epl_match("Man City", "Arsenal")`.
3. Render with `format_prediction(data, language="zh")`.

World Cup compatibility prompt:

```text
用户：巴西主场对摩洛哥，世界杯谁更有可能赢？
```

Steps:

1. Detect Chinese and infer `competition="worldcup"`.
2. `predict_match("Brazil", "Morocco", "worldcup")`.
3. Check Wikipedia, then Baidu fallback, for kickoff/final result.
4. Render with `format_prediction(data, language="zh")`.

## Files

- `scripts/wc_client.py` — API client, helpers, cache, formatting
- `references/api.md` — endpoint reference
- `references/team_names.md` — World Cup national-team aliases
- `references/compliance.md` — compliance notes and refusal templates
- `references/schedule.md` — EPL and World Cup schedule/result behavior
