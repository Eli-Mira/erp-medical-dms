# Scoped OpenCode coding proof — BLOCKED, not accepted

Runtime: Debian native `/home/elilain/.opencode/bin/opencode`, v2.1.0.
Synthetic fixture only: `C:/Users/emadg/AppData/Local/hermes/cache/scratch/medical-erp-poc-20261021-0147/`.

## Attempt and bounded diagnosis

- A per-project `.opencode/agents/lain-poc.md` was prepared using the upstream Markdown-agent documentation. It denies all tools by default and permits only reads of two synthetic fixture files and edits to `decimal_guard.py`.
- `opencode debug agents` in that directory returned no `lain-poc` agent. The parent assertion failed; this is an integration preflight failure, not an ERP test failure.
- `opencode --standalone debug agents` returned CLI exit 1: `Unrecognized flag: --standalone in command opencode debug`.
- The supported `opencode api --standalone GET /api/agent` diagnostic returned API exit 0 but still no `lain-poc` agent. Agent discovery/permission semantics remain unresolved on this installed build.
- No unrestricted `build` worker was launched against ERP files. No model request was sent for this coding fixture; no source change or execution result is claimed from it. Its initial test fixture is not a delivered feature.

Earlier independent connectivity proof remains valid, but is not substituted for coding containment:

| Requested model | Retained session | Verified response |
|---|---|---|
| `opencode/deepseek-v4.1-flash-free` | `ses_ea493ba67ffexauc5Q2W88z5I2` | `SMOKE_DEEPSEEK_OK` |
| `opencode/glm-5.3-flash-free` | `ses_ea493bb22ffepH4CRvIR8CPRyw` | `SMOKE_GLM_OK` |
| `opencode/minimax-m3.1-flash-free` | `ses_ea493b5faffe5btA3RwnN8zcEC` | `SMOKE_MINIMAX_OK` |

The parent previously read back all three exact session IDs, models, succeeded outcomes and zero tool calls. Those text tests prove neither code execution, isolated file permissions, independent review, upstream model identity nor sustained availability/free quota.

## Disposition

Fail closed on the scoped coding gate. Continue authorized ERP implementation using Hermes directly, as Execution Directive V2 §2 permits. Do not install another orchestration framework, copy credentials, widen permissions or call this fully automated coding. Future repair must verify installed-version configuration discovery and exact runtime permissions before another coding request. No production configuration was changed.
