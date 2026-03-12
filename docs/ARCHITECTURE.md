# Zion — Architecture

> Full technical architecture from 5 rounds of planning.

---

## Overview

```
┌─────────────────────────────────────────────────────┐
│                     ZION                            │
│                                                     │
│  ┌─────────┐  ┌──────────────────┐  ┌───────────┐  │
│  │  Agent  │  │   Manager Chat   │  │  Watcher  │  │
│  │  Panel  │  │   (centre)       │  │  Panel    │  │
│  │  (left) │  │                  │  │  (right)  │  │
│  └─────────┘  └──────────────────┘  └───────────┘  │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Control Bar: Handoff | Stop | Daemon | Git  │   │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                         │
                    reads/writes
                         │
              ┌──────────────────┐
              │  RootlessOnline  │
              │  (project repo)  │
              └──────────────────┘
```

---

## Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Model serving | Ollama | Runs Gemma 3 12B locally on GPU |
| Model | Gemma 3 12B | Single model, multiple roles via system prompts |
| Dashboard backend | Flask + SocketIO | Serves UI, handles API, real-time agent updates |
| Dashboard frontend | Vanilla HTML/CSS/JS | No heavy frameworks, fast and lightweight |
| Agent pipeline | Python | Coordinator → Worker → Reviewer → Logger |
| Scheduler | Python daemon thread | Autonomous task execution when Harley is away |
| Data storage | JSON files | task_queue, session_state, briefings, watcher_log |
| Repo writes | Python file I/O | Direct writes to local clone of RootlessOnline |
| Git sync | GitPython | Harley-triggered push to GitHub |

---

## Data Layer

```
Zion/data/
├── task_queue.json      ← All tasks: pending/in_progress/completed/escalated/failed
├── session_state.json   ← Harley present/away, active project, resume state
├── watcher_log.json     ← Private log: agent efficiency, chat history, patterns
├── error_log.json       ← All errors from daemon (never deleted)
├── feedback_log.json    ← Harley's approve/reject feedback on Manager outputs
├── daemon.log           ← Daemon activity log (text)
└── briefings/
    └── briefing_YYYY-MM-DDTHH-MM.md   ← One per return session
```

---

## Agent Roles

### Manager
- Talks to Harley directly
- Distributes work to other agents
- Synthesises results back to Harley
- Always active (not just when Harley is away)

### Worker
- Executes assigned tasks
- Reads project context from RootlessOnline repo
- Output goes to Reviewer before anything is logged
- One retry if rejected

### Reviewer
- Governance compliance checker (not quality judge)
- Checks 5 things: $0 budget, human sovereignty, literal communication, decision log consistency, regeneration
- Three verdicts: approve / approve_with_note / reject
- Two-strikes rule: second rejection escalates to Harley

### Logger
- Writes approved outputs to RootlessOnline repo files
- Append-only, never overwrites
- Writes to: STATE/worklog.md, STATE/decision_log.md
- Creates briefing files in Zion/data/briefings/

### Watcher
- Silent observer — doesn't interfere with tasks
- Tracks: efficiency, chat history, unresolved ideas, patterns
- Private log: only Harley sees it
- Reflection mode: 3-way conversation (Harley + Watcher + Manager)

---

## Daemon Loop

```python
while running:
    if harley_is_away():
        if daily_cap_reached():     → sleep 1hr
        if hardware_not_safe():     → sleep 10min
        task = get_next_task()
        if no_task:                 → sleep 5min
        else:
            run_pipeline(task)      → Coordinator→Worker→Reviewer→Logger
            cooldown(2min)
    else:
        sleep(1min)
```

---

## Task Priority

1. Harley-flagged tasks (always first)
2. Phase 1 > Phase 2 > Phase 3+ tasks
3. Tasks that unblock other tasks
4. FIFO when equal

---

## Hardware Safety Rules

| Rule | Threshold | Action |
|------|-----------|--------|
| VRAM check | < 3GB free | Defer task 10min |
| Temperature | > 82°C | Defer task |
| Task cooldown | Always | 2min sleep between tasks |
| Daily cap | 20 tasks/day | Sleep until tomorrow |
| Task timeout | 3 minutes | Kill Ollama, restart, retry once |

---

## "Keep Me In Loop While Out"

When Harley is away:
- Daemon runs tasks from queue
- Heartbeat writes to session_state.json every 15min
- Logger appends to worklog.md after each completed task
- Errors logged to error_log.json
- Escalations flagged in task_queue.json

When Harley returns (clicks "I'm back"):
- Briefing auto-generated from completed/escalated/failed tasks
- Briefing shown immediately in Manager chat
- Escalated items highlighted at top
- Task queue shows what's still pending

---

## Version Control Flow

```
Agents write locally → Zion/data/ + RootlessOnline/ (local clone)
                                        ↓
                          Harley reviews (anytime)
                                        ↓
                     Harley clicks "Sync to GitHub"
                                        ↓
                    git add . && git commit && git push
                    (to selected branch in dropdown)
```

AIs never push to GitHub automatically. Harley controls all syncs.
This follows CONSTITUTION Principle 4: Human Sovereignty.
