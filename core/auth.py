from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, Field

from rag.access_control import BUSINESS_DEPARTMENT_ID, DEFAULT_TENANT_ID


AUTH_MODE = (os.getenv("APP_AUTH_MODE") or "development").strip().lower()


class Principal(BaseModel):
    tenant_id: str
    user_id: str
    roles: list[str] = Field(default_factory=list)
    department_ids: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    clearance_level: str = "internal"
    auth_source: str = "development_fallback"


class IdentityFallback(BaseModel):
    tenant_id: str = DEFAULT_TENANT_ID
    user_id: str = "user_demo"
    roles: list[str] = Field(default_factory=lambda: ["operator", "analyst"])
    department_ids: list[str] = Field(default_factory=lambda: [BUSINESS_DEPARTMENT_ID])
    groups: list[str] = Field(default_factory=list)
    clearance_level: str = "internal"


def resolve_principal(headers: Mapping[str, str], fallback: IdentityFallback | None = None) -> Principal:
    header_principal = _principal_from_headers(headers)
    if header_principal is not None:
        return header_principal

    if AUTH_MODE == "production":
        raise PermissionError("Missing authenticated identity headers")

    fallback = fallback or IdentityFallback()
    return Principal(
        tenant_id=fallback.tenant_id,
        user_id=fallback.user_id,
        roles=fallback.roles,
        department_ids=fallback.department_ids,
        groups=fallback.groups,
        clearance_level=fallback.clearance_level,
        auth_source="development_fallback",
    )


def identity_kwargs(principal: Principal) -> dict[str, object]:
    return {
        "tenant_id": principal.tenant_id,
        "user_id": principal.user_id,
        "roles": principal.roles,
        "department_ids": principal.department_ids,
        "groups": principal.groups,
        "clearance_level": principal.clearance_level,
    }


def _principal_from_headers(headers: Mapping[str, str]) -> Principal | None:
    tenant_id = _header(headers, "x-tenant-id")
    user_id = _header(headers, "x-user-id")
    if not tenant_id or not user_id:
        return None

    return Principal(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=_split_header(_header(headers, "x-roles")) or ["operator"],
        department_ids=_split_header(_header(headers, "x-department-ids")) or [BUSINESS_DEPARTMENT_ID],
        groups=_split_header(_header(headers, "x-groups")),
        clearance_level=_header(headers, "x-clearance-level") or "internal",
        auth_source="headers",
    )


def _header(headers: Mapping[str, str], name: str) -> str:
    value = headers.get(name) or headers.get(name.title())
    return str(value or "").strip()


def _split_header(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
