import logging
import uuid
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from quart import abort, current_app, request

from config import CONFIG_AUTH_CLIENT, CONFIG_SEARCH_CLIENT
from core.authentication import AuthError
from core.effective_access import resolve_effective_access
from error import error_response
from mongo_table_connecters.data_group import get_data_group_by_id
from mongo_table_connecters.teams import get_team_by_id
from mongo_table_connecters.users import get_user_by_ad_email, get_user_by_id


def _content_access_claims(path: str, auth_claims: dict[str, Any]) -> dict[str, Any]:
    """Add validated application Data Group claims for Team-scoped content paths."""
    normalized_path = str(path or "").replace("|", "/").lstrip("/")
    team_id = normalized_path.split("/", 1)[0]
    try:
        uuid.UUID(team_id)
    except (ValueError, TypeError, AttributeError):
        return auth_claims
    team = get_team_by_id(team_id) if team_id else None
    if not team:
        return auth_claims

    application_user_id = str(auth_claims.get("application_user_id") or "").strip()
    username = auth_claims.get("preferred_username") or auth_claims.get("email") or auth_claims.get("upn")
    user = get_user_by_id(application_user_id) if application_user_id else (
        get_user_by_ad_email(str(username)) if username else None
    )
    data_groups = [
        get_data_group_by_id(str(group_id))
        for group_id in (team.get("data_group_id") or [])
    ]
    access = resolve_effective_access(
        user=user,
        team=team,
        data_groups=data_groups,
    )
    trusted_claims = dict(auth_claims)
    trusted_claims["team_id"] = access.team_id
    trusted_claims["data_groups_id"] = [item.id for item in access.data_groups]
    trusted_claims["selected_scopes"] = []
    trusted_claims["application_user_id"] = access.user_id
    return trusted_claims


def authenticated_path(route_fn: Callable[[str, dict[str, Any]], Any]):
    """
    Decorator for routes that request a specific file that might require access control enforcement
    """

    @wraps(route_fn)
    async def auth_handler(path=""):
        # If authentication is enabled, validate the user can access the file
        if "|" in path:
            path = path.replace("|","/")
        auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
        search_client = current_app.config[CONFIG_SEARCH_CLIENT]
        authorized = False
        try:
            auth_claims = await auth_helper.get_auth_claims_if_enabled(request.headers)
            if getattr(auth_helper, "require_access_control", False):
                auth_claims = _content_access_claims(path, auth_claims)
            authorized = await auth_helper.check_path_auth(path, auth_claims, search_client)
        except AuthError:
            abort(403)
        except Exception as error:
            logging.exception("Problem checking path auth %s", error)
            return error_response(error, route="/content")

        if not authorized:
            abort(403)

        return await route_fn(path, auth_claims)

    return auth_handler


_C = TypeVar("_C", bound=Callable[..., Any])


def authenticated(route_fn: _C) -> _C:
    """
    Decorator for routes that might require access control. Unpacks Authorization header information into an auth_claims dictionary
    """

    @wraps(route_fn)
    async def auth_handler(*args, **kwargs):
        auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
        try:
            auth_claims = await auth_helper.get_auth_claims_if_enabled(request.headers)
        except AuthError:
            abort(403)

        return await route_fn(auth_claims, *args, **kwargs)

    return cast(_C, auth_handler)
