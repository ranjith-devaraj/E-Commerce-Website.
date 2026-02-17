from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from extensions import mongo
from bson import ObjectId

notifications = Blueprint("notifications", __name__)

@notifications.route("/notifications", methods=["GET"])
@login_required
def get_notifications():

    user_object_id = ObjectId(current_user.id)

    notifs = list(
        mongo.db.notifications.find(
            {"user_id": user_object_id}
        ).sort("created_at", -1)
    )

    unread_count = mongo.db.notifications.count_documents({
        "user_id": user_object_id,
        "is_read": False
    })

    # Convert ObjectId → string for frontend
    for n in notifs:
        n["_id"] = str(n["_id"])
        n["user_id"] = str(n["user_id"])

    return jsonify({
        "notifications": notifs,
        "unread_count": unread_count
    })

@notifications.route("/notifications/mark-read", methods=["POST"])
@login_required
def mark_notifications_read():
    mongo.db.notifications.update_many(
        {"user_id": ObjectId(current_user.id)},
        {"$set": {"is_read": True}}
    )
    return jsonify({"success": True})
@notifications.route("/notifications/clear", methods=["POST"])
@login_required
def clear_notifications():
    mongo.db.notifications.delete_many({
        "user_id": ObjectId(current_user.id)
    })

    return jsonify({"success": True})
