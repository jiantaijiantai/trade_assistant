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


import hashlib

from core.schemas import PolicyDecision, RequestContext, ToolSpec


def build_idempotency_key(
    context: RequestContext,
    action_type: str,
    business_id: str,
) -> str:
    raw = f"{context.tenant_id}:{context.user_id}:{action_type}:{business_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"idem_{digest}"


def check_roles(context: RequestContext, required_roles: list[str]) -> PolicyDecision:
    if not required_roles:
        return PolicyDecision(allowed=True, reason="工具不要求特定角色")

    owned = set(context.roles)
    required = set(required_roles)

    if required.issubset(owned):
        return PolicyDecision(allowed=True, reason="用户角色满足要求")

    missing = sorted(required - owned)
    return PolicyDecision(
        allowed=False,
        reason=f"缺少角色：{', '.join(missing)}",
    )


def check_cost_budget(
    context: RequestContext,
    current_cost_units: int,
    next_cost_units: int,
) -> PolicyDecision:
    total = current_cost_units + next_cost_units

    if total <= context.max_cost_units:
        return PolicyDecision(
            allowed=True,
            reason=f"成本预算通过：{total}/{context.max_cost_units}",
        )

    return PolicyDecision(
        allowed=False,
        reason=f"成本预算不足：{total}/{context.max_cost_units}",
    )


def check_tool_permission(
    context: RequestContext,
    tool: ToolSpec,
) -> PolicyDecision:
    return check_roles(context, tool.required_roles)
