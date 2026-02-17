from functools import wraps
from flask import redirect, url_for, session, abort
from flask_login import current_user


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            session["next"] = url_for("auth.login")
            return redirect(url_for("auth.login"))

        if current_user.role != "admin":
            abort(403)

        return func(*args, **kwargs)
    return wrapper


def login_required_with_redirect(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            session["next"] = url_for(func.__name__)
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)
    return wrapper



def roles_required(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if current_user.role not in roles:
                abort(403)
            return func(*args, **kwargs)
        return wrapper
    return decorator
