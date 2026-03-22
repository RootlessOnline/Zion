"""
Zion Dashboard Server
Flask + SocketIO backend serving the Zion UI and handling API calls.
"""

import json
import threading
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS

# ── Governance boot check ─────────────────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent / "governance"))
from validator import boot_check
boot_check()

# ── Setup ──────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"
PROMPTS_DIR = BASE_DIR / "prompts"

app = Flask(__name__, template_folder="dashboard", static_folder="dashboard/static")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Import daemon
import sys
sys.path.insert(0, str(BASE_DIR / "daemon"))
from collective_daemon import (
    CollectiveDaemon, load_config, load_json, save_json,
    now_iso, generate_briefing, call_ollama, load_prompt, assemble_prompt
)
from write_gateway import safe_write, safe_write_json, safe_append, WriteViolation
from proposer import run_proposer, approve_proposal, dismiss_proposal

config = load_config()
daemon = CollectiveDaemon(socketio=socketio)
daemon_thread = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_state():
    return load_json(DATA_DIR / "session_state.json")


def set_state(updates: dict):
    state = get_state()
    state.update(updates)
    save_json(DATA_DIR / "session_state.json", state)


def get_queue():
    return load_json(DATA_DIR / "task_queue.json")


def get_watcher_log():
    watcher_path = DATA_DIR / "watcher_log.json"
    return load_json(watcher_path)


def get_latest_briefing() -> str:
    briefings_dir = DATA_DIR / "briefings"
    briefings = sorted(briefings_dir.glob("briefing_*.md"), reverse=True)
    if briefings:
        return briefings[0].read_text()
    return "No briefings yet."


def get_all_briefings():
    briefings_dir = DATA_DIR / "briefings"
    briefings = sorted(briefings_dir.glob("briefing_*.md"), reverse=True)
    return [{"name": b.name, "date": b.stem.replace("briefing_", "")} for b in briefings]


# ── Git Operations ─────────────────────────────────────────────────────────────

def get_git_branches(repo_path: str) -> list:
    try:
        result = subprocess.run(
            ["git", "branch", "-a"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        branches = [b.strip().replace("* ", "") for b in result.stdout.strip().split("\n")]
        return [b for b in branches if b]
    except Exception:
        return ["main"]


def git_status(repo_path: str) -> dict:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        changed = [l for l in result.stdout.strip().split("\n") if l]
        return {"changed_files": len(changed), "files": changed}
    except Exception:
        return {"changed_files": 0, "files": []}


def git_push(repo_path: str, branch: str, message: str) -> dict:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        token = os.environ.get("GITHUB_TOKEN", "")
        user = os.environ.get("GITHUB_USER", "RootlessOnline")

        # Set remote URL with token
        remote_url = f"https://{user}:{token}@github.com/{user}/Zion.git"
        subprocess.run(["git", "remote", "set-url", "origin", remote_url], cwd=repo_path, timeout=10)

        subprocess.run(["git", "add", "."], cwd=repo_path, timeout=30)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path, timeout=30
        )
        result = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=repo_path, capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return {"success": True, "message": "Pushed to GitHub"}
        else:
            return {"success": False, "message": result.stderr}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    state = get_state()
    queue = get_queue()
    pending = [t for t in queue.get("queue", []) if t["status"] == "pending"]
    in_progress = [t for t in queue.get("queue", []) if t["status"] == "in_progress"]
    completed_today = [t for t in queue.get("queue", []) if t["status"] == "completed"]
    escalated = [t for t in queue.get("queue", []) if t["status"] == "escalated"]

    return jsonify({
        "state": state,
        "queue_summary": {
            "pending": len(pending),
            "in_progress": len(in_progress),
            "completed": len(completed_today),
            "escalated": len(escalated)
        },
        "tasks": {
            "pending": pending,
            "in_progress": in_progress,
            "escalated": escalated
        },
        "config": {
            "projects": config["projects"],
            "model": config["model"]
        }
    })


@app.route("/api/handoff", methods=["POST"])
def api_handoff():
    """Harley clicks 'Hand off to agents'."""
    set_state({
        "harley_present": False,
        "away_since": now_iso(),
        "resume_on_start": True
    })
    socketio.emit("status_change", {"harley_present": False})
    return jsonify({"success": True, "message": "Agents are now working. See you when you're back."})


@app.route("/api/im_back", methods=["POST"])
def api_im_back():
    """Harley clicks 'I'm back'."""
    state = get_state()
    away_since = state.get("away_since", now_iso())
    set_state({
        "harley_present": True,
        "away_since": None,
        "resume_on_start": False,
        "unread_briefing": False
    })
    briefing, tasks_data = generate_briefing(away_since, config)
    socketio.emit("status_change", {"harley_present": True})
    socketio.emit("briefing_ready", {"briefing": briefing, "tasks": tasks_data})
    return jsonify({"success": True, "briefing": briefing, "tasks": tasks_data})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    """Emergency stop — freeze all agents."""
    note = request.json.get("note", "")
    set_state({
        "harley_present": True,
        "emergency_stop": True,
        "stop_note": note,
        "stop_time": now_iso()
    })
    socketio.emit("emergency_stop", {"note": note})
    return jsonify({"success": True, "message": "All agents paused."})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    """Resume after emergency stop."""
    set_state({"emergency_stop": False, "stop_note": None})
    socketio.emit("resume", {})
    return jsonify({"success": True})


@app.route("/api/switch_project", methods=["POST"])
def api_switch_project():
    """Switch active project."""
    project_id = request.json.get("project_id")
    valid_ids = [p["id"] for p in config["projects"]]
    if project_id not in valid_ids:
        return jsonify({"success": False, "message": "Unknown project"})
    set_state({"active_project": project_id})
    socketio.emit("project_switched", {"project_id": project_id})
    return jsonify({"success": True, "project_id": project_id})


@app.route("/api/add_task", methods=["POST"])
def api_add_task():
    """Add a task to the queue."""
    data = request.json
    task = {
        "id": f"T{int(datetime.now().timestamp())}",
        "project": data.get("project", get_state().get("active_project")),
        "task": data["task"],
        "status": "pending",
        "assigned_to": "worker",
        "harley_flagged": data.get("priority", False),
        "phase": data.get("phase", 1),
        "created": now_iso(),
        "started": None,
        "completed": None,
        "retry_count": 0
    }
    queue_path = DATA_DIR / "task_queue.json"
    queue_data = load_json(queue_path)
    queue_data.setdefault("queue", []).append(task)
    save_json(queue_path, queue_data)
    socketio.emit("task_added", task)
    return jsonify({"success": True, "task": task})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Send a message to Manager agent. Returns thinking + answer separately."""
    message = request.json.get("message", "")
    history = request.json.get("history", [])
    active_project = get_state().get("active_project", "garden_business")

    system_prompt = assemble_prompt("manager")
    context_msg = f"[Active project: {active_project}]\n\nHarley says: {message}"

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": context_msg})

    try:
        url = f"{config['ollama_host']}/api/chat"
        payload = {
            "model": config["model"],
            "messages": messages,
            "stream": False
        }
        response = requests.post(url, json=payload, timeout=180)

        if not response.ok:
            return jsonify({"success": False, "response": f"Ollama error {response.status_code}: {response.text[:200]}"})

        msg = response.json().get("message", {})
        thinking = msg.get("thinking", "")
        answer = msg.get("content", "")

        # DeepSeek-r1 sometimes embeds think tags inside content
        if not thinking and "<think>" in answer:
            import re
            m = re.search(r"<think>(.*?)</think>", answer, re.DOTALL)
            if m:
                thinking = m.group(1).strip()
                answer = answer.replace(m.group(0), "").strip()

        result = f"<think>{thinking}</think>\n{answer}" if thinking else answer

        watcher_data = load_json(DATA_DIR / "watcher_log.json")
        watcher_data.setdefault("chat_history", []).append({
            "timestamp": now_iso(),
            "project": active_project,
            "harley": message,
            "manager": answer
        })
        save_json(DATA_DIR / "watcher_log.json", watcher_data)

        return jsonify({"success": True, "response": result})
    except Exception as e:
        return jsonify({"success": False, "response": f"Manager unavailable: {str(e)}"})


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    """Store feedback on Manager output for learning."""
    data = request.json
    feedback_path = DATA_DIR / "feedback_log.json"
    feedback_data = load_json(feedback_path)
    feedback_data.setdefault("feedback", []).append({
        "timestamp": now_iso(),
        "approved": data.get("approved"),
        "message": data.get("message"),
        "response": data.get("response"),
        "feedback_text": data.get("feedback_text", ""),
        "project": get_state().get("active_project")
    })
    save_json(feedback_path, feedback_data)
    return jsonify({"success": True})


@app.route("/api/watcher")
def api_watcher():
    """Get Watcher log data."""
    return jsonify(get_watcher_log())


@app.route("/api/reflect", methods=["POST"])
def api_reflect():
    """Start a Watcher reflection session."""
    watcher_data = get_watcher_log()
    observations = watcher_data.get("observations", [])
    chat_history = watcher_data.get("chat_history", [])

    system_prompt = assemble_prompt("watcher")
    context = (
        f"RECENT OBSERVATIONS:\n{json.dumps(observations[-20:], indent=2)}\n\n"
        f"RECENT CHAT HISTORY:\n{json.dumps(chat_history[-10:], indent=2)}\n\n"
        "Harley wants to reflect. Present your observations plainly."
    )

    try:
        response = call_ollama(system_prompt, context, config)
        return jsonify({"success": True, "reflection": response})
    except Exception as e:
        return jsonify({"success": False, "reflection": f"Watcher unavailable: {str(e)}"})


@app.route("/api/tasks", methods=["GET"])
def api_tasks():
    """Return all tasks — pending, completed, escalated, benched."""
    queue_data = load_json(DATA_DIR / "task_queue.json")
    queue = queue_data.get("queue", [])

    # Load worklog outputs for completed tasks
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

    for t in queue:
        if t["status"] == "completed" and t["id"] in worklog_entries:
            t["output"] = worklog_entries[t["id"]]

    return jsonify({"success": True, "tasks": queue})


@app.route("/api/task/reorder", methods=["POST"])
def api_task_reorder():
    """Reorder pending tasks in the queue."""
    ordered_ids = request.json.get("ids", [])
    queue_path = DATA_DIR / "task_queue.json"
    queue_data = load_json(queue_path)
    queue = queue_data.get("queue", [])

    # Separate pending from non-pending
    pending = {t["id"]: t for t in queue if t["status"] == "pending"}
    non_pending = [t for t in queue if t["status"] != "pending"]

    # Reorder pending by provided id list
    reordered = [pending[tid] for tid in ordered_ids if tid in pending]
    # Add any pending tasks not in the list at the end
    reordered += [t for t in queue if t["status"] == "pending" and t["id"] not in ordered_ids]

    queue_data["queue"] = non_pending + reordered
    save_json(queue_path, queue_data)
    return jsonify({"success": True})


@app.route("/api/task/bench", methods=["POST"])
def api_task_bench():
    """Move a task to benched status — won't be picked up by daemon."""
    task_id = request.json.get("task_id")
    queue_path = DATA_DIR / "task_queue.json"
    queue_data = load_json(queue_path)
    for t in queue_data.get("queue", []):
        if t["id"] == task_id:
            t["status"] = "benched"
            break
    save_json(queue_path, queue_data)
    return jsonify({"success": True})


@app.route("/api/task/unbench", methods=["POST"])
def api_task_unbench():
    """Move a benched task back to pending."""
    task_id = request.json.get("task_id")
    queue_path = DATA_DIR / "task_queue.json"
    queue_data = load_json(queue_path)
    for t in queue_data.get("queue", []):
        if t["id"] == task_id:
            t["status"] = "pending"
            break
    save_json(queue_path, queue_data)
    return jsonify({"success": True})


@app.route("/api/task/keep", methods=["POST"])
def api_task_keep():
    """Save a task output to approved_outputs.json for future use as example."""
    task_id = request.json.get("task_id")
    task_text = request.json.get("task")
    output = request.json.get("output")
    project = request.json.get("project", "")
    if not task_id or not output:
        return jsonify({"success": False, "error": "Missing task_id or output"})
    approved_path = DATA_DIR / "approved_outputs.json"
    approved = load_json(approved_path) if approved_path.exists() else {"outputs": []}
    # Don't duplicate
    existing_ids = [o["task_id"] for o in approved.get("outputs", [])]
    if task_id not in existing_ids:
        approved.setdefault("outputs", []).append({
            "task_id": task_id,
            "task": task_text,
            "output": output,
            "project": project,
            "approved_at": now_iso()
        })
        save_json(approved_path, approved)
    return jsonify({"success": True})


@app.route("/api/task/delete", methods=["POST"])
def api_task_delete():
    """Remove a task output from the worklog."""
    task_id = request.json.get("task_id")
    if not task_id:
        return jsonify({"success": False, "error": "Missing task_id"})
    try:
        repo_path = Path(config["collective_repo_path"]).expanduser()
        worklog = repo_path / "STATE" / "worklog.md"
        if worklog.exists():
            content_wl = worklog.read_text()
            # Remove the block for this task_id
            import re
            blocks = re.split(r"\n---\n", content_wl)
            kept = [b for b in blocks if task_id not in b]
            safe_write(worklog, "\n---\n".join(kept), mode="write", agent="api.task_delete")
        # Also mark task as deleted in queue
        queue_path = DATA_DIR / "task_queue.json"
        queue_data = load_json(queue_path)
        queue_data["queue"] = [t for t in queue_data.get("queue", []) if t["id"] != task_id]
        save_json(queue_path, queue_data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/worklog")
def api_worklog():
    """Return recent worklog entries from the repo."""
    try:
        repo_path = Path(config["collective_repo_path"]).expanduser()
        worklog = repo_path / "STATE" / "worklog.md"
        if worklog.exists():
            lines = worklog.read_text().split("\n")
            # Return last 100 lines
            return jsonify({"success": True, "content": "\n".join(lines[-100:])})
        return jsonify({"success": True, "content": "No worklog yet."})
    except Exception as e:
        return jsonify({"success": False, "content": str(e)})


@app.route("/api/briefings")
def api_briefings():
    return jsonify({
        "latest": get_latest_briefing(),
        "history": get_all_briefings()
    })


@app.route("/api/briefing/<filename>")
def api_briefing_file(filename):
    filepath = DATA_DIR / "briefings" / filename
    if filepath.exists():
        return jsonify({"content": filepath.read_text()})
    return jsonify({"content": "Not found"}), 404


@app.route("/api/git/status")
def api_git_status():
    repo_path = Path(config["collective_repo_path"]).expanduser()
    branches = get_git_branches(str(repo_path))
    status = git_status(str(repo_path))
    return jsonify({"branches": branches, "status": status})


@app.route("/api/git/push", methods=["POST"])
def api_git_push():
    data = request.json
    repo_path = Path(config["collective_repo_path"]).expanduser()
    branch = data.get("branch", "main")
    message = data.get("message", f"Zion sync {now_iso()}")
    result = git_push(str(repo_path), branch, message)
    return jsonify(result)


@app.route("/api/daemon/start", methods=["POST"])
def api_daemon_start():
    global daemon_thread
    if daemon_thread and daemon_thread.is_alive():
        return jsonify({"success": False, "message": "Daemon already running"})
    daemon.running = True
    daemon_thread = threading.Thread(target=daemon.run, daemon=True)
    daemon_thread.start()
    return jsonify({"success": True, "message": "Daemon started"})


@app.route("/api/daemon/stop", methods=["POST"])
def api_daemon_stop():
    daemon.stop()
    return jsonify({"success": True, "message": "Daemon stopping"})


@app.route("/api/daemon/status")
def api_daemon_status():
    running = daemon_thread is not None and daemon_thread.is_alive()
    return jsonify({
        "running": running,
        "tasks_today": daemon.tasks_today,
        "daily_cap": config["daemon"]["daily_task_cap"]
    })



# ── OS Mode — Proposals ────────────────────────────────────────────────────────

@app.route("/api/proposals")
def api_get_proposals():
    from proposer import load_proposals
    data = load_proposals()
    pending = [p for p in data.get("proposals", []) if p.get("status") == "pending"]
    return jsonify({"success": True, "proposals": pending})


@app.route("/api/proposals/approve", methods=["POST"])
def api_approve_proposal():
    proposal_id = request.json.get("proposal_id")
    task = approve_proposal(proposal_id, config)
    if not task:
        return jsonify({"success": False, "message": "Proposal not found"})
    socketio.emit("task_added", task)
    return jsonify({"success": True, "task": task})


@app.route("/api/proposals/dismiss", methods=["POST"])
def api_dismiss_proposal():
    proposal_id = request.json.get("proposal_id")
    ok = dismiss_proposal(proposal_id)
    return jsonify({"success": ok})


@app.route("/api/proposals/run", methods=["POST"])
def api_run_proposer():
    try:
        added = run_proposer(config, socketio)
        from proposer import load_proposals
        data = load_proposals()
        pending = [p for p in data.get("proposals", []) if p.get("status") == "pending"]
        return jsonify({"success": True, "added": added, "proposals": pending})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ── SocketIO Events ────────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    state = get_state()
    socketio.emit("connected", {
        "harley_present": state.get("harley_present", True),
        "active_project": state.get("active_project", "garden_business")
    })


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = config.get("dashboard_port", 5000)
    print(f"\n🟢 Zion starting at http://localhost:{port}\n")
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
