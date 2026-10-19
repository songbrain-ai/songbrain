/**
 * Coding-agent hint for the User-Agent header (0.3.3).
 *
 * When the SDK runs inside a coding agent's shell, the User-Agent gets a short
 * suffix such as `songbrain-js/0.3.3 (agent: claude-code)`. Only the agent's
 * name is sent, read from environment variables those tools set themselves;
 * no other environment data leaves the process. Browsers have no env, so they
 * never send a hint. Set `SONGBRAIN_NO_AGENT_HINT=1` to turn it off.
 */
import { VERSION } from "./version.js";

// Env var set by the tool → name we send. AI_AGENT is the cross-tool
// convention ("claude-code_2-1-0_agent"); the others are per-tool flags.
const FLAGS: ReadonlyArray<readonly [string, string]> = [
  ["CLAUDECODE", "claude-code"],
  ["CURSOR_AGENT", "cursor"],
  ["GEMINI_CLI", "gemini-cli"],
  ["CODEX_SANDBOX", "codex"],
  ["OPENCODE", "opencode"],
  ["AUGMENT_AGENT", "augment"],
];

type Env = Record<string, string | undefined>;

function processEnv(): Env {
  const p = (globalThis as { process?: { env?: Env } }).process;
  return p?.env ?? {};
}

export function agentHint(env: Env = processEnv()): string | undefined {
  if (env.SONGBRAIN_NO_AGENT_HINT) return undefined;
  const raw = env.AI_AGENT ?? "";
  if (raw) {
    const name = (raw.split("_", 1)[0] ?? "").toLowerCase().replace(/[^a-z0-9.-]/g, "").slice(0, 40);
    if (name) return name;
  }
  for (const [key, name] of FLAGS) if (env[key]) return name;
  return undefined;
}

export function userAgent(env?: Env): string {
  const hint = agentHint(env);
  const base = `songbrain-js/${VERSION}`;
  return hint ? `${base} (agent: ${hint})` : base;
}
