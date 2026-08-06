from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    CREATED = "created"
    ROUTED = "routed"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REPLAYED = "replayed"


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {
        TaskStatus.ROUTED,
        TaskStatus.WAITING_APPROVAL,
        TaskStatus.RUNNING,
        TaskStatus.SUCCEEDED,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
        TaskStatus.REPLAYED,
    },
    TaskStatus.ROUTED: {TaskStatus.WAITING_APPROVAL, TaskStatus.RUNNING, TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.REPLAYED},
    TaskStatus.WAITING_APPROVAL: {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.FAILED, TaskStatus.REPLAYED},
    TaskStatus.RUNNING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.WAITING_APPROVAL, TaskStatus.REPLAYED},
    TaskStatus.SUCCEEDED: {TaskStatus.REPLAYED},
    TaskStatus.FAILED: {TaskStatus.REPLAYED},
    TaskStatus.CANCELLED: {TaskStatus.REPLAYED},
    TaskStatus.REPLAYED: {TaskStatus.ROUTED, TaskStatus.RUNNING, TaskStatus.FAILED},
}


def can_transition(current: str | TaskStatus, target: str | TaskStatus) -> bool:
    current_status = TaskStatus(current)
    target_status = TaskStatus(target)
    return target_status in ALLOWED_TRANSITIONS[current_status]
