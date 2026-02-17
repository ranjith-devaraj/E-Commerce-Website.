from datetime import datetime

class Payment:
    @staticmethod
    def create_payment(user_id, order_id, upi_ref, app_name):
        return {
            "user_id": user_id,
            "order_id": order_id,
            "upi_ref": upi_ref,
            "app": app_name,
            "status": "Payment Submitted",
            "created_at": datetime.utcnow()
        }
