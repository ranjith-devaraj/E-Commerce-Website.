from flask import Blueprint, render_template, redirect, url_for, jsonify, request, session
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from extensions import mongo

cart = Blueprint("cart", __name__)

# =========================
# HELPER: OFFER-AWARE PRICE
# =========================
def get_effective_price(product):
    if product.get("is_offer") and product.get("offer_price"):
        return float(product["offer_price"])
    return float(product["price"])

# =========================
# ADD TO CART (UNIVERSAL AJAX) ✅ FIX
# =========================
@cart.route("/cart/add", methods=["POST"])
@login_required
def add_to_cart_universal():
    data = request.get_json(silent=True) or {}

    product_id = data.get("product_id")
    qty = int(data.get("qty", 1))

    if not product_id:
        return jsonify({"success": False}), 400

    product = mongo.db.products.find_one(
        {"_id": ObjectId(product_id)}
    )

    if not product:
        return jsonify({"success": False}), 404

    price = get_effective_price(product)

    cart_data = mongo.db.carts.find_one({"user_id": current_user.id})

    if not cart_data:
        mongo.db.carts.insert_one({
            "user_id": current_user.id,
            "items": [{
                "product_id": product["_id"],
                "name": product["name"],
                "price": price,
                "qty": qty,
                "item_total": qty * price
            }]
        })
    else:
        _add_or_update_item(cart_data, product, qty)

    return jsonify({"success": True})

@cart.route("/cart/count")
@login_required
def cart_count():
    cart = mongo.db.carts.find_one({"user_id": current_user.id})
    if not cart or "items" not in cart:
        return jsonify({"count": 0})

    count = sum(item["qty"] for item in cart["items"])
    return jsonify({"count": count})

# =========================
# VIEW CART
# =========================
@cart.route("/cart")
@login_required
def view_cart():
    cart_doc = mongo.db.carts.find_one({"user_id": current_user.id})
    raw_items = cart_doc["items"] if cart_doc and "items" in cart_doc else []

    items = []

    for item in raw_items:
        product = mongo.db.products.find_one(
            {"_id": ObjectId(item["product_id"])}
        )
        if not product:
            continue

        # ✅ OFFER-AWARE PRICE
        price = get_effective_price(product)
        original_price = product["price"] if product.get("is_offer") else None
        qty = int(item["qty"])

        items.append({
            "product_id": str(product["_id"]),
            "name": product["name"],
            "price": price,
            "original_price": original_price,
            "qty": qty,
            "item_total": price * qty,
            "image": product.get("image"),
            "is_offer": product.get("is_offer", False)
        })

    return render_template("cart.html", items=items)


# =========================
# ADD TO CART (NORMAL)
# =========================
@cart.route("/cart/add/<product_id>")
@login_required

def add_to_cart(product_id):
    product = mongo.db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        return redirect("/")

    price = get_effective_price(product)

    cart_data = mongo.db.carts.find_one({"user_id": current_user.id})

    if not cart_data:
        mongo.db.carts.insert_one({
            "user_id": current_user.id,
            "items": [{
                "product_id": product["_id"],
                "name": product["name"],
                "price": price,
                "qty": 1,
                "item_total": price
            }]
        })
    else:
        _add_or_update_item(cart_data, product, 1)

    return redirect(url_for("cart.view_cart"))


# =========================
# ADD TO CART (AJAX)
# =========================
@cart.route("/cart/add-ajax/<product_id>", methods=["POST"])
@login_required
def add_to_cart_ajax(product_id):
    data = request.get_json(silent=True) or {}
    qty = int(data.get("qty", 1))

    product = mongo.db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        return jsonify({"success": False}), 404

    cart_data = mongo.db.carts.find_one({"user_id": current_user.id})

    if not cart_data:
        price = get_effective_price(product)
        mongo.db.carts.insert_one({
            "user_id": current_user.id,
            "items": [{
                "product_id": product["_id"],
                "name": product["name"],
                "price": price,
                "qty": qty,
                "item_total": qty * price
            }]
        })
    else:
        _add_or_update_item(cart_data, product, qty)

    return jsonify({"success": True})


# =========================
# BUY NOW (WITH QTY)
# =========================
@cart.route("/cart/buy-now/<product_id>", methods=["POST"])
@login_required
def buy_now(product_id):
    qty = int(request.form.get("qty", 1))

    product = mongo.db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        return redirect(url_for("shop.home"))

    # OFFER-AWARE PRICE
    if product.get("is_offer") and product.get("offer_price"):
        price = product["offer_price"]
    else:
        price = product["price"]

    # ✅ STORE IN SESSION (NOT DB CART)
    session["buy_now"] = [{
        "product_id": str(product["_id"]),
        "name": product["name"],
        "price": price,
        "qty": qty,
        "item_total": price * qty
    }]

    return redirect(url_for("orders.checkout"))


# =========================
# UPDATE QUANTITY (+ / -)
# =========================
@cart.route("/cart/update/<product_id>/<action>")
@login_required
def update_quantity(product_id, action):
    cart_data = mongo.db.carts.find_one({"user_id": current_user.id})
    if not cart_data:
        return redirect(url_for("cart.view_cart"))

    for item in cart_data["items"]:
        if str(item["product_id"]) == product_id:
            if action == "increase":
                item["qty"] += 1
            elif action == "decrease" and item["qty"] > 1:
                item["qty"] -= 1

            item["item_total"] = item["qty"] * item["price"]
            break

    mongo.db.carts.update_one(
        {"_id": cart_data["_id"]},
        {"$set": {"items": cart_data["items"]}}
    )

    return redirect(url_for("cart.view_cart"))


# =========================
# REMOVE ITEM
# =========================
@cart.route("/cart/remove/<product_id>")
@login_required
def remove_item(product_id):
    cart_data = mongo.db.carts.find_one({"user_id": current_user.id})
    if not cart_data:
        return redirect(url_for("cart.view_cart"))

    cart_data["items"] = [
        item for item in cart_data["items"]
        if str(item["product_id"]) != product_id
    ]

    mongo.db.carts.update_one(
        {"_id": cart_data["_id"]},
        {"$set": {"items": cart_data["items"]}}
    )

    return redirect(url_for("cart.view_cart"))


# =========================
# INTERNAL HELPER
# =========================
def _add_or_update_item(cart_data, product, qty):
    price = get_effective_price(product)
    found = False

    for item in cart_data["items"]:
        if item["product_id"] == product["_id"]:
            item["qty"] += qty
            item["price"] = price  # ✅ always sync offer price
            item["item_total"] = item["qty"] * price
            found = True
            break

    if not found:
        cart_data["items"].append({
            "product_id": product["_id"],
            "name": product["name"],
            "price": price,
            "qty": qty,
            "item_total": qty * price
        })

    mongo.db.carts.update_one(
        {"_id": cart_data["_id"]},
        {"$set": {"items": cart_data["items"]}}
    )
