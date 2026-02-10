import hmac
import os
from functools import wraps
from typing import Callable

from flask import abort, redirect, request, session, url_for


def _admin_password() -> str:
    return os.getenv("IMAGESORTER_PASSWORD", "")


def login_required(fn: Callable):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        pw = _admin_password()
        if not pw:
            return fn(*args, **kwargs)
        if session.get("authed") is True:
            return fn(*args, **kwargs)
        if request.path.startswith("/api/"):
            abort(401)
        return redirect(url_for("login", next=request.path))

    return wrapper


def check_password(candidate: str) -> bool:
    pw = _admin_password()
    if not pw:
        return True
    return hmac.compare_digest(candidate or "", pw)


def upload_token_ok(candidate: str) -> bool:
    token = os.getenv("IMAGESORTER_UPLOAD_TOKEN", "")
    if not token:
        return False
    return hmac.compare_digest(candidate or "", token)

