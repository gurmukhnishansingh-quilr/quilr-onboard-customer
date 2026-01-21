from fastapi import Depends, HTTPException
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from starlette.responses import RedirectResponse
import base64
import json
import time

from .config import settings

oauth = OAuth()
oauth.register(
    name="microsoft",
    client_id=settings.ms_client_id,
    client_secret=settings.ms_client_secret,
    server_metadata_url=settings.ms_metadata_url,
    client_kwargs={"scope": "openid profile email User.Read"},
)


def _dev_user() -> dict:
    return {"name": "Dev User", "email": "dev@local", "mode": "dev"}


async def login(request: Request) -> RedirectResponse:
    if settings.dev_auth_bypass:
        request.session["user"] = _dev_user()
        return RedirectResponse(f"{settings.frontend_url}/dashboard")
    if not settings.ms_client_id or not settings.ms_client_secret:
        raise HTTPException(
            status_code=500,
            detail="Microsoft OAuth is not configured. Set MS_CLIENT_ID and MS_CLIENT_SECRET.",
        )
    return await oauth.microsoft.authorize_redirect(request, settings.ms_redirect_uri)


async def callback(request: Request) -> RedirectResponse:
    if settings.dev_auth_bypass:
        request.session["user"] = _dev_user()
        return RedirectResponse(f"{settings.frontend_url}/dashboard")
    token = await oauth.microsoft.authorize_access_token(request)
    user = None
    claims = None
    try:
        claims = await oauth.microsoft.parse_id_token(request, token)
        _ensure_group_access(claims)
        user = claims
    except Exception:
        userinfo = await oauth.microsoft.userinfo(token=token)
        if userinfo:
            _ensure_group_access(userinfo)
            user = {
                "email": userinfo.get("email") or userinfo.get("upn"),
                "name": userinfo.get("name"),
                "sub": userinfo.get("sub"),
            }
    if not user:
        raise HTTPException(status_code=401, detail="Failed to authenticate user.")
    request.session["user"] = {
        "email": user.get("email") or user.get("preferred_username"),
        "name": user.get("name"),
        "sub": user.get("sub"),
    }
    return RedirectResponse(f"{settings.frontend_url}/dashboard")


def get_current_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user and settings.dev_auth_bypass:
        user = _dev_user()
        request.session["user"] = user
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user


def require_user(user: dict = Depends(get_current_user)) -> dict:
    return user


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _extract_group_claims(claims: dict) -> set[str]:
    values: set[str] = set()
    for key in ("groups", "roles", "wids"):
        raw = claims.get(key)
        if isinstance(raw, list):
            values.update(str(item) for item in raw if item)
        elif isinstance(raw, str) and raw:
            values.add(raw)
    return values


def _ensure_group_access(
    claims: dict | None, extra_groups: list[str] | None = None
) -> None:
    if settings.dev_auth_bypass:
        return
    required_names = set(settings.auth_required_group_names or [])
    required_ids = set(settings.auth_required_group_ids or [])
    if not required_names and not required_ids:
        return
    if not claims:
        raise HTTPException(status_code=403, detail="You don't have access.")
    candidates = _extract_group_claims(claims)
    if extra_groups:
        candidates.update(str(item) for item in extra_groups if item)
    if not candidates:
        raise HTTPException(
            status_code=403,
            detail="You don't have access. Missing group claims.",
        )
    if required_names.intersection(candidates) or required_ids.intersection(candidates):
        return
    raise HTTPException(
        status_code=403,
        detail="You don't have access. User is not in CustomerOnboardAdmin.",
    )


def decode_id_token(id_token: str) -> dict:
    parts = id_token.split(".")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid ID token format.")
    try:
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid ID token payload.") from exc
    return payload


def create_session_from_id_token(
    id_token: str, groups: list[str] | None = None
) -> dict:
    claims = decode_id_token(id_token)
    _ensure_group_access(claims, groups)
    now = int(time.time())
    exp = claims.get("exp")
    if exp and exp < now:
        raise HTTPException(status_code=401, detail="ID token has expired.")
    if settings.ms_client_id:
        aud = claims.get("aud")
        if aud and aud != settings.ms_client_id:
            raise HTTPException(status_code=401, detail="ID token audience mismatch.")
    if not settings.allow_unverified_tokens:
        raise HTTPException(
            status_code=403,
            detail="Token verification is disabled without JWKS configuration.",
        )
    return {
        "email": claims.get("preferred_username")
        or claims.get("email")
        or claims.get("upn"),
        "name": claims.get("name") or claims.get("given_name"),
        "sub": claims.get("sub"),
        "mode": "frontend-oauth",
    }
