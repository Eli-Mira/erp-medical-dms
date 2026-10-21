# OpenCode model routing (best-free-tier)

Task type -> model tier is a decision table, not a guess. `scripts/model-router.js`
maps a task description to `{ tier, model }`, and Lain passes `--model <model>` to
`opencode run`.

## Tier -> role
| tier | role | example task |
|------|------|--------------|
| `quick` | housekeeping: grep, sed, format, smoke, small edits | "grep the invoice for overdue" |
| `default` | routine edits, features, single file | "add a pytest for the collection" |
| `deep` | correctness-sensitive: DB, security, review, design | "review the ar ledger migration" |
| `orchestrate` | multi-step: coordinate, release, delegate, publish | "run final E2E and open the pub-url" |

## Config
Rod models below are *IDs* — they only resolve if the used provider has an API key
set (e.g. OpenRouter `OPENROUTER_API_KEY`, or the direct provider). Patch the
`default` value under each tier to your confirmed free API. Start with the tier
markers, not the model text, when you upgrade.

- quick: `huggingface/smolVLM`
- default: `huggingface/smollm2-1.7b`
- deep: `openai/gpt-4o-mini`
- orchestrate: `google/gemini-2.5-flash`

## Usage
1. Lain decides the tier from the task + routes it through `node scripts/model-router.js "task"`.
2. Lain runs OpenCode with that tier: `opencode run --model <chose> "task"`.
3. No automatic routing loop: one `opencode run` per task, verify output, then move on.
