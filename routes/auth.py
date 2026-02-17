from flask import Blueprint, render_template, request, redirect, session, url_for
from flask_login import login_user, logout_user, login_required
from extensions import mongo, bcrypt
from services.mail_service import send_email
from models.user_model import User

from oauthlib.oauth2 import WebApplicationClient
import requests
import os
import random
import time
from datetime import datetime

auth = Blueprint("auth", __name__)

OTP_EXPIRY_SECONDS = 300  # 5 minutes


# =====================================================
# GOOGLE OAUTH CONFIG
# =====================================================
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
google_client = WebApplicationClient(GOOGLE_CLIENT_ID)


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


# =====================================================
# LOGIN (EMAIL + PASSWORD)
# =====================================================
@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = mongo.db.users.find_one({"email": email})

        if not user or not user.get("password"):
            return render_template("login.html", error="Invalid email or password")

        if not bcrypt.check_password_hash(user["password"], password):
            return render_template("login.html", error="Invalid email or password")

        login_user(User(user))

        if user.get("role") == "admin":
            return redirect("/admin/dashboard")

        return redirect("/")

    return render_template("login.html")


# =====================================================
# REGISTER (SEND OTP ONLY – NO DB WRITE)
# =====================================================
@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        if mongo.db.users.find_one({"email": email}):
            return render_template("register.html", error="Email already registered")

        otp = str(random.randint(100000, 999999))

        session["otp"] = otp
        session["otp_time"] = time.time()
        session["pending_user"] = {
            "name": name,
            "email": email,
            "password": password  # temporary plain password
        }

        send_email(
            email,
            "Email Verification OTP",
            f"Your OTP is {otp}. Valid for 5 minutes."
        )

        return redirect(url_for("auth.verify_otp"))

    return render_template("register.html")


# =====================================================
# VERIFY OTP (CREATE USER HERE)
# =====================================================
@auth.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        user_otp = request.form.get("otp")

        if "otp" not in session or "pending_user" not in session:
            return redirect(url_for("auth.register"))

        if time.time() - session["otp_time"] > OTP_EXPIRY_SECONDS:
            session.clear()
            return render_template("verify_otp.html", error="OTP expired")

        if user_otp != session["otp"]:
            return render_template("verify_otp.html", error="Invalid OTP")

        data = session["pending_user"]

        hashed_password = bcrypt.generate_password_hash(
            data["password"]
        ).decode("utf-8")

        mongo.db.users.insert_one({
            "name": data["name"],
            "email": data["email"],
            "password": hashed_password,
            "role": "user",
            "created_at": datetime.utcnow()
        })

        session.clear()
        return redirect(url_for("auth.login"))

    return render_template("verify_otp.html")


# =====================================================
# GOOGLE LOGIN START
# =====================================================
@auth.route("/google/login")
def google_login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = google_client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


# =====================================================
# GOOGLE LOGIN CALLBACK
# =====================================================
@auth.route("/google/login/callback")
def google_callback():
    code = request.args.get("code")

    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    token_url, headers, body = google_client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )

    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    google_client.parse_request_body_response(token_response.text)

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = google_client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    userinfo = userinfo_response.json()

    if not userinfo.get("email_verified"):
        return "Email not verified by Google", 400

    email = userinfo["email"]
    name = userinfo["name"]
    google_id = userinfo["sub"]

    user = mongo.db.users.find_one({"email": email})

    if not user:
        user_id = mongo.db.users.insert_one({
            "name": name,
            "email": email,
            "google_id": google_id,
            "role": "user",
            "created_at": datetime.utcnow()
        }).inserted_id

        user = mongo.db.users.find_one({"_id": user_id})

    login_user(User(user))
    return redirect("/")


# =====================================================
# LOGOUT
# =====================================================
@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")
