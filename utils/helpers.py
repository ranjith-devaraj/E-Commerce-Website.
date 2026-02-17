from bson.objectid import ObjectId
from flask import url_for


def str_to_object_id(id_str):
    try:
        return ObjectId(id_str)
    except Exception:
        return None

def product_image(image):
    if not image:
        return url_for("static", filename="images/default_product.png")

    if image.startswith("http"):
        return image  # external images

    return url_for("static", filename=f"uploads/{image}")


def calculate_cart_total(cart_items, products_collection):
    total = 0
    detailed_items = []

    for item in cart_items:
        product = products_collection.find_one(
            {"_id": ObjectId(item["product_id"])}
        )
        if product:
            subtotal = product["price"] * item["qty"]
            total += subtotal
            detailed_items.append({
                "product": product,
                "qty": item["qty"],
                "subtotal": subtotal
            })

    return total, detailed_items
