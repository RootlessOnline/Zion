"""
Zion Collective Daemon
Runs autonomously when Harley is away.
Manages the agent pipeline: Coordinator → Worker → Reviewer → Logger
"""

import json
import time
import subprocess
import threading
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from python_reviewer import run_python_reviewer
from search_tool import build_search_context, needs_search
from write_gateway import safe_write, safe_write_json, safe_append, WriteViolation
from proposer import run_proposer, approve_proposal, dismiss_proposal

# ── Setup ──────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"
PROMPTS_DIR = BASE_DIR / "prompts"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "daemon.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("zion.daemon")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_prompt(name: str) -> str:
    """Load a single prompt file. Use assemble_prompt() for agent calls."""
    p = PROMPTS_DIR / f"{name}_prompt.md"
    if p.exists():
        return p.read_text()
    return ""


def assemble_prompt(name: str) -> str:
    """
    Assemble a full agent prompt: Page -1 (hard limits) + agent-specific prompt.
    Always use this for agent calls — never load_prompt() directly.
    """
    page_minus_one_path = PROMPTS_DIR / "page_minus_one.md"
    agent_prompt_path   = PROMPTS_DIR / f"{name}_prompt.md"

    parts = []
    if page_minus_one_path.exists():
        parts.append(page_minus_one_path.read_text())
    else:
        log.warning("page_minus_one.md not found — agent running without hard limits prefix")

    if agent_prompt_path.exists():
        parts.append(agent_prompt_path.read_text())
    else:
        log.warning(f"Prompt not found for agent: {name}")

    return "\n\n".join(parts)


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict, agent: str = "daemon"):
    """Write JSON through the write gateway. Falls back to direct write for
    internal data files during startup before gateway is fully initialised."""
    try:
        safe_write_json(path, data, agent=agent)
    except WriteViolation as e:
        log.error(f"save_json blocked by gateway: {e}")
        raise


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Hardware Safety ────────────────────────────────────────────────────────────

def get_free_vram_mb() -> int:
    """Check available VRAM via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        return int(result.stdout.strip())
    except Exception as e:
        log.warning(f"Could not check VRAM: {e}")
        return 99999  # assume OK if we can't check


def get_gpu_temp() -> int:
    """Check GPU temperature."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        return int(result.stdout.strip())
    except Exception:
        return 0


def hardware_is_safe(config: dict) -> tuple[bool, str]:
    """Returns (safe, reason). Checks VRAM and temperature."""
    min_vram = config["daemon"]["vram_minimum_mb"]
    free_vram = get_free_vram_mb()
    if free_vram < min_vram:
        return False, f"VRAM too low: {free_vram}MB free, need {min_vram}MB"

    temp = get_gpu_temp()
    if temp > 82:
        return False, f"GPU temperature too high: {temp}°C"

    return True, "OK"


# ── Ollama Interface ───────────────────────────────────────────────────────────

def call_ollama(system_prompt: str, user_message: str, config: dict) -> str:
    """Call Ollama with a system prompt and user message. Returns response text (no think tags)."""
    url = f"{config['ollama_host']}/api/chat"
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "stream": False,
        "think": True
    }
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        msg = response.json()["message"]
        # DeepSeek-r1 sometimes returns output in thinking instead of content
        return msg.get("content", "") or msg.get("thinking", "")
    except requests.Timeout:
        log.error("Ollama request timed out")
        raise
    except Exception as e:
        log.error(f"Ollama call failed: {e}")
        raise


def parse_json_response(text: str) -> dict:
    """Extract JSON from model response, stripping think tags and markdown fences."""
    import re
    text = text.strip()
    # Strip think tags if present
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try finding JSON object in text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    log.warning(f"Failed to parse JSON response: {text[:200]}")
    return {"error": "parse_failed", "raw": text}


# ── Task Queue ─────────────────────────────────────────────────────────────────

def get_next_task(config: dict) -> dict | None:
    """Get the highest priority pending task from queue."""
    queue_path = DATA_DIR / "task_queue.json"
    queue_data = load_json(queue_path)
    pending = [t for t in queue_data.get("queue", []) if t["status"] == "pending"]

    if not pending:
        # Only pull from TASKS.md if explicitly enabled in config
        if config.get("daemon", {}).get("auto_pull_tasks_md", False):
            return pull_task_from_repo(config)
        return None

    # Sort by priority: harley_flagged > phase > created_at
    def priority_score(task):
        score = 0
        if task.get("harley_flagged"):
            score += 1000
        phase = task.get("phase", 99)
        score += (10 - phase) * 100
        return score

    pending.sort(key=priority_score, reverse=True)
    return pending[0]


def pull_task_from_repo(config: dict) -> dict | None:
    """Pull next task from TASKS.md when queue is empty (Option B)."""
    repo_path = Path(config["collective_repo_path"]).expanduser()
    tasks_file = repo_path / "TASKS.md"
    if not tasks_file.exists():
        return None

    # Find first pending task in the active project
    active_project = load_json(DATA_DIR / "session_state.json").get("active_project", "")
    tasks_content = tasks_file.read_text()

    # Simple parse: find lines with ⏳ Pending status
    lines = tasks_content.split("\n")
    for line in lines:
        if "⏳ Pending" in line and active_project.replace("_", " ").title() in tasks_content:
            task_name = line.split("|")[1].strip() if "|" in line else line.strip()
            if task_name and len(task_name) > 3:
                new_task = {
                    "id": f"AUTO-{int(time.time())}",
                    "project": active_project,
                    "task": task_name,
                    "status": "pending",
                    "assigned_to": "worker",
                    "source": "tasks_md_auto",
                    "phase": 1,
                    "harley_flagged": False,
                    "created": now_iso(),
                    "started": None,
                    "completed": None,
                    "retry_count": 0
                }
                # Add to queue
                queue_path = DATA_DIR / "task_queue.json"
                queue_data = load_json(queue_path)
                queue_data.setdefault("queue", []).append(new_task)
                save_json(queue_path, queue_data)
                log.info(f"Pulled task from TASKS.md: {task_name}")
                # Mark as in-progress in TASKS.md so it won't be pulled again
                tasks_content = tasks_content.replace(
                    line, line.replace("⏳ Pending", "🔄 In Progress (Zion)")
                )
                try:
                    safe_write(tasks_file, tasks_content, mode="write", agent="daemon.task_puller")
                except WriteViolation as e:
                    log.warning(f"Could not mark task in-progress in TASKS.md: {e}")
                return new_task

    return None


def update_task_status(task_id: str, status: str, extra: dict = None):
    """Update a task's status in the queue."""
    queue_path = DATA_DIR / "task_queue.json"
    queue_data = load_json(queue_path)
    for task in queue_data.get("queue", []):
        if task["id"] == task_id:
            task["status"] = status
            if extra:
                task.update(extra)
            break
    save_json(queue_path, queue_data)


# ── Agent Pipeline ─────────────────────────────────────────────────────────────

def build_worker_context(task: dict, config: dict) -> str:
    """Build the dynamic context block injected into Worker's call."""
    repo_path = Path(config["collective_repo_path"]).expanduser()
    project_id = task.get("project", "")
    context_parts = [f"CURRENT TASK: {task['task']}", f"TASK ID: {task['id']}",
                     f"PROJECT: {project_id}"]

    # Load project README
    project_readme = repo_path / "PROJECTS" / project_id / "README.md"
    if project_readme.exists():
        content = project_readme.read_text()[:2000]
        context_parts.append(f"\nPROJECT CONTEXT:\n{content}")

    # Load recent worklog entries
    worklog = repo_path / "STATE" / "worklog.md"
    if worklog.exists():
        lines = worklog.read_text().split("\n")
        recent = "\n".join(lines[-30:])
        context_parts.append(f"\nRECENT WORKLOG (last 30 lines):\n{recent}")

    return "\n\n".join(context_parts)


def run_worker(task: dict, config: dict, socketio=None) -> dict:
    """Run Worker agent on a task."""
    log.info(f"Worker starting task {task['id']}: {task['task']}")
    emit_status(socketio, "worker", "working", f"Working on: {task['task']}")

    system_prompt = assemble_prompt("worker")
    context = build_worker_context(task, config)

    # Inject real web search results if task needs them
    if needs_search(task["task"]):
        emit_status(socketio, "worker", "working", f"Searching web: {task['task'][:40]}...")
        search_context = build_search_context(task["task"])
        if search_context:
            context = context + "\n\n" + search_context
            log.info(f"Web search results injected for task {task['id']}")
        else:
            context = context + "\n\nNOTE: Web search was attempted but returned no results. Do not invent URLs or contact details — state that they could not be found."
            log.warning(f"Web search returned no results for task {task['id']}")

    user_message = f"{context}\n\nComplete this task now. Return only valid JSON."

    try:
        response = call_ollama(system_prompt, user_message, config)
        result = parse_json_response(response)
        result["task_id"] = task["id"]
        log.info(f"Worker completed task {task['id']}")
        emit_status(socketio, "worker", "idle", f"Completed: {task['task']}")
        return result
    except Exception as e:
        log.error(f"Worker failed on task {task['id']}: {e}")
        emit_status(socketio, "worker", "error", str(e))
        return {"task_id": task["id"], "error": str(e), "output": ""}


def run_reviewer(task: dict, worker_output: dict, config: dict, socketio=None) -> dict:
    """Run Python Reviewer on Worker output. Deterministic governance checks, no LLM needed."""
    log.info(f"Reviewer checking task {task['id']}")
    emit_status(socketio, "reviewer", "working", f"Reviewing: {task['task']}")
    repo_path = Path(config["collective_repo_path"]).expanduser()
    try:
        result = run_python_reviewer(task, worker_output, repo_path)
        log.info(f"Reviewer verdict on {task['id']}: {result.get('verdict', 'unknown')}")
        emit_status(socketio, "reviewer", "idle", f"Verdict: {result.get('verdict', '?')}")
        return result
    except Exception as e:
        log.error(f"Reviewer failed on task {task['id']}: {e}")
        emit_status(socketio, "reviewer", "error", str(e))
        return {"task_id": task["id"], "verdict": "approve", "reason": f"Reviewer error — defaulting to approve: {e}", "reviewed_by": "python_reviewer"}


def run_logger(task: dict, worker_output: dict, reviewer_output: dict,
               config: dict, socketio=None):
    """Run Logger agent to write approved output to repo files."""
    log.info(f"Logger writing task {task['id']}")
    emit_status(socketio, "logger", "working", f"Logging: {task['id']}")

    repo_path = Path(config["collective_repo_path"]).expanduser()
    worklog_path = repo_path / "STATE" / "worklog.md"

    # Ensure file exists
    if not worklog_path.exists():
        try:
            safe_write(worklog_path, "# Worklog\n\n", mode="write", agent="logger")
        except WriteViolation as e:
            log.error(f"Could not initialise worklog: {e}")
            return

    # Build log entry
    timestamp = now_iso()
    note = reviewer_output.get("note", "")
    note_line = f"\n**Note:** {note}" if note else ""
    entry = (
        f"\n## {task['id']} — {task.get('project', '')} — {timestamp}\n"
        f"**Task:** {task['task']}\n"
        f"**Agent:** Worker\n"
        f"**Output:** {worker_output.get('output', '')}\n"
        f"**Reviewer verdict:** {reviewer_output.get('verdict', 'unknown')}"
        f"{note_line}\n"
        f"---\n"
    )

    # Append to worklog
    try:
        safe_append(worklog_path, entry, agent="logger")
    except WriteViolation as e:
        log.error(f"Logger blocked from writing worklog: {e}")
        return

    log.info(f"Logger wrote task {task['id']} to worklog")
    emit_status(socketio, "logger", "idle", f"Logged: {task['id']}")

    # Mark task as done in TASKS.md if it was pulled from there
    if task.get("source") == "tasks_md_auto":
        try:
            repo_path = Path(config["collective_repo_path"]).expanduser()
            tasks_file = repo_path / "TASKS.md"
            if tasks_file.exists():
                tc = tasks_file.read_text()
                task_name = task.get("task", "")
                # Replace in-progress marker with done
                import re
                tc = re.sub(
                    rf"(\|[^|]*{re.escape(task_name)}[^|]*\|[^|]*)\🔄 In Progress \(Zion\)",
                    r"✅ Done (Zion)",
                    tc
                )
                safe_write(tasks_file, tc, mode="write", agent="logger.tasks_md")
                log.info(f"Marked task '{task_name}' as done in TASKS.md")
        except Exception as e:
            log.warning(f"Could not update TASKS.md: {e}")

    # Update heartbeat
    write_heartbeat(task)


def write_heartbeat(task: dict):
    """Write progress heartbeat to session_state."""
    state_path = DATA_DIR / "session_state.json"
    state = load_json(state_path)
    state["active_task_id"] = task["id"]
    state["last_action"] = f"Working on: {task['task']}"
    state["resume_on_start"] = True
    save_json(state_path, state)


# ── Full Pipeline ──────────────────────────────────────────────────────────────

def run_pipeline(task: dict, config: dict, socketio=None) -> dict:
    """Run the full Coordinator → Worker → Reviewer → Logger pipeline."""
    log.info(f"Pipeline starting for task {task['id']}")
    update_task_status(task["id"], "in_progress", {"started": now_iso()})

    # Worker
    worker_output = run_worker(task, config, socketio)
    if "error" in worker_output:
        update_task_status(task["id"], "failed",
                           {"error": worker_output["error"], "completed": now_iso()})
        log_error(task, worker_output["error"])
        return {"status": "failed", "reason": "worker_error"}

    # Reviewer — first attempt
    reviewer_output = run_reviewer(task, worker_output, config, socketio)
    verdict = reviewer_output.get("verdict", "reject")

    # Handle reject → one retry
    if verdict == "reject":
        retry_instruction = reviewer_output.get("retry_instruction", "Revise your output.")
        log.info(f"Reviewer rejected task {task['id']}, retrying Worker...")
        retry_count = task.get("retry_count", 0) + 1

        if retry_count >= 2:
            # Two strikes — escalate
            log.warning(f"Task {task['id']} escalated after 2 rejections")
            update_task_status(task["id"], "escalated",
                               {"escalation_reason": reviewer_output.get("reason"),
                                "completed": now_iso()})
            add_to_briefing_escalated(task, reviewer_output)
            return {"status": "escalated"}

        # Retry Worker with Reviewer feedback
        task["retry_count"] = retry_count
        worker_output["retry_context"] = retry_instruction
        worker_output = run_worker(task, config, socketio)
        reviewer_output = run_reviewer(task, worker_output, config, socketio)
        verdict = reviewer_output.get("verdict", "reject")

        if verdict == "reject":
            update_task_status(task["id"], "escalated",
                               {"escalation_reason": reviewer_output.get("reason"),
                                "completed": now_iso()})
            add_to_briefing_escalated(task, reviewer_output)
            return {"status": "escalated"}

    # Approved (with or without note) — run Logger
    run_logger(task, worker_output, reviewer_output, config, socketio)
    update_task_status(task["id"], "completed", {"completed": now_iso()})

    # Update Watcher log
    log_watcher_observation(task, reviewer_output, worker_output)

    log.info(f"Pipeline completed task {task['id']} with verdict: {verdict}")
    return {"status": "completed", "verdict": verdict}


# ── Briefing ───────────────────────────────────────────────────────────────────

def generate_briefing(away_since: str, config: dict) -> str:
    """Generate a briefing file for when Harley returns."""
    queue_data = load_json(DATA_DIR / "task_queue.json")
    completed = [t for t in queue_data.get("queue", []) if t["status"] == "completed"]
    escalated = [t for t in queue_data.get("queue", []) if t["status"] == "escalated"]
    failed = [t for t in queue_data.get("queue", []) if t["status"] == "failed"]
    pending = [t for t in queue_data.get("queue", []) if t["status"] == "pending"]

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
    filename = f"briefing_{timestamp}.md"
    filepath = DATA_DIR / "briefings" / filename

    lines = [
        f"# Briefing — {datetime.now().strftime('%A %d %B %Y at %H:%M')}",
        f"*Generated when Harley returned. Away since: {away_since}*",
        "",
        "## Summary",
        f"{len(completed)} tasks completed. {len(escalated)} need your decision. "
        f"{len(failed)} failed. {len(pending)} still pending.",
        "",
        f"## Completed ({len(completed)})",
    ]
    # Load worklog to get Worker outputs
    worklog_entries = {}
    try:
        repo_path = Path(config["collective_repo_path"]).expanduser()
        worklog = repo_path / "STATE" / "worklog.md"
        if worklog.exists():
            import re
            wlog = worklog.read_text()
            for block in re.split(r"\n---\n", wlog):
                id_match = re.search(r"## (\S+) —", block)
                output_match = re.search(r"\*\*Output:\*\* (.+?)(?:\n\*\*|$)", block, re.DOTALL)
                if id_match and output_match:
                    worklog_entries[id_match.group(1)] = output_match.group(1).strip()
    except Exception:
        pass

    for t in completed:
        lines.append(f"- **{t['id']}** [{t['project']}]: {t['task']}")
        output = worklog_entries.get(t['id'], "")
        if output:
            lines.append(f"  *Output:* {output}")

    if escalated:
        lines += ["", f"## ⚠️ Needs Your Decision ({len(escalated)})"]
        for t in escalated:
            reason = t.get("escalation_reason", "No reason logged")
            lines.append(f"- **{t['id']}** [{t['project']}]: {t['task']}")
            lines.append(f"  *Reason: {reason}*")

    if failed:
        lines += ["", f"## ❌ Failed ({len(failed)})"]
        for t in failed:
            error = t.get("error", "Unknown error")
            lines.append(f"- **{t['id']}**: {t['task']} — {error}")

    if pending:
        lines += ["", f"## Next Up ({len(pending)})"]
        for t in pending[:5]:
            lines.append(f"- **{t['id']}** [{t['project']}]: {t['task']}")

    content = "\n".join(lines)
    try:
        safe_write(filepath, content, mode="write", agent="daemon.briefing")
    except WriteViolation as e:
        log.error(f"Briefing write blocked by gateway: {e}")
        return
    log.info(f"Briefing written to {filepath}")

    # Mark as unread in session state
    state_path = DATA_DIR / "session_state.json"
    state = load_json(state_path)
    state["unread_briefing"] = True
    state["latest_briefing"] = str(filepath)
    save_json(state_path, state)

    # Build structured task data for frontend Keep/Delete cards
    tasks_data = []
    for t in completed:
        tasks_data.append({
            "task_id": t["id"],
            "task": t["task"],
            "project": t["project"],
            "output": worklog_entries.get(t["id"], ""),
            "status": "completed"
        })
    for t in escalated:
        tasks_data.append({
            "task_id": t["id"],
            "task": t["task"],
            "project": t["project"],
            "output": t.get("escalation_reason", ""),
            "status": "escalated"
        })

    return content, tasks_data


def add_to_briefing_escalated(task: dict, reviewer_output: dict):
    """Add an escalated task to the watcher log for inclusion in next briefing."""
    watcher_log = DATA_DIR / "watcher_log.json"
    data = load_json(watcher_log)
    data.setdefault("observations", []).append({
        "timestamp": now_iso(),
        "type": "flag",
        "subject": f"task_{task['id']}",
        "observation": f"Task escalated: {task['task']}. Reason: {reviewer_output.get('reason')}",
        "severity": "warning"
    })
    save_json(watcher_log, data)


def log_error(task: dict, error: str):
    """Log an error to error_log.json."""
    error_log = DATA_DIR / "error_log.json"
    data = load_json(error_log)
    data.setdefault("errors", []).append({
        "timestamp": now_iso(),
        "task_id": task["id"],
        "task": task["task"],
        "error": error
    })
    save_json(error_log, data)


def log_watcher_observation(task: dict, reviewer_output: dict, worker_output: dict):
    """Log task completion data for Watcher analysis."""
    watcher_log = DATA_DIR / "watcher_log.json"
    data = load_json(watcher_log)
    data.setdefault("observations", []).append({
        "timestamp": now_iso(),
        "type": "efficiency",
        "subject": "worker",
        "observation": (
            f"Task {task['id']} completed. "
            f"Verdict: {reviewer_output.get('verdict')}. "
            f"Retries: {task.get('retry_count', 0)}. "
            f"Project: {task.get('project')}."
        ),
        "severity": "info"
    })
    save_json(watcher_log, data)


# ── Socket Emit ────────────────────────────────────────────────────────────────

def emit_status(socketio, agent: str, status: str, action: str):
    """Emit agent status update to dashboard via SocketIO if available."""
    if socketio:
        try:
            socketio.emit("agent_status", {
                "agent": agent,
                "status": status,
                "action": action,
                "timestamp": now_iso()
            })
        except Exception:
            pass


# ── Main Daemon Loop ───────────────────────────────────────────────────────────

class CollectiveDaemon:
    def __init__(self, socketio=None):
        self.config = load_config()
        self.socketio = socketio
        self.running = False
        self.tasks_today = 0
        self.day_start = datetime.now().date()
        self._lock = threading.Lock()
        self._proposal_tick = 0  # count loops, run proposer every N cycles

    def reset_daily_counter(self):
        today = datetime.now().date()
        if today != self.day_start:
            self.tasks_today = 0
            self.day_start = today

    def harley_is_away(self) -> bool:
        state = load_json(DATA_DIR / "session_state.json")
        present = state.get("harley_present", True)

        # Failsafe: if harley_present=true but away_since is >8 hours ago, flip
        if present and state.get("away_since"):
            try:
                away_since = datetime.fromisoformat(state["away_since"])
                hours_away = (datetime.now(timezone.utc) - away_since).total_seconds() / 3600
                failsafe_hours = self.config["daemon"]["inactivity_failsafe_hours"]
                if hours_away > failsafe_hours:
                    log.info(f"Failsafe triggered: {hours_away:.1f}h since last activity")
                    return True
            except Exception:
                pass

        return not present

    def run(self):
        self.running = True
        log.info("Zion daemon started")

        while self.running:
            try:
                self.reset_daily_counter()

                if not self.harley_is_away():
                    time.sleep(60)
                    continue

                # Daily cap check
                daily_cap = self.config["daemon"]["daily_task_cap"]
                if self.tasks_today >= daily_cap:
                    log.info(f"Daily task cap ({daily_cap}) reached, sleeping until tomorrow")
                    time.sleep(3600)
                    continue

                # Hardware safety check
                safe, reason = hardware_is_safe(self.config)
                if not safe:
                    log.warning(f"Hardware not safe: {reason}. Waiting 10 minutes.")
                    time.sleep(600)
                    continue

                # Get next task
                # Run proposer every 30 idle loops (~15 min at 30s sleep)
                self._proposal_tick += 1
                if self._proposal_tick % 30 == 0:
                    try:
                        run_proposer(self.config, self.socketio)
                    except Exception as e:
                        log.warning(f"Proposer error: {e}")

                task = get_next_task(self.config)
                if not task:
                    log.info("No pending tasks. Sleeping 30 seconds.")
                    time.sleep(30)
                    continue

                # Run pipeline
                with self._lock:
                    result = run_pipeline(task, self.config, self.socketio)
                    self.tasks_today += 1
                    log.info(
                        f"Task {task['id']} result: {result['status']}. "
                        f"Today: {self.tasks_today}/{daily_cap}"
                    )

                # Cooldown between tasks
                cooldown = self.config["daemon"]["task_cooldown_seconds"]
                log.info(f"Cooldown: sleeping {cooldown}s")
                time.sleep(cooldown)

            except KeyboardInterrupt:
                log.info("Daemon stopped by keyboard interrupt")
                self.running = False
            except Exception as e:
                log.error(f"Daemon loop error: {e}")
                time.sleep(60)

    def stop(self):
        self.running = False
        log.info("Zion daemon stopping")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    daemon = CollectiveDaemon()
    daemon.run()