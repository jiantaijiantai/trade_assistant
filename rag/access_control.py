from __future__ import annotations

from core.schemas import RequestContext
from rag.schemas import MetadataValue, SearchHit


DEFAULT_TENANT_ID = "company_internal"
BUSINESS_DEPARTMENT_ID = "business"
BUSINESS_COLLECTION_NAME = "company_internal__business"

VISIBILITY_DEPARTMENT = "department"
VISIBILITY_GROUP = "group"
VISIBILITY_ROLE = "role"
VISIBILITY_USERS = "users"

SENSITIVITY_LEVELS = {
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}


def build_default_acl_metadata(
    tenant_id: str = DEFAULT_TENANT_ID,
    department_id: str = BUSINESS_DEPARTMENT_ID,
    owner_user_id: str = "",
    visibility: str = VISIBILITY_DEPARTMENT,
    allowed_user_ids: str = "",
    allowed_roles: str = "",
    allowed_groups: str = "",
    sensitivity_level: str = "internal",
) -> dict[str, MetadataValue]:
    return {
        "tenant_id": tenant_id or DEFAULT_TENANT_ID,
        "department_id": department_id or BUSINESS_DEPARTMENT_ID,
        "collection_key": department_id or BUSINESS_DEPARTMENT_ID,
        "owner_user_id": owner_user_id,
        "visibility": visibility or VISIBILITY_DEPARTMENT,
        "allowed_user_ids": allowed_user_ids,
        "allowed_roles": allowed_roles,
        "allowed_groups": allowed_groups,
        "sensitivity_level": sensitivity_level or "internal",
    }


def build_vector_where(context: RequestContext) -> dict[str, object]:
    return {
        "$and": [
            {"tenant_id": context.tenant_id},
            {"department_id": BUSINESS_DEPARTMENT_ID},
        ]
    }


def filter_authorized_hits(
    hits: list[SearchHit],
    context: RequestContext,
) -> list[SearchHit]:
    return [hit for hit in hits if can_access_metadata(context, hit.metadata)]


def can_access_metadata(
    context: RequestContext,
    metadata: dict[str, MetadataValue],
) -> bool:
    if str(metadata.get("tenant_id", "")) != context.tenant_id:
        return False

    if not _has_sufficient_clearance(context.clearance_level, str(metadata.get("sensitivity_level", "internal"))):
        return False

    roles = set(context.roles)
    if "admin" in roles:
        return True

    department_id = str(metadata.get("department_id", ""))
    if department_id and department_id not in set(context.department_ids):
        return False

    visibility = str(metadata.get("visibility", VISIBILITY_DEPARTMENT) or VISIBILITY_DEPARTMENT)
    if visibility == VISIBILITY_DEPARTMENT:
        return bool(department_id and department_id in set(context.department_ids))

    if visibility == VISIBILITY_ROLE:
        return bool(roles.intersection(_split_acl_value(metadata.get("allowed_roles"))))

    if visibility == VISIBILITY_GROUP:
        return bool(set(context.groups).intersection(_split_acl_value(metadata.get("allowed_groups"))))

    if visibility == VISIBILITY_USERS:
        return context.user_id in _split_acl_value(metadata.get("allowed_user_ids"))

    return False


def _has_sufficient_clearance(user_level: str, document_level: str) -> bool:
    user_rank = SENSITIVITY_LEVELS.get((user_level or "internal").lower(), 0)
    document_rank = SENSITIVITY_LEVELS.get((document_level or "internal").lower(), 1)
    return user_rank >= document_rank


def _split_acl_value(value: MetadataValue | None) -> set[str]:
    if value is None:
        return set()

    return {item.strip() for item in str(value).split(",") if item.strip()}
