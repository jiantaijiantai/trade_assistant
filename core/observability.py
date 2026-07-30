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


import time
from uuid import uuid4

from core.schemas import AuditEvent, RequestContext


def new_request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


class TraceRecorder:
    def __init__(self, context: RequestContext):
        self.context = context
        self.started_at = time.perf_counter()
        self.events: list[AuditEvent] = []

    def record(self, event_type: str, message: str, **data):
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
