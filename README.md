OpenClaw skill to find hot trends and create prediction markets on Betbud and on chain.

# Betbud Prediction Skill for OpenClaw

This skill scans X/Twitter for hot debatable topics in a category (crypto, politics, etc.), uses Claude to turn the top one into a yes/no prediction market proposal (question, duration, resolution, score, reasoning, sources).

## How to add this skill in OpenClaw

1. In OpenClaw agent → add skill from ClawHub or local repo
2. Point to this repo: https://github.com/SamJ12/Betbud-Prediction-skill
3. Input example: {"category": "Crypto"}

## Requirements

- User must have their own API keys in .env or agent config:
  - TWITTERAPI_IO_KEY
  - ANTHROPIC_API_KEY
  - RPC_URL (Base Sepolia)
  - PRIVATE_KEY (user's wallet for on-chain tx)

Run locally for testing: `python3 skill.py`

For full flow: Twitter trends → Claude proposal → on-chain market creation → registration in betbud.live "Events" table.
