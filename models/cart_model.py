class Cart:
    @staticmethod
    def create_cart(user_id):
        return {
            "user_id": user_id,
            "items": []
        }

    @staticmethod
    def cart_item(product_id, qty=1):
        return {
            "product_id": product_id,
            "qty": int(qty)
        }
