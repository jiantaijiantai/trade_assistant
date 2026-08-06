\
\
\
\
\
\
\
\
\
\


import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.schemas import AuditEvent, RequestContext

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_LOG_PATH = PROJECT_ROOT / "logs" / "runtime.jsonl"


def new_request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


def write_runtime_log(
    event_type: str,
    message: str,
    *,
    request_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    if _env_bool("DISABLE_RUNTIME_LOGS", default=False):
        return

    path = Path(os.getenv("RUNTIME_LOG_PATH") or DEFAULT_RUNTIME_LOG_PATH)
    payload = {
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "event_type": event_type,
        "message": message,
        "request_id": request_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "data": data or {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(payload, ensure_ascii=False) + "\n")


class TraceRecorder:
    def __init__(self, context: RequestContext):
        self.context = context
        self.started_at = time.perf_counter()
        self.events: list[AuditEvent] = []

    def record(self, event_type: str, message: str, **data):
        write_runtime_log(
            event_type,
            message,
            request_id=self.context.request_id,
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            data=data,
        )
        self.events.append(
            AuditEvent(
                request_id=self.context.request_id,
                event_type=event_type,
                message=message,
                data=data,
            )
        )

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.started_at) * 1000)

    def to_dict(self):
        return {
            "request_id": self.context.request_id,
            "tenant_id": self.context.tenant_id,
            "user_id": self.context.user_id,
            "elapsed_ms": self.elapsed_ms(),
            "events": [event.model_dump() for event in self.events],
        }


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
