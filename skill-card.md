# Football Match Analyzer

Predict English Premier League match outcomes first, while keeping World Cup
national-team predictions available under the existing `worldcup-analyzer`
Skill identity.

## What It Does

- Predicts Win / Draw / Loss from the home team's point of view.
- Shows expected goal difference.
- Supports EPL / Premier League / 英超 matchups as the default mode.
- Keeps 2026 FIFA World Cup national-team compatibility.
- Adds kickoff or final-result context when available.
- Answers in the user's language, including Chinese and English.
- Warns when API usage reaches plan limits.
- Supports automatic Agent temporary keys: 2 free simulation queries per day.
- Repeated queries for the same home/away fixture within 3 days do not
  consume additional credits.

## 中文简介

这个 Skill 现在优先支持英格兰超级联赛比赛预测，同时保留世界杯国家队预测能力，
并沿用原来的 `worldcup-analyzer` 名称，方便已安装用户继续使用。它会从主队视角
给出 Win / Draw / Loss、预期净胜球，并在可用时补充开赛时间或完赛结果。

没有永久 API key 时，Skill 会自动申请 Agent 临时 key；每日可免费试用 2 次。
同一组主客场球队在 3 天内重复查询不会额外消耗 credits。额度用完后，可前往
`https://www.jiajielitong.com` 注册或续期 API key。

## Requirements

`SOCCER_API_KEY` is optional for Agent Skill users. If it is not set, the
client requests a 24-hour Agent temporary key automatically. When the
temporary-key limit is reached, users can register or renew a permanent API
key at `https://www.jiajielitong.com`.

## Safety

This skill is for statistical analysis only. It does not provide betting
advice, stakes, bookmaker odds, or wagering strategy.

## Changelog

### 1.1.1

Republished EPL-first version to refresh the ClawHub latest tag and update
the marketplace listing to the current EPL-first description.

### 1.1.0

English: Added EPL-first support through `/matches/epl/simulate/` and
`/matches/epl/schedule/`, while preserving World Cup support under the same
published Skill.

中文：新增英超优先支持，通过 `/matches/epl/simulate/` 预测比赛，并通过
`/matches/epl/schedule/` 获取赛程上下文；同时保留世界杯支持，继续使用同一个已发布
Skill。
