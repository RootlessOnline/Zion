"""
Zion Proposer — OS Mode
=======================
Zion observes what's been done, what's pending, and the active project,
then surfaces task proposals for Harley to approve or dismiss.

Proposals are NOT tasks. They sit in data/proposals.json as suggestions.
Nothing runs until Harley approves one — which moves it into the task queue.

Proposal lifecycle:
  pending   → shown in dashboard, waiting for Harley
  approved  → moved to task queue, removed from proposals
  dismissed → logged and removed, not shown again this session
  expired   → not actioned within 24h, quietly removed
"""

import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

log = logging.getLogger("zion.proposer")

BASE_DIR   = Path(__file__).parent.parent.resolve()
DATA_DIR   = BASE_DIR / "data"
PROMPTS_DIR = BASE_DIR / "prompts"
PROPOSALS_PATH = DATA_DIR / "proposals.json"

MAX_ACTIVE_PROPOSALS = 3      # never show more than 3 at once
PROPOSAL_EXPIRY_HOURS = 24    # proposals older than this are expired
MIN_HOURS_BETWEEN_RUNS = 1    # don't re-propose more often than this


# ── Proposal store ─────────────────────────────────────────────────────────────

def load_proposals() -> dict:
    if PROPOSALS_PATH.exists():
        try:
            return json.loads(PROPOSALS_PATH.read_text())
        except Exception:
            pass
    return {"proposals": [], "last_run": None, "dismissed": []}


def save_proposals(data: dict):
    PROPOSALS_PATH.write_text(json.dumps(data, indent=2))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def proposal_id(task_text: str, project: str) -> str:
    """Stable ID based on content — prevents duplicate proposals."""
    raw = f"{task_text.strip().lower()}::{project.strip().lower()}"
    return "prop_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


# ── Context gathering ──────────────────────────────────────────────────────────

def get_active_project(config: dict) -> dict | None:
    for p in config.get("projects", []):
        if p.get("active"):
            return p
    return None


def get_recent_completed(n: int = 5) -> list[dict]:
    """Return last N completed tasks."""
    queue_path = DATA_DIR / "task_queue.json"
    if not queue_path.exists():
        return []
    try:
        data = json.loads(queue_path.read_text())
        done = [t for t in data.get("queue", []) if t.get("status") == "completed"]
        return done[-n:]
    except Exception:
        return []


def get_pending_tasks() -> list[dict]:
    queue_path = DATA_DIR / "task_queue.json"
    if not queue_path.exists():
        return []
    try:
        data = json.loads(queue_path.read_text())
        return [t for t in data.get("queue", [])
                if t.get("status") in ("pending", "in_progress")]
    except Exception:
        return []


def get_dismissed_this_session(proposals_data: dict) -> list[str]:
    """Return list of task texts dismissed this session — avoid re-proposing."""
    return proposals_data.get("dismissed", [])


def read_project_readme(project: dict) -> str:
    """Try to read the project README for context."""
    repo_path = Path("~/RootlessOnline").expanduser()
    readme_path = repo_path / project.get("repo_path", "") / "README.md"
    if readme_path.exists():
        content = readme_path.read_text()
        return content[:2000]  # first 2000 chars is enough
    return ""


# ── LLM call ──────────────────────────────────────────────────────────────────

def call_ollama_proposer(system: str, user: str, config: dict) -> str:
    """Call ollama for proposal generation."""
    import requests
    try:
        response = requests.post(
            f"{config['ollama_host']}/api/chat",
            json={
                "model": config["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 600}
            },
            timeout=120
        )
        data = response.json()
        msg = data.get("message", {})
        # DeepSeek-r1 sometimes puts output in thinking instead of content
        return msg.get("content", "") or msg.get("thinking", "")
    except Exception as e:
        log.error(f"Proposer LLM call failed: {e}")
        return ""


def assemble_proposer_prompt() -> str:
    """Load Page -1 + proposer-specific instructions."""
    page_minus_one = PROMPTS_DIR / "page_minus_one.md"
    parts = []
    if page_minus_one.exists():
        parts.append(page_minus_one.read_text())

    parts.append("""
# Your Role — Proposer

You observe the active project and suggest what Zion should work on next.
You do NOT run tasks. You propose them for Harley to approve or dismiss.

## Rules for proposals
- Maximum 3 proposals at a time
- Each proposal must be one concrete, literal task — not a vague direction
- Each proposal must have a one-sentence reason (max 15 words)
- $0 budget — only propose free actions
- Do not re-propose recently completed tasks
- Do not propose tasks already in the queue
- Do not propose decisions — only execution tasks

## Output format (strict JSON, nothing else)
{
  "proposals": [
    {
      "task": "exact task description Zion should do",
      "reason": "one sentence, max 15 words, why this is the logical next step",
      "project": "project_id"
    }
  ]
}

Return between 1 and 3 proposals. Return an empty list if nothing useful can be proposed right now.
""")
    return "\n\n".join(parts)


# ── Core proposal generation ───────────────────────────────────────────────────

def generate_proposals(config: dict) -> list[dict]:
    """Ask the LLM what to work on next. Returns list of raw proposal dicts."""
    project = get_active_project(config)
    if not project:
        log.info("Proposer: no active project found")
        return []

    recent = get_recent_completed(5)
    pending = get_pending_tasks()
    readme  = read_project_readme(project)
    proposals_data = load_proposals()
    dismissed = get_dismissed_this_session(proposals_data)

    # Build context string
    context_lines = [
        f"Active project: {project['name']} (id: {project['id']}, phase: {project.get('phase', '?')})",
        "",
    ]

    if readme:
        context_lines += ["Project README (first 2000 chars):", readme, ""]

    if recent:
        context_lines.append("Recently completed tasks:")
        for t in recent:
            context_lines.append(f"  - [{t.get('project','')}] {t.get('task','')}")
        context_lines.append("")

    if pending:
        context_lines.append("Already in queue (do not re-propose):")
        for t in pending:
            context_lines.append(f"  - {t.get('task','')}")
        context_lines.append("")

    if dismissed:
        context_lines.append("Dismissed this session (do not re-propose):")
        for d in dismissed[-10:]:
            context_lines.append(f"  - {d}")
        context_lines.append("")

    context_lines.append(
        "Based on the above, what are the most useful next tasks for this project? "
        "Be specific and literal. Each task must be completable by an AI agent with no budget."
    )

    user_prompt = "\n".join(context_lines)
    system_prompt = assemble_proposer_prompt()

    raw = call_ollama_proposer(system_prompt, user_prompt, config)
    if not raw:
        log.warning("Proposer: LLM returned empty response")
        return []

    log.info(f"Proposer raw response (first 500 chars): {raw[:500]}")

    # Parse JSON — strip think blocks if present
    import re
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    # Find JSON object
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        log.warning(f"Proposer: could not parse JSON from response: {raw[:200]}")
        return []

    try:
        parsed = json.loads(match.group(0))
        return parsed.get("proposals", [])
    except json.JSONDecodeError as e:
        log.warning(f"Proposer: JSON parse error: {e} | raw: {raw[:200]}")
        return []


# ── Main run function ──────────────────────────────────────────────────────────

def run_proposer(config: dict, socketio=None) -> int:
    """
    Run one proposal cycle. Returns number of new proposals added.
    Called by the daemon on a timer — not every loop iteration.
    """
    proposals_data = load_proposals()

    # Expire old proposals
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=PROPOSAL_EXPIRY_HOURS)
    active = [
        p for p in proposals_data.get("proposals", [])
        if p.get("status") == "pending"
        and datetime.fromisoformat(p.get("created_at", now_iso())) > cutoff
    ]
    proposals_data["proposals"] = active

    # Don't run if already at max
    if len(active) >= MAX_ACTIVE_PROPOSALS:
        log.info(f"Proposer: already at max ({MAX_ACTIVE_PROPOSALS} pending). Skipping.")
        return 0

    # Don't run too often
    last_run = proposals_data.get("last_run")
    if last_run:
        try:
            elapsed = (now - datetime.fromisoformat(last_run)).total_seconds() / 3600
            if elapsed < MIN_HOURS_BETWEEN_RUNS:
                log.info(f"Proposer: ran {elapsed:.1f}h ago, too soon. Skipping.")
                return 0
        except Exception:
            pass

    log.info("Proposer: generating proposals...")
    proposals_data["last_run"] = now_iso()

    raw_proposals = generate_proposals(config)
    if not raw_proposals:
        save_proposals(proposals_data)
        return 0

    # Deduplicate against existing and dismissed
    existing_ids = {p["id"] for p in proposals_data.get("proposals", [])}
    dismissed    = set(proposals_data.get("dismissed", []))
    added = 0

    for raw in raw_proposals:
        task    = raw.get("task", "").strip()
        reason  = raw.get("reason", "").strip()
        project = raw.get("project", config.get("projects", [{}])[0].get("id", ""))

        if not task or not reason:
            continue
        if task.lower() in dismissed:
            continue

        pid = proposal_id(task, project)
        if pid in existing_ids:
            continue

        proposals_data["proposals"].append({
            "id":         pid,
            "task":       task,
            "reason":     reason,
            "project":    project,
            "status":     "pending",
            "created_at": now_iso(),
        })
        existing_ids.add(pid)
        added += 1

        if len(proposals_data["proposals"]) >= MAX_ACTIVE_PROPOSALS:
            break

    save_proposals(proposals_data)

    if added > 0:
        log.info(f"Proposer: added {added} new proposal(s)")
        if socketio:
            try:
                socketio.emit("proposals_updated", {"count": len(proposals_data["proposals"])})
            except Exception:
                pass

    return added


# ── Approval / Dismissal (called from API) ────────────────────────────────────

def approve_proposal(proposal_id: str, config: dict) -> dict | None:
    """
    Move a proposal into the task queue.
    Returns the new task dict if successful, None if not found.
    """
    proposals_data = load_proposals()
    proposal = next(
        (p for p in proposals_data["proposals"] if p["id"] == proposal_id), None
    )
    if not proposal:
        return None

    # Build task entry
    import uuid
    task = {
        "id":         "task_" + uuid.uuid4().hex[:8],
        "task":       proposal["task"],
        "project":    proposal["project"],
        "status":     "pending",
        "source":     "proposer",
        "proposal_id": proposal_id,
        "created_at": now_iso(),
        "retry_count": 0,
    }

    # Add to queue
    queue_path = DATA_DIR / "task_queue.json"
    queue_data = json.loads(queue_path.read_text()) if queue_path.exists() else {"queue": []}
    queue_data["queue"].append(task)
    queue_path.write_text(json.dumps(queue_data, indent=2))

    # Remove from proposals
    proposals_data["proposals"] = [
        p for p in proposals_data["proposals"] if p["id"] != proposal_id
    ]
    save_proposals(proposals_data)

    log.info(f"Proposal approved → task {task['id']}: {task['task'][:60]}")
    return task


def dismiss_proposal(proposal_id: str) -> bool:
    """
    Dismiss a proposal — log it as dismissed so it won't be re-proposed this session.
    Returns True if found and dismissed.
    """
    proposals_data = load_proposals()
    proposal = next(
        (p for p in proposals_data["proposals"] if p["id"] == proposal_id), None
    )
    if not proposal:
        return False

    proposals_data["proposals"] = [
        p for p in proposals_data["proposals"] if p["id"] != proposal_id
    ]
    proposals_data.setdefault("dismissed", []).append(proposal["task"].lower())
    # Cap dismissed list at 50
    proposals_data["dismissed"] = proposals_data["dismissed"][-50:]

    save_proposals(proposals_data)
    log.info(f"Proposal dismissed: {proposal['task'][:60]}")
    return True
