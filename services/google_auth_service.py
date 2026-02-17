from authlib.integrations.flask_client import OAuth
from flask import redirect, url_for, session
from extensions import mongo
from models.user_model import User
from flask_login import login_user
from datetime import datetime

oauth = OAuth()

def init_google_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def google_login():
    return oauth.google.authorize_redirect(
        url_for("auth.google_callback", _external=True)
    )


def google_callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get("userinfo")

    if not user_info:
        return redirect("/login")

    user = mongo.db.users.find_one({"email": user_info["email"]})

    if not user:
        user_id = mongo.db.users.insert_one({
            "name": user_info["name"],
            "email": user_info["email"],
            "google_id": user_info["sub"],
            "role": "user",
            "created_at": datetime.utcnow()
        }).inserted_id

        user = mongo.db.users.find_one({"_id": user_id})

    login_user(User(user))
    return redirect(session.get("next") or "/")
