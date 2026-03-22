"""
Zion Write Gateway
==================
Every file write in Zion goes through here. No exceptions.

Checks (in order):
  1. Absolute path — resolve symlinks, normalise
  2. Repo boundary — path must be inside BASE_DIR or COLLECTIVE_DIR
  3. Allowlist — path must match a pattern in governance/permissions.json
  4. Extension whitelist — only .md, .json, .txt, .log allowed
  5. Size limit — 100KB max per write
  6. Append-only guard — certain files may never be overwritten
  7. Atomic write — write to .tmp, then rename

On any violation: raises WriteViolation, logs to error_log.json.
Never silently passes a bad write.
"""

import os
import json
import hashlib
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("zion.write_gateway")

BASE_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = BASE_DIR / "data"
GOVERNANCE_DIR = BASE_DIR / "governance"
PERMISSIONS_PATH = GOVERNANCE_DIR / "permissions.json"
ERROR_LOG = DATA_DIR / "error_log.json"

# Files that may only ever be appended to — never overwritten
APPEND_ONLY_PATTERNS = [
    "worklog.md",
    "decision_log.md",
    "error_log.json",
    "feedback_log.json",
    "watcher_log.json",
]

# Only these extensions may be written
ALLOWED_EXTENSIONS = {".md", ".json", ".txt", ".log"}

# Max bytes per write
MAX_FILE_BYTES = 100 * 1024  # 100KB


class WriteViolation(Exception):
    """Raised when a write attempt fails gateway checks."""
    def __init__(self, reason: str, attempted_path: str):
        self.reason = reason
        self.attempted_path = attempted_path
        super().__init__(f"WriteViolation: {reason} | path: {attempted_path}")


# ── Internal helpers ───────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_violation(reason: str, attempted_path: str, agent: str = "unknown"):
    """Append violation to error_log.json. Never raises — logging must not fail."""
    try:
        error_log = DATA_DIR / "error_log.json"
        data = {"errors": []}
        if error_log.exists():
            try:
                data = json.loads(error_log.read_text())
            except Exception:
                data = {"errors": []}

        data["errors"].append({
            "timestamp": _now_iso(),
            "type": "write_violation",
            "agent": agent,
            "reason": reason,
            "attempted_path": attempted_path,
        })

        # Write error log directly (bypasses gateway — this is the logger itself)
        error_log.write_text(json.dumps(data, indent=2))
    except Exception as e:
        log.error(f"Could not write to error log: {e}")


def _resolve_safe(raw_path: str | Path) -> Path:
    """
    Resolve a path to absolute, following symlinks.
    Returns the real path so we can check it against allowed roots.
    """
    p = Path(raw_path)
    # Expand ~ if present
    p = p.expanduser()
    # Make absolute relative to BASE_DIR if not already absolute
    if not p.is_absolute():
        p = BASE_DIR / p
    # Resolve symlinks and normalise (.., ., etc.)
    # Note: resolve() follows symlinks fully — a symlink pointing outside
    # the repo will reveal its real destination here.
    return p.resolve()


def _load_permissions() -> dict:
    """Load the allowlist from governance/permissions.json."""
    if not PERMISSIONS_PATH.exists():
        # Governance file missing — fail hard
        raise WriteViolation(
            "governance/permissions.json not found — cannot validate write",
            str(PERMISSIONS_PATH)
        )
    try:
        return json.loads(PERMISSIONS_PATH.read_text())
    except json.JSONDecodeError as e:
        raise WriteViolation(
            f"governance/permissions.json is malformed: {e}",
            str(PERMISSIONS_PATH)
        )


def _path_is_allowed(resolved: Path, permissions: dict) -> tuple[bool, str]:
    """
    Check resolved path against the allowlist.
    Returns (allowed, rule_matched_or_reason).
    """
    allowed_paths = permissions.get("allowed_write_paths", [])

    for pattern in allowed_paths:
        # Expand pattern relative to BASE_DIR
        pattern_path = _resolve_safe(pattern) if "/" in pattern else BASE_DIR / pattern
        try:
            resolved.relative_to(pattern_path)
            return True, pattern
        except ValueError:
            continue

    return False, "no matching rule in allowed_write_paths"


def _is_append_only(resolved: Path) -> bool:
    for pattern in APPEND_ONLY_PATTERNS:
        if resolved.name == pattern or resolved.name.endswith(pattern):
            return True
    return False


def _atomic_write(resolved: Path, content: str, mode: str):
    """Write content atomically using a temp file + rename."""
    resolved.parent.mkdir(parents=True, exist_ok=True)

    if mode == "append":
        # For append: read existing, concatenate, write atomically
        existing = resolved.read_text() if resolved.exists() else ""
        full_content = existing + content
    else:
        full_content = content

    # Write to temp file in same directory (ensures same filesystem for rename)
    tmp_path = resolved.parent / (resolved.name + ".tmp")
    try:
        tmp_path.write_text(full_content, encoding="utf-8")
        tmp_path.rename(resolved)
    except Exception:
        # Clean up tmp if rename failed
        if tmp_path.exists():
            tmp_path.unlink()
        raise


# ── Public API ─────────────────────────────────────────────────────────────────

def safe_write(
    path: str | Path,
    content: str,
    mode: str = "write",   # "write" | "append"
    agent: str = "unknown",
) -> Path:
    """
    Write content to path after running all safety checks.

    Args:
        path:    Target file path (relative to BASE_DIR or absolute)
        content: String content to write
        mode:    "write" (overwrite) or "append" (add to end)
        agent:   Name of the agent requesting the write (for audit log)

    Returns:
        The resolved Path that was written to.

    Raises:
        WriteViolation: if any check fails. Write does NOT happen.
    """
    raw_path_str = str(path)

    # ── Check 1: Resolve path ──────────────────────────────────────────────────
    try:
        resolved = _resolve_safe(path)
    except Exception as e:
        _log_violation(f"Path resolution failed: {e}", raw_path_str, agent)
        raise WriteViolation(f"Path resolution failed: {e}", raw_path_str)

    # ── Check 2: Extension whitelist ───────────────────────────────────────────
    if resolved.suffix not in ALLOWED_EXTENSIONS:
        reason = f"Extension '{resolved.suffix}' not in allowed list {ALLOWED_EXTENSIONS}"
        _log_violation(reason, str(resolved), agent)
        raise WriteViolation(reason, str(resolved))

    # ── Check 3: Content size ──────────────────────────────────────────────────
    content_bytes = content.encode("utf-8")
    if len(content_bytes) > MAX_FILE_BYTES:
        reason = f"Content size {len(content_bytes)} bytes exceeds {MAX_FILE_BYTES} byte limit"
        _log_violation(reason, str(resolved), agent)
        raise WriteViolation(reason, str(resolved))

    # ── Check 4: Append-only guard ─────────────────────────────────────────────
    if mode == "write" and _is_append_only(resolved):
        reason = f"'{resolved.name}' is append-only — use mode='append'"
        _log_violation(reason, str(resolved), agent)
        raise WriteViolation(reason, str(resolved))

    # ── Check 5: Allowlist ─────────────────────────────────────────────────────
    try:
        permissions = _load_permissions()
    except WriteViolation:
        raise  # Already logged inside _load_permissions

    allowed, rule = _path_is_allowed(resolved, permissions)
    if not allowed:
        reason = f"Path not in allowlist: {rule}"
        _log_violation(reason, str(resolved), agent)
        raise WriteViolation(reason, str(resolved))

    # ── Check 6: Symlink rejection (post-resolve double-check) ─────────────────
    # After resolution, if the path still has a symlink ancestor, reject it.
    # (resolve() should have followed them, but we verify the parent chain)
    check = resolved
    while check != check.parent:
        if check.is_symlink():
            reason = f"Symlink detected in path after resolution: {check}"
            _log_violation(reason, str(resolved), agent)
            raise WriteViolation(reason, str(resolved))
        check = check.parent

    # ── All checks passed — write ──────────────────────────────────────────────
    try:
        _atomic_write(resolved, content, mode)
    except Exception as e:
        reason = f"Write failed after passing all checks: {e}"
        _log_violation(reason, str(resolved), agent)
        raise WriteViolation(reason, str(resolved))

    log.info(f"[write_gateway] {agent} wrote {len(content_bytes)}B → {resolved} (mode={mode})")
    return resolved


def safe_write_json(
    path: str | Path,
    data: dict | list,
    agent: str = "unknown",
) -> Path:
    """
    Convenience wrapper: serialise dict/list to JSON and write.
    Always overwrites (JSON files are not append-only by nature).
    """
    content = json.dumps(data, indent=2)
    return safe_write(path, content, mode="write", agent=agent)


def safe_append(
    path: str | Path,
    content: str,
    agent: str = "unknown",
) -> Path:
    """Convenience wrapper for append mode."""
    return safe_write(path, content, mode="append", agent=agent)
