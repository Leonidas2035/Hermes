#!/usr/bin/env python3
"""
Antigravity Bridge — Read Antigravity state/config and invoke agy CLI from Hermes Agent.

This module exposes Hermes tools for querying Antigravity's `.gemini` state
(read-only) and invoking `agy --print` tasks.

Paths (Antigravity):
  App data:      ~/.gemini/
  CLI data:      ~/.gemini/antigravity-cli/
  Core app:      ~/.gemini/antigravity/

Key state files consumed:
  ~/.gemini/state.json, ~/.gemini/settings.json, ~/.gemini/projects.json,
  ~/.gemini/google_accounts.json, ~/.gemini/trustedFolders.json,
  ~/.gemini/installation_id
  ~/.gemini/antigravity/antigravity_state.pbtxt
  ~/.gemini/antigravity-cli/antigravity-oauth-token
  ~/.gemini/antigravity-cli/history.jsonl
  ~/.gemini/config/mcp_config.json
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
GEMINI_DIR = Path.home() / ".gemini"
ANTIGRAVITY_DIR = GEMINI_DIR / "antigravity"
CLI_DIR = GEMINI_DIR / "antigravity-cli"
CONFIG_DIR = GEMINI_DIR / "config"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Public state readers (read-only)
# ---------------------------------------------------------------------------
def get_projects() -> Dict[str, str]:
    """Return Antigravity project map: {workspace_path: project_type}."""
    return _read_json(GEMINI_DIR / "projects.json").get("projects", {})


def get_google_accounts() -> Dict[str, Any]:
    """Return active/old Google accounts used by Antigravity."""
    return _read_json(GEMINI_DIR / "google_accounts.json")


def get_security_settings() -> Dict[str, Any]:
    """Return security/auth settings (selected auth type, etc.)."""
    return _read_json(GEMINI_DIR / "settings.json")


def get_trusted_folders() -> Dict[str, str]:
    """Return trusted workspace folder policies."""
    return _read_json(GEMINI_DIR / "trustedFolders.json")


def get_installation_ids() -> Dict[str, str]:
    """Return installation UUIDs for .gemini root, antigravity app, and antigravity-cli."""
    ids: Dict[str, Optional[str]] = {
        "dot_gemini": _read_text(GEMINI_DIR / "installation_id").strip() or None,
        "antigravity": _read_text(ANTIGRAVITY_DIR / "installation_id").strip() or None,
        "antigravity_cli": _read_text(CLI_DIR / "installation_id").strip() or None,
    }
    return {k: v for k, v in ids.items() if v}


def get_cli_oauth_token() -> Dict[str, Any]:
    """Return Antigravity CLI OAuth token (read-only, for auth introspection)."""
    raw = _read_text(CLI_DIR / "antigravity-oauth-token")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def get_antigravity_state() -> Dict[str, Any]:
    """Parse Antigravity protobuf-text state into a JSON-friendly dict."""
    state: Dict[str, Any] = {}
    pbtxt = _read_text(ANTIGRAVITY_DIR / "antigravity_state.pbtxt")
    for line in pbtxt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"')
            if key not in state:
                state[key] = value
            else:
                # collect repeated keys (e.g. completed_steps)
                existing = state[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    state[key] = [existing, value]
    return state


def get_mcp_config() -> Dict[str, Any]:
    """Return MCP configuration (may be symlinked from antigravity dir)."""
    return _read_json(CONFIG_DIR / "mcp_config.json")


def get_recent_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent CLI history entries (up to `limit`)."""
    hist_path = CLI_DIR / "history.jsonl"
    if not hist_path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    try:
        with hist_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return entries[-limit:]


def get_bridge_summary() -> Dict[str, Any]:
    """Aggregate the most useful Antigravity state for Hermes consumption."""
    return {
        "projects": get_projects(),
        "google_accounts": get_google_accounts(),
        "security": get_security_settings(),
        "trusted_folders": get_trusted_folders(),
        "installation_ids": get_installation_ids(),
        "oauth_email": (get_cli_oauth_token().get("token", {}) or {}).get("email"),
        "oauth_token_type": (get_cli_oauth_token().get("token", {}) or {}).get("token_type"),
        "antigravity_state": get_antigravity_state(),
        "mcp_config": get_mcp_config(),
        "recent_history_count": len(get_recent_history(limit=1000)),
    }


# ---------------------------------------------------------------------------
# agy invocation helper — subprocess-based, no pty.fork()
# ---------------------------------------------------------------------------
def invoke_agy(prompt: str, workspace: Optional[str] = None, timeout: int = 300) -> Dict[str, Any]:
    """Invoke `agy --print` with a single prompt.

    Uses ``subprocess.run`` with a plain pipe. Requires ``agy`` on PATH.

    Args:
        prompt: The user prompt to send to Antigravity.
        workspace: Optional working directory (defaults to CWD).
        timeout: Seconds before killing the process.

    Returns:
        dict with keys: stdout, stderr, returncode, timed_out.
    """
    cmd = ["agy", "--print", prompt, "--dangerously-skip-permissions"]
    if workspace:
        cmd += ["--add-dir", str(workspace)]

    try:
        proc = subprocess.run(
            cmd,
            cwd=workspace or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "timeout",
            "returncode": -1,
            "timed_out": True,
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "timed_out": False,
        }


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------
from tools.registry import registry, tool_error  # noqa: E402

_AGY_TOOLSET = "antigravity"

_GET_SUMMARY_SCHEMA = {
    "name": "get_agy_summary",
    "description": (
        "Return Antigravity state summary: projects, google_accounts, "
        "security settings, trusted folders, installation IDs, auth metadata, "
        "and recent CLI history count. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

_INVOKE_AGY_SCHEMA = {
    "name": "invoke_agy",
    "description": (
        "Invoke Antigravity (agy) with a single prompt and return its output. "
        "Use this to run coding tasks through agy from Hermes. "
        "Provide a concise task description in `prompt`. "
        "Optionally set `workspace` to the target project directory."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Task prompt to send to Antigravity.",
            },
            "workspace": {
                "type": "string",
                "description": "Working directory for the task (defaults to current CWD).",
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds to wait (default 300).",
            },
        },
        "required": ["prompt"],
    },
}


def _check_agy_available() -> bool:
    return shutil.which("agy") is not None


def _handle_get_agy_summary(args: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    try:
        return {"ok": True, "data": get_bridge_summary()}
    except Exception as exc:
        return tool_error(str(exc))  # type: ignore[return-value]


def _handle_invoke_agy(args: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    prompt = args.get("prompt", "")
    if not prompt:
        return tool_error("Missing required field: prompt")  # type: ignore[return-value]
    result = invoke_agy(
        prompt=prompt,
        workspace=args.get("workspace"),
        timeout=int(args.get("timeout", 300)),
    )
    return {"ok": True, "data": result}


registry.register(
    name="get_agy_summary",
    toolset=_AGY_TOOLSET,
    schema=_GET_SUMMARY_SCHEMA,
    handler=_handle_get_agy_summary,
    check_fn=_check_agy_available,
    emoji="📋",
)

registry.register(
    name="invoke_agy",
    toolset=_AGY_TOOLSET,
    schema=_INVOKE_AGY_SCHEMA,
    handler=_handle_invoke_agy,
    check_fn=_check_agy_available,
    emoji="🤖",
)
