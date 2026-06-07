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

## Requirements

Set `SOCCER_API_KEY` before prediction calls. Users can apply for an API key
at `https://www.jiajielitong.com`.

## Safety

This skill is for statistical analysis only. It does not provide betting
advice, stakes, bookmaker odds, or wagering strategy.
