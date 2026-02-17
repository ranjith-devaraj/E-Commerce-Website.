from datetime import datetime

class Order:
    @staticmethod
    def create_order(user_id, items, total_amount):
        return {
            "user_id": user_id,
            "items": items,
            "total_amount": float(total_amount),
            "status": "Payment Submitted",
            "created_at": datetime.utcnow()
        }
