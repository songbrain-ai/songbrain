"""Coding-agent hint for the User-Agent header (0.3.3).

When the SDK runs inside a coding agent's shell, the User-Agent gets a short
suffix such as ``songbrain-python/0.3.3 (agent: claude-code)``. Only the
agent's name is sent, read from environment variables those tools set
themselves; no other environment data leaves the process. Set
``SONGBRAIN_NO_AGENT_HINT=1`` to turn it off.
"""
import os
import re
from typing import Mapping, Optional

# Env var set by the tool → name we send. AI_AGENT is the cross-tool
# convention ("claude-code_2-1-0_agent"); the others are per-tool flags.
_FLAGS = (
    ("CLAUDECODE", "claude-code"),
    ("CURSOR_AGENT", "cursor"),
    ("GEMINI_CLI", "gemini-cli"),
    ("CODEX_SANDBOX", "codex"),
    ("OPENCODE", "opencode"),
    ("AUGMENT_AGENT", "augment"),
)
_UNSAFE = re.compile(r"[^a-z0-9.-]")


def agent_hint(environ: Optional[Mapping[str, str]] = None) -> Optional[str]:
    env = os.environ if environ is None else environ
    if env.get("SONGBRAIN_NO_AGENT_HINT"):
        return None
    raw = env.get("AI_AGENT") or ""
    if raw:
        name = _UNSAFE.sub("", raw.split("_", 1)[0].lower())[:40]
        if name:
            return name
    for var, name in _FLAGS:
        if env.get(var):
            return name
    return None


def user_agent(version: str, environ: Optional[Mapping[str, str]] = None) -> str:
    hint = agent_hint(environ)
    base = f"songbrain-python/{version}"
    return f"{base} (agent: {hint})" if hint else base
