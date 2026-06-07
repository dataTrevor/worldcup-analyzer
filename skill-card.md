# World Cup Analyzer

Predict international national-team match outcomes with a machine learning
model and present the result as statistical reference only.

## What it does

- Predicts Win / Draw / Loss from the home team's point of view.
- Shows expected goal difference.
- Answers in the user's language, including Chinese and English.
- Adds 2026 FIFA World Cup kickoff or final-result context when available.
- Uses Wikipedia as the primary schedule source and Baidu Baike as fallback.
- Warns when API usage reaches plan limits.
- Supports automatic Agent temporary keys: 2 free predictions per day.
- Repeated queries for the same home/away fixture within 3 days do not
  consume additional credits.

## Requirements

`SOCCER_API_KEY` is optional for Agent Skill users. If it is not set, the
client requests a 24-hour Agent temporary key automatically. When the
temporary-key limit is reached, users can register a permanent API key at
`https://www.jiajielitong.com`.

## Safety

This skill is for statistical analysis only. It does not provide betting
advice, stakes, bookmaker odds, or wagering strategy.
