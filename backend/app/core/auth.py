"""Auth dependency. AUTH_MODE=none uses a demo identity (role from X-Demo-Role header);
AUTH_MODE=firebase verifies Firebase ID tokens and reads the `role` custom claim."""
from __future__ import annotations

from fastapi import Header, HTTPException

from ..config import settings

_fb_ready = False


def _init_firebase() -> None:
    global _fb_ready
    if not _fb_ready:
        import firebase_admin

        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"projectId": settings.project})
        _fb_ready = True


async def current_user(authorization: str | None = Header(default=None),
                       x_demo_role: str | None = Header(default=None)) -> dict:
    if settings.auth_mode != "firebase":
        return {"uid": "demo", "email": "demo@local", "role": x_demo_role or "demo"}
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    _init_firebase()
    from firebase_admin import auth as fb_auth

    try:
        claims = fb_auth.verify_id_token(authorization.removeprefix("Bearer "))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(401, f"invalid token: {e}") from e
    # Without custom claims every signed-in user is a demo user with access to all views.
    return {"uid": claims["uid"], "email": claims.get("email"), "role": claims.get("role", "demo")}
