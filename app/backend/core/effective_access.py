from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


ALLOWED_DATA_SCOPES = frozenset({"global", "personal"})
DATA_GROUP_ACCESS_TEAM = "team"
DATA_GROUP_ACCESS_SELECTED_USERS = "selected_users"


class AccessControlError(ValueError):
    def __init__(self, message: str, *, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class EffectiveDataGroup:
    id: str
    name: str
    access_mode: str
    member_count: int

    def serialize(self) -> dict[str, Any]:
        return {
            "_id": self.id,
            "name": self.name,
            "access_mode": self.access_mode,
            "member_count": self.member_count,
        }


@dataclass(frozen=True)
class EffectiveAccess:
    user_id: str
    team_id: str
    team_name: str
    data_groups: tuple[EffectiveDataGroup, ...]
    selected_data_group_ids: tuple[str, ...]
    selected_scopes: tuple[str, ...]
    agent_id: str | None
    is_system_admin: bool

    def serialize(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "team": {"_id": self.team_id, "name": self.team_name},
            "data_groups": [item.serialize() for item in self.data_groups],
            "selected_data_group_ids": list(self.selected_data_group_ids),
            "selected_scopes": list(self.selected_scopes),
            "agent_id": self.agent_id,
            "is_system_admin": self.is_system_admin,
        }


def _unique_strings(value: Any, field: str, *, maximum: int = 100) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise AccessControlError(f"{field} must be an array of at most {maximum} values", status_code=400)
    result: list[str] = []
    for item in value:
        normalized = str(item or "").strip()
        if not normalized:
            raise AccessControlError(f"{field} contains an invalid value", status_code=400)
        if normalized not in result:
            result.append(normalized)
    return result


def resolve_effective_access(
    *,
    user: dict[str, Any] | None,
    team: dict[str, Any] | None,
    data_groups: Iterable[dict[str, Any] | None],
    requested_data_group_ids: Any = None,
    requested_scopes: Any = None,
    agent_id: str | None = None,
) -> EffectiveAccess:
    if not user or not user.get("_id") or user.get("active", True) is not True:
        raise AccessControlError("The signed-in application user is unavailable")
    if not team or not team.get("_id"):
        raise AccessControlError("Team not found", status_code=404)

    user_id = str(user["_id"])
    team_id = str(team["_id"])
    is_system_admin = user.get("is_sys_admin") is True
    team_user_ids = {str(item) for item in (team.get("user_id") or [])}
    if not is_system_admin and user_id not in team_user_ids:
        raise AccessControlError("You are not a member of this team")

    normalized_agent_id = str(agent_id or "").strip() or None
    team_agent_ids = {str(item) for item in (team.get("agent_id") or [])}
    if normalized_agent_id and normalized_agent_id not in team_agent_ids:
        raise AccessControlError("The selected agent does not belong to this team")

    team_group_ids = [str(item) for item in (team.get("data_group_id") or [])]
    groups_by_id = {
        str(item.get("_id")): item
        for item in data_groups
        if item and item.get("_id") and str(item.get("_id")) in team_group_ids
    }
    available: list[EffectiveDataGroup] = []
    for group_id in team_group_ids:
        group = groups_by_id.get(group_id)
        if not group:
            continue
        member_ids = {str(item) for item in (group.get("user_id") or [])}
        configured_mode = str(group.get("access_mode") or "").strip().lower()
        access_mode = configured_mode or (
            DATA_GROUP_ACCESS_TEAM if not member_ids else DATA_GROUP_ACCESS_SELECTED_USERS
        )
        if access_mode not in {DATA_GROUP_ACCESS_TEAM, DATA_GROUP_ACCESS_SELECTED_USERS}:
            access_mode = DATA_GROUP_ACCESS_SELECTED_USERS
        if not is_system_admin and access_mode == DATA_GROUP_ACCESS_SELECTED_USERS and user_id not in member_ids:
            continue
        available.append(
            EffectiveDataGroup(
                id=group_id,
                name=str(group.get("name") or group_id),
                access_mode=access_mode,
                member_count=len(member_ids),
            )
        )

    requested_group_ids = _unique_strings(requested_data_group_ids, "data_groups_id")
    available_ids = {item.id for item in available}
    denied_group_ids = [item for item in requested_group_ids if item not in available_ids]
    if denied_group_ids:
        raise AccessControlError("One or more selected data groups are not available to this user")

    scopes = _unique_strings(requested_scopes, "selected_scopes", maximum=2)
    if any(item not in ALLOWED_DATA_SCOPES for item in scopes):
        raise AccessControlError("selected_scopes contains an unsupported scope", status_code=400)

    return EffectiveAccess(
        user_id=user_id,
        team_id=team_id,
        team_name=str(team.get("name") or team_id),
        data_groups=tuple(available),
        selected_data_group_ids=tuple(requested_group_ids),
        selected_scopes=tuple(scopes),
        agent_id=normalized_agent_id,
        is_system_admin=is_system_admin,
    )
