// Task -> model router for OpenCode (best-available *free* tier per task class).
// Kept as a plain decision table; no framework. Run: node scripts/model-router.js "task description"
"use strict";

const ROUTE = {
  // ---------- quick housekeeping (no money, no correctness-diamond) ----------
  quick: {
    default: "huggingface/smolVLM", // free; good for grep/sed/format/echo-type work
    keywords: ["grep", "sed", "format", "lint", "echo", "copy", "rename", "move", "diff", "find", "quick", "one-liner", "sql", "tests", "smoke"],
  },

  // ---------- routine feature work (one file, well-specified) ----------
  default: {
    default: "huggingface/smollm2-1.7b", // free permissive LLM, suitable for routine edits
    keywords: ["edit", "add", "refactor", "fix", "test", "readme", "config", "routes", "api", "feature", "ticket", "issue"],
  },

  // ---------- correctness-sensitive / decision-heavy work ----------
  deep: {
    default: "openai/gpt-4o-mini", // free/capped tier; strong enough for code review & design
    keywords: ["review", "design", "arch", "security", "audit", "postgres", "alembic", "db schema", "authentication", "authorization", "pr", "plan", "spec"],
  },

  // ---------- orchestration, agent coordination, release gates ----------
  orchestrate: {
    default: "google/gemini-2.5-flash", // free tier; best at multi-step coordination & triage
    keywords: ["orchestrat", "coordinate", "delegate", "reviewer", "release", "checkpoint", "tag", "publish", "integrate", "system"],
  },
};

// Fall back through the categories in order; a task matching several types takes
// the *deepest* matching category. Simpler heuristic to keep it deterministic:
// sort categories by keyword count and pick the category with the most hits.
function pickModel(task, { exact = false } = {}) {
  const t = (task || "").toLowerCase().trim();
  if (!t) return { tier: "default", model: ROUTE.default.default };

  let best = null;
  let bestHits = -1;
  for (const [tier, cfg] of Object.entries(ROUTE)) {
    const hits = cfg.keywords.filter((k) => t.includes(k)).length;
    if (hits > bestHits) {
      bestHits = hits;
      best = { tier, model: cfg.default };
    }
  }
  if (bestHits <= 0) return { tier: "default", model: ROUTE.default.default };
  return best;
}

// CLI wrapper
if (require.main === module) {
  const [, , ...args] = process.argv;
  const task = args.join(" ");
  process.stdout.write(JSON.stringify(pickModel(task), null, 2));
}

module.exports = { pickModel, ROUTE };
