from flask import Blueprint, render_template, redirect, url_for, request, session
from flask_login import login_required, current_user
from extensions import mongo
from datetime import datetime
from bson.objectid import ObjectId

orders = Blueprint("orders", __name__)

# -------------------------------------------------
# HELPER: GET FINAL PRICE (OFFER-AWARE)
# -------------------------------------------------
def get_effective_price(product):
    if product.get("is_offer") and product.get("offer_price"):
        return float(product["offer_price"])
    return float(product["price"])


# -------------------------------------------------
# CHECKOUT
# -------------------------------------------------
@orders.route("/checkout")
@login_required
def checkout():

    # ✅ BUY NOW
    buy_now_items = session.get("buy_now")

    if buy_now_items:
        items = buy_now_items
        source = "buy_now"
    else:
        cart = mongo.db.carts.find_one({"user_id": current_user.id})
        if not cart or not cart.get("items"):
            return redirect(url_for("cart.view_cart"))

        items = cart["items"]
        source = "cart"

    total = sum(item["item_total"] for item in items)

    # ✅ UPI SETTINGS
    settings = mongo.db.settings.find_one({"_id": "upi_settings"})
    upi_id = settings.get("upi_id") if settings else None
    shop_name = settings.get("shop_name") if settings else None

    return render_template(
        "checkout.html",
        items=items,          # 🔑 IMPORTANT
        total=total,
        source=source,
        upi_id=upi_id,
        shop_name=shop_name
    )

# -------------------------------------------------
# PLACE ORDER
# -------------------------------------------------
@orders.route("/place-order", methods=["POST"])
@login_required
def place_order():
    payment_method = request.form.get("payment_method")
    address = request.form.get("address")
    source = request.form.get("source")

    # ---------------- GET ITEMS ----------------
    if source == "buy_now":
        items = session.get("buy_now")
        if not items:
            return redirect(url_for("shop.home"))
    else:
        cart = mongo.db.carts.find_one({"user_id": current_user.id})
        if not cart or not cart.get("items"):
            return redirect(url_for("orders.checkout"))
        items = cart["items"]

    total = 0
    order_items = []

    for item in items:
        product = mongo.db.products.find_one(
            {"_id": ObjectId(item["product_id"])}
        )
        if not product:
            continue

        qty = int(item["qty"])

        # 🔴 CHECK STOCK
        if product["stock"] < qty:
            return redirect(url_for("cart.view_cart"))

        price = get_effective_price(product)
        item_total = price * qty

        total += item_total

        order_items.append({
            "product_id": str(product["_id"]),
            "name": product["name"],
            "price": price,
            "original_price": product["price"] if product.get("is_offer") else None,
            "qty": qty,
            "item_total": item_total,
            "is_offer": product.get("is_offer", False)
        })

        # 🔴 DECREASE STOCK
        mongo.db.products.update_one(
            {"_id": product["_id"]},
            {"$inc": {"stock": -qty}}
        )

    # ---------------- CREATE ORDER ----------------
    order = {
        "user_id": current_user.id,
        "items": order_items,
        "total_amount": total,
        "address": address,
        "payment_method": payment_method,
        "status": "Order Placed",
        "created_at": datetime.utcnow()
    }

    # ---------------- UPI ----------------
    if payment_method == "upi":
        upi_ref = request.form.get("upi_ref")

        if not upi_ref:
            return "UPI Reference ID required", 400

        order["upi_ref"] = upi_ref
        order["status"] = "Payment Submitted"

    # ---------------- COD ----------------
    elif payment_method == "cod":
        order["status"] = "Cash on Delivery"

    mongo.db.orders.insert_one(order)

    # ---------------- CLEANUP ----------------
    if source == "buy_now":
        session.pop("buy_now", None)
    else:
        mongo.db.carts.delete_one({"user_id": current_user.id})

    return redirect(url_for("orders.order_history"))

# -------------------------------------------------
# ORDER HISTORY
# -------------------------------------------------
@orders.route("/orders")
@login_required
def order_history():
    user_orders = list(
        mongo.db.orders.find({"user_id": current_user.id})
        .sort("created_at", -1)
    )
    return render_template("order_history.html", orders=user_orders)


# -------------------------------------------------
# CANCEL ORDER
# -------------------------------------------------
@orders.route("/orders/cancel/<order_id>", methods=["POST"])
@login_required
def cancel_order(order_id):
    order = mongo.db.orders.find_one({
        "_id": ObjectId(order_id),
        "user_id": current_user.id
    })

    if not order:
        return redirect(url_for("orders.order_history"))

    cancellable_statuses = [
        "Order Placed",
        "Payment Submitted",
        "Payment Verified",
        "Packed",
        "Cash on Delivery"
    ]

    if order.get("status") not in cancellable_statuses:
        return redirect(url_for("orders.order_history"))

    mongo.db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {
            "status": "Cancelled",
            "cancelled_at": datetime.utcnow()
        }}
    )

    return redirect(url_for("orders.order_history"))
