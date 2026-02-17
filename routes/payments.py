from flask import Blueprint, request, redirect
from flask_login import login_required, current_user
from extensions import mongo
from datetime import datetime

payments = Blueprint("payments", __name__)

@payments.route("/payment/submit", methods=["POST"])
@login_required
def submit_payment():
    mongo.db.payments.insert_one({
        "user_id": current_user.id,
        "order_id": request.form.get("order_id"),
        "upi_ref": request.form.get("upi_ref"),
        "app": request.form.get("app"),
        "status": "Payment Submitted",
        "created_at": datetime.utcnow()
    })
    return redirect("/orders")
