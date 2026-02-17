from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from extensions import mongo
from flask_login import login_required, current_user
from datetime import datetime
import uuid
import os

shop = Blueprint("shop", __name__)

# =====================================================
# HOME
# =====================================================
@shop.route("/")
def home():
    page = int(request.args.get("page", 1))
    limit = 8
    skip = (page - 1) * limit

    query = {}
    category = request.args.get("category")
    if category:
        query["category"] = category

    products = list(
        mongo.db.products.find(query).skip(skip).limit(limit)
    )

    total = mongo.db.products.count_documents(query)

    offer_products = list(
        mongo.db.products.find({
            "is_offer": True,
            "offer_price": {"$ne": None}
        })
    )

    banners = list(
        mongo.db.banners.find()
        .sort("created_at", -1)
        .limit(7)
    )

    return render_template(
        "shop.html",
        products=products,
        offer_products=offer_products,
        banners=banners,
        total=total,
        page=page
    )

# =====================================================
# CATEGORY LIST
# =====================================================
@shop.route("/categories")
def categories():
    categories = mongo.db.products.distinct("category")
    category_cards = []

    for cat in categories:
        if not cat:
            continue

        product = mongo.db.products.find_one({
            "category": {
                "$regex": f"^{cat.strip()}\\s*$",
                "$options": "i"
            }
        })

        if not product:
            continue

        images = product.get("images") or []
        image = images[0] if images else product.get("image")

        category_cards.append({
            "name": cat.strip().title(),
            "slug": cat.strip().lower(),
            "image": image
        })

    return render_template(
        "category.html",
        categories=category_cards
    )

# =====================================================
# CATEGORY PRODUCTS
# =====================================================
@shop.route("/category/<category_name>")
def category_page(category_name):
    normalized_category = category_name.replace("-", " ").strip()

    offer_products = list(
        mongo.db.products.find({
            "category": {
                "$regex": f"^{normalized_category}$",
                "$options": "i"   # case-insensitive
            },
            "is_offer": True,
            "offer_price": {"$ne": None}
        })
    )

    normal_products = list(
        mongo.db.products.find({
            "category": {
                "$regex": f"^{normalized_category}$",
                "$options": "i"
            },
            "$or": [
                {"is_offer": {"$ne": True}},
                {"offer_price": None}
            ]
        })
    )

    return render_template(
        "category_products.html",
        category_name=normalized_category.title(),
        offer_products=offer_products,
        products=normal_products
    )

# =====================================================
# PRODUCT DETAILS
# =====================================================
@shop.route("/product/<product_id>")
def product_detail(product_id):
    try:
        product_id = ObjectId(product_id)
    except InvalidId:
        return redirect(url_for("shop.home"))

    product = mongo.db.products.find_one({"_id": product_id})
    if not product:
        return redirect(url_for("shop.home"))

    reviews = list(
        mongo.db.reviews.find(
            {"product_id": product_id}
        ).sort("created_at", -1)
    )

    related_products = list(
        mongo.db.products.find({
            "category": product.get("category"),
            "_id": {"$ne": product["_id"]}
        }).limit(5)
    )

    return render_template(
        "product.html",
        product=product,
        reviews=reviews,
        related_products=related_products
    )

# =====================================================
# ADD REVIEW
# =====================================================
@shop.route("/product/<product_id>/review", methods=["POST"])
@login_required
def add_review(product_id):
    rating = int(request.form.get("rating"))
    comment = request.form.get("comment")

    uploaded_files = request.files.getlist("images")
    image_urls = []

    review_folder = os.path.join(os.getcwd(), "static", "reviews")
    os.makedirs(review_folder, exist_ok=True)

    for file in uploaded_files:
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1]
            filename = f"{uuid.uuid4().hex}{ext}"
            save_path = os.path.join(review_folder, filename)
            file.save(save_path)
            image_urls.append(f"/static/reviews/{filename}")

    mongo.db.reviews.insert_one({
        "product_id": ObjectId(product_id),
        "user_id": current_user.id,
        "user_name": getattr(current_user, "name", "User"),
        "rating": rating,
        "comment": comment,
        "images": image_urls,
        "created_at": datetime.utcnow()
    })

    return redirect(
        url_for("shop.product_detail", product_id=product_id)
    )

# =====================================================
# EDIT REVIEW
# =====================================================
@shop.route("/review/<review_id>/edit", methods=["POST"])
@login_required
def edit_review(review_id):
    review = mongo.db.reviews.find_one({
        "_id": ObjectId(review_id),
        "user_id": current_user.id
    })

    if not review:
        return "Unauthorized", 403

    rating = int(request.form.get("rating"))
    comment = request.form.get("comment")

    uploaded_files = request.files.getlist("images")
    image_urls = []

    review_folder = os.path.join(os.getcwd(), "static", "reviews")
    os.makedirs(review_folder, exist_ok=True)

    if uploaded_files and uploaded_files[0].filename:
        for img in review.get("images", []):
            img_path = os.path.join(os.getcwd(), img.lstrip("/"))
            if os.path.exists(img_path):
                os.remove(img_path)

        for file in uploaded_files:
            if file and file.filename:
                ext = os.path.splitext(file.filename)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                save_path = os.path.join(review_folder, filename)
                file.save(save_path)
                image_urls.append(f"/static/reviews/{filename}")
    else:
        image_urls = review.get("images", [])

    mongo.db.reviews.update_one(
        {"_id": ObjectId(review_id)},
        {"$set": {
            "rating": rating,
            "comment": comment,
            "images": image_urls,
            "updated_at": datetime.utcnow()
        }}
    )

    return redirect(
        url_for("shop.product_detail", product_id=review["product_id"])
    )

# =====================================================
# DELETE REVIEW
# =====================================================
@shop.route("/review/<review_id>/delete", methods=["POST"])
@login_required
def delete_review(review_id):
    review = mongo.db.reviews.find_one({
        "_id": ObjectId(review_id),
        "user_id": current_user.id
    })

    if not review:
        return "Unauthorized", 403

    for img in review.get("images", []):
        img_path = os.path.join(os.getcwd(), img.lstrip("/"))
        if os.path.exists(img_path):
            os.remove(img_path)

    mongo.db.reviews.delete_one({"_id": ObjectId(review_id)})

    return redirect(
        url_for("shop.product_detail", product_id=review["product_id"])
    )

@shop.route("/notifications")
@login_required

def notifications():
    notifications = list(
        mongo.db.notifications
        .find({"user_id": str(current_user.id)})
        .sort("created_at", -1)
    )

    unread_count = mongo.db.notifications.count_documents({
        "user_id": str(current_user.id),
        "is_read": False
    })

    return jsonify({
        "notifications": notifications,
        "unread_count": unread_count
    })
def clear_notifications():
    mongo.db.notifications.delete_many({
        "user_id": str(current_user.id)
    })

    return jsonify({"success": True})

