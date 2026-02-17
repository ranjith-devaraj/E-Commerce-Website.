from datetime import datetime

class Product:
    @staticmethod
    def create_product(
        name,
        description,
        price,
        category,
        stock,
        image_url
    ):
        return {
            "name": name,
            "description": description,
            "price": float(price),
            "category": category,
            "stock": int(stock),
            "image": image_url,
            "created_at": datetime.utcnow()
        }
