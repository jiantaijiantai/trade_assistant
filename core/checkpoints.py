from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.task_state import TaskStatus, can_transition


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASK_STORE_DIR = PROJECT_ROOT / "outputs" / "task_checkpoints"


def new_task_id(request_id: str) -> str:
    return f"task_{request_id.removeprefix('req_')}"


def create_task_record(
    *,
    task_id: str,
    initial_state: dict[str, Any],
    require_approval: bool,
) -> dict[str, Any]:
    now = _now()
    record = {
        "task_id": task_id,
        "status": TaskStatus.CREATED.value,
        "created_at": now,
        "updated_at": now,
        "require_approval": require_approval,
        "approval": None,
        "initial_state": initial_state,
        "latest_state": initial_state,
        "checkpoints": [
            {
                "checkpoint_id": f"{task_id}_created",
                "status": TaskStatus.CREATED.value,
                "created_at": now,
                "state": initial_state,
            }
        ],
    }
    _write_record(record)
    return record


def load_task_record(task_id: str) -> dict[str, Any]:
    path = _record_path(task_id)
    if not path.exists():
        raise FileNotFoundError(f"Task not found: {task_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_task_checkpoint(
    *,
    task_id: str,
    status: TaskStatus,
    state: dict[str, Any],
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = load_task_record(task_id)
    current_status = TaskStatus(record["status"])
    if current_status != status and not can_transition(current_status, status):
        raise ValueError(f"Invalid task transition: {current_status.value} -> {status.value}")

    now = _now()
    record["status"] = status.value
    record["updated_at"] = now
    record["latest_state"] = state
    if approval is not None:
        record["approval"] = approval

    record.setdefault("checkpoints", []).append(
        {
            "checkpoint_id": f"{task_id}_{len(record.get('checkpoints', [])):04d}",
            "status": status.value,
            "created_at": now,
            "state": state,
        }
    )
    _write_record(record)
    return record


def save_replay_record(
    *,
    source_task_id: str,
    replay_task_id: str,
    initial_state: dict[str, Any],
    require_approval: bool,
) -> dict[str, Any]:
    source = load_task_record(source_task_id)
    save_task_checkpoint(
        task_id=source_task_id,
        status=TaskStatus.REPLAYED,
        state=source["latest_state"],
    )
    return create_task_record(
        task_id=replay_task_id,
        initial_state=initial_state,
        require_approval=require_approval,
    )


def _record_path(task_id: str) -> Path:
    return TASK_STORE_DIR / f"{task_id}.json"


def _write_record(record: dict[str, Any]) -> None:
    TASK_STORE_DIR.mkdir(parents=True, exist_ok=True)
    _record_path(record["task_id"]).write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
