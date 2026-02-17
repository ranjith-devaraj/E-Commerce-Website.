from itertools import product
from flask import Blueprint, render_template, redirect, request, url_for, make_response
from flask_login import login_required
from extensions import mongo
from utils.decorators import admin_required, roles_required
from services.image_service import save_image
from models.product_model import Product
from bson.objectid import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.units import inch
import io
import json
import os
import uuid

admin = Blueprint("admin", __name__)

# ================= MULTI IMAGE HELPER =================
def save_multiple_images(files, limit=5):
    images = []
    for file in files[:limit]:
        if file and file.filename:
            filename = save_image(file)
            images.append(filename)
    return images


# ================= DASHBOARD =================
@admin.route("/dashboard")
@login_required
@roles_required("admin", "finance")  # Only finance role can access dashboard
def dashboard():

    # ---------- BASIC COUNTS ----------
    total_orders = mongo.db.orders.count_documents({})

    pending_payments = mongo.db.orders.count_documents({
        "$or": [
            {
                "payment_method": "upi",
                "payment_status": {"$in": [None, "PENDING"]}
            },
            {
                "payment_method": "cod",
                "status": "Order Placed"
            }
        ]
    })

    # ---------- TOTAL REVENUE ----------
    revenue_cursor = mongo.db.orders.aggregate([
        {
            "$match": {
                "status": {
                    "$in": [
                        "Payment Verified",
                        "Packed",
                        "Shipped",
                        "Out for Delivery",
                        "Delivered",
                        "Cash on Delivery"
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "total_revenue": {"$sum": "$total_amount"}
            }
        }
    ])

    revenue_data = list(revenue_cursor)
    total_revenue = revenue_data[0]["total_revenue"] if revenue_data else 0

    # ---------- SALES ANALYTICS ----------
    delivered_count = mongo.db.orders.count_documents({"status": "Delivered"})
    cancelled_count = mongo.db.orders.count_documents({"status": "Cancelled"})

    return render_template(
        "admin/dashboard.html",
        total_orders=total_orders,
        pending_payments=pending_payments,
        total_revenue=total_revenue,
        delivered_count=delivered_count,
        cancelled_count=cancelled_count
    )
# ================= ANALYTICS =================
@admin.route("/analytics")
@login_required
@roles_required("admin", "finance")
def analytics():
    selected_product = request.args.get("product_id")

    products = list(mongo.db.products.find())

    analytics = None

    if selected_product:
        orders = mongo.db.orders.find({
            "items.product_id": selected_product
        })

        sold_qty = 0
        delivered = 0
        cancelled = 0

        for order in orders:
            for item in order["items"]:
                if item["product_id"] == selected_product:
                    sold_qty += item["qty"]

            if order["status"] == "Delivered":
                delivered += 1
            elif order["status"] == "Cancelled":
                cancelled += 1

        analytics = {
            "sold_qty": sold_qty,
            "delivered": delivered,
            "cancelled": cancelled
        }

    return render_template(
        "admin/analytics.html",
        products=products,
        analytics=analytics,
        selected_product=selected_product
    )
# ================= DOWNLOAD ANALYTICS PDF =================
@admin.route("/analytics/download")
@login_required
@roles_required("admin", "finance")
def download_analytics_report():

    product_id = request.args.get("product_id")
    if not product_id:
        return redirect(url_for("admin.analytics"))

    product = mongo.db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        return redirect(url_for("admin.analytics"))

    # ---------------- ANALYTICS ----------------
    orders = mongo.db.orders.find({
        "items.product_id": str(product["_id"])
    })

    sold_qty = 0
    delivered = 0
    cancelled = 0

    for order in orders:
        for item in order["items"]:
            if item["product_id"] == str(product["_id"]):
                sold_qty += item["qty"]

        if order["status"] == "Delivered":
            delivered += 1
        elif order["status"] == "Cancelled":
            cancelled += 1

    # ---------------- PDF GENERATION ----------------
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, y, "Product Analytics Report")
    y -= 40

    pdf.setFont("Helvetica", 12)
    pdf.drawString(40, y, f"Product Name: {product['name']}")
    y -= 25

    pdf.drawString(40, y, f"Total Units Sold: {sold_qty}")
    y -= 20

    pdf.drawString(40, y, f"Delivered Orders: {delivered}")
    y -= 20

    pdf.drawString(40, y, f"Cancelled Orders: {cancelled}")
    y -= 30

    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawString(40, y, "Generated by Admin Analytics")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=analytics_{product['name']}.pdf"
    )

    return response



# ================= PRODUCTS =================
@admin.route("/products", methods=["GET", "POST"])
@login_required# Only admin can manage products
@roles_required("admin", "finance")  
def products():
    if request.method == "POST":
        images = request.files.getlist("images")
        image_list = save_multiple_images(images, 5)

        # ===== OFFER LOGIC (FIXED) =====
        is_offer = True if request.form.get("is_offer") else False

        offer_price_raw = request.form.get("offer_price")
        offer_price = float(offer_price_raw) if (is_offer and offer_price_raw) else None

        # ===== CREATE PRODUCT =====
        product = Product.create_product(
            name=request.form.get("name"),
            description=request.form.get("description"),
            price=float(request.form.get("price")),
            category=request.form.get("category"),
            stock=int(request.form.get("stock")),
            image_url=image_list[0] if image_list else None
        )

        # ===== ADD IMAGES & OFFER FIELDS =====
        product["images"] = image_list
        product["is_offer"] = is_offer
        product["offer_price"] = offer_price

        mongo.db.products.insert_one(product)

        return redirect(url_for("admin.products"))

    products = list(mongo.db.products.find())
    return render_template("admin/products.html", products=products)

# ================= EDIT PRODUCT =================
@admin.route("/products/edit/<product_id>", methods=["GET", "POST"])
@login_required
@admin_required  # Only admin can manage products
@roles_required("admin", "finance") 
def edit_product(product_id):
    try:
        product = mongo.db.products.find_one({"_id": ObjectId(product_id)})
    except InvalidId:
        return redirect(url_for("admin.products"))

    if not product:
        return redirect(url_for("admin.products"))

    # ================= POST =================
    if request.method == "POST":

        # ================= BASIC FIELDS =================
        update_data = {
            "name": request.form.get("name"),
            "description": request.form.get("description"),
            "price": float(request.form.get("price")),
            "category": request.form.get("category"),
            "stock": int(request.form.get("stock")),
        }

        # ================= OFFER LOGIC =================
        is_offer = True if request.form.get("is_offer") else False
        offer_price_raw = request.form.get("offer_price")

        update_data["is_offer"] = is_offer
        update_data["offer_price"] = (
            float(offer_price_raw) if is_offer and offer_price_raw else None
        )

        # 🔔 NOTIFICATION LOGIC ✅ (FIXED LOCATION)
        if is_offer and not product.get("is_offer"):
            users = mongo.db.users.find({"role": "user"})
            for user in users:
                mongo.db.notifications.insert_one({
                "user_id": str(user["_id"]),
                "title": "🔥 New Offer Available",
                "message": f"{product['name']} is now on offer!",
                "product_id": str(product["_id"]),
                "is_read": False,
                "created_at": datetime.utcnow()
        })


        # ================= EXISTING IMAGES =================
        images = product.get("images", [])

        removed_images = request.form.get("removed_images")
        if removed_images:
            removed_images = json.loads(removed_images)

            for img in removed_images:
                img_path = os.path.join("static", "uploads", img)
                if os.path.exists(img_path):
                    os.remove(img_path)

            images = [img for img in images if img not in removed_images]

        # ================= NEW IMAGES =================
        new_images = request.files.getlist("images")
        saved_images = save_multiple_images(new_images, 5)

        images.extend(saved_images)

        update_data["images"] = images
        update_data["image_url"] = images[0] if images else None

        # ================= UPDATE DB =================
        mongo.db.products.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": update_data}
        )

        return redirect(url_for("admin.products"))

    # ================= GET =================
    return render_template("admin/edit_product.html", product=product)


# ================= DELETE PRODUCT =================
@admin.route("/products/delete/<product_id>")
@login_required
@roles_required("admin", "finance") 
def delete_product(product_id):
    try:
        mongo.db.products.delete_one({"_id": ObjectId(product_id)})
    except InvalidId:
        pass
    return redirect(url_for("admin.products"))


# ================= PAYMENTS =================
@admin.route("/payments")
@login_required
@roles_required("admin", "finance") 
def payments():
    pending = mongo.db.orders.find({
        "payment_method": "upi",
        "payment_status": {"$in": [None, "PENDING"]}
    }).sort("created_at", -1)

    processed = mongo.db.orders.find({
        "payment_method": "upi",
        "payment_status": {"$in": ["VERIFIED", "REJECTED"]}
    }).sort("created_at", -1)

    cod_orders = mongo.db.orders.find({
    "payment_method": "cod",
    "status": {"$in": ["Cash on Delivery", "Order Placed", "Packed"]}
}).sort("created_at", -1)


    return render_template(
        "admin/payments.html",
        payments=list(pending),
        processed_payments=list(processed),
        cod_orders=list(cod_orders)
    )


@admin.route("/payments/verify", methods=["POST"])
@login_required
@roles_required("admin", "finance")
def verify_payment_action():
    order_id = request.form.get("order_id")
    action = request.form.get("action")

    if action == "verify":
        mongo.db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"payment_status": "VERIFIED", "status": "Packed"}}
        )

    elif action == "reject":
        mongo.db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {
                "$set": {
                    "payment_status": "REJECTED",
                    "status": "Cancelled",
                    "cancelled_at": datetime.utcnow()
                }
            }
        )

    return redirect(url_for("admin.payments"))


# ================= ORDERS =================
@admin.route("/orders")
@login_required
@roles_required("admin", "finance")
def admin_orders():
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)

    orders = mongo.db.orders.find({
        "$or": [
            {"status": {"$ne": "Cancelled"}},
            {"status": "Cancelled", "cancelled_at": {"$lte": cutoff}}
        ]
    }).sort("created_at", -1)

    return render_template("admin/orders.html", orders=list(orders))


@admin.route("/orders/update-status", methods=["POST"])
@login_required
@roles_required("admin", "finance")
def update_order_status():
    mongo.db.orders.update_one(
        {"_id": ObjectId(request.form.get("order_id"))},
        {"$set": {"status": request.form.get("status")}}
    )
    return redirect(
        url_for("admin.view_order",
                order_id=request.form.get("order_id"))
    )


@admin.route("/orders/view/<order_id>")
@login_required
@roles_required("admin", "finance")
def view_order(order_id):
    try:
        order = mongo.db.orders.find_one({"_id": ObjectId(order_id)})
    except InvalidId:
        return redirect(url_for("admin.admin_orders"))

    if not order:
        return redirect(url_for("admin.admin_orders"))

    return render_template("admin/order_view.html", order=order)


# ================= PRINT ORDER =================
@admin.route("/orders/print/<order_id>")
@login_required
@roles_required("admin", "finance")
def print_order(order_id):
    order = mongo.db.orders.find_one({"_id": ObjectId(order_id)})
    if not order:
        return redirect(url_for("admin.admin_orders"))

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    styles = getSampleStyleSheet()
    y = height - 50

    # ================= LOGO =================
    logo_path = "static/images/logo.webp"
    if os.path.exists(logo_path):
        pdf.drawImage(logo_path, 40, y - 40, width=90, height=60, mask="auto")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(150, y - 20, "ORDER INVOICE")
    y -= 80

    # ================= TABLE HEADER =================
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, y, "Product")
    pdf.drawString(360, y, "Qty")
    pdf.drawRightString(width - 40, y, "Amount")
    y -= 15

    pdf.line(40, y, width - 40, y)
    y -= 15

    pdf.setFont("Helvetica", 10)

    # ================= ITEMS =================
    for item in order.get("items", []):

        # Page break safety
        if y < 120:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 10)

        # 🔹 Product name (wrapped)
        p = Paragraph(item["name"], styles["Normal"])
        w, h = p.wrap(300, y)
        p.drawOn(pdf, 40, y - h)

        # 🔹 Qty
        pdf.drawString(370, y - 12, str(item["qty"]))

        # 🔹 Price
        pdf.drawRightString(
            width - 40,
            y - 12,
            f"Rs/- {item['item_total']}"
        )

        y -= h + 12

    # ================= TOTAL =================
    y -= 10
    pdf.line(40, y, width - 40, y)
    y -= 20

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(
        width - 40,
        y,
        f"Total Amount: Rs/- {order.get('total_amount')}"
    )

    # ================= ADDRESS =================
    y -= 40
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, "Delivery Address")
    y -= 16

    pdf.setFont("Helvetica", 10)
    address = order.get("address")

    if isinstance(address, dict):
        for v in address.values():
            pdf.drawString(40, y, str(v))
            y -= 14
    elif address:
        pdf.drawString(40, y, str(address))

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=order_{order_id}.pdf"
    return response


# =====================================================
# BANNERS (ADMIN ONLY)
# =====================================================
@admin.route("/banners", methods=["GET", "POST"])
@login_required
@roles_required("admin", "finance")
def banners():
    if request.method == "POST":
        image = request.files.get("image")
        title = request.form.get("title")
        link = request.form.get("link")

        if not image or not image.filename:
            return redirect(url_for("admin.banners"))

        if mongo.db.banners.count_documents({}) >= 7:
            return redirect(url_for("admin.banners"))

        ext = os.path.splitext(image.filename)[1]
        filename = f"{uuid.uuid4().hex}{ext}"

        folder = os.path.join("static", "banners")
        os.makedirs(folder, exist_ok=True)
        image.save(os.path.join(folder, filename))

        mongo.db.banners.insert_one({
            "image": f"/static/banners/{filename}",
            "title": title,
            "link": link,
            "created_at": datetime.utcnow()
        })

        return redirect(url_for("admin.banners"))

    banners = list(mongo.db.banners.find().sort("created_at", -1))
    return render_template("admin/banners.html", banners=banners)


@admin.route("/banners/delete/<banner_id>", methods=["POST"])
@login_required
@roles_required("admin", "finance")
def delete_banner(banner_id):
    try:
        banner = mongo.db.banners.find_one({"_id": ObjectId(banner_id)})
    except InvalidId:
        return redirect(url_for("admin.banners"))

    if banner:
        path = banner["image"].lstrip("/")
        if os.path.exists(path):
            os.remove(path)
        mongo.db.banners.delete_one({"_id": ObjectId(banner_id)})

    return redirect(url_for("admin.banners"))

#====notification center============

def notify_users_for_offer(product):
    users = mongo.db.users.find({"role": "user"})

    for user in users:
        # check if product exists in user's cart
        cart = mongo.db.carts.find_one({"user_id": user["_id"]})

        in_cart = False
        if cart:
            in_cart = any(
                str(item["product_id"]) == str(product["_id"])
                for item in cart.get("items", [])
            )

        mongo.db.notifications.insert_one({
            "user_id": user["_id"],
            "title": "🔥 Product on Offer!",
            "message": (
                f"{product['name']} is now on OFFER!"
                + (" (Already in your cart 🛒)" if in_cart else "")
            ),
            "product_id": product["_id"],
            "is_read": False,
            "created_at": datetime.utcnow()
        })

# ================= UPI SETTINGS =================
@admin.route("/upi-settings", methods=["GET", "POST"])
@login_required
@roles_required("admin", "finance")
def upi_settings():

    if request.method == "POST":
        upi_id = request.form.get("upi_id")
        shop_name = request.form.get("shop_name")

        mongo.db.settings.update_one(
            {"_id": "upi_settings"},
            {
                "$set": {
                    "upi_id": upi_id,
                    "shop_name": shop_name,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        return redirect(url_for("admin.upi_settings"))

    settings = mongo.db.settings.find_one({"_id": "upi_settings"})

    return render_template(
        "admin/upi_settings.html",
        settings=settings
    )
