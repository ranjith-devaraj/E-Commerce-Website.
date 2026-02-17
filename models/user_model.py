from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, data):
        self.id = str(data["_id"])
        self.name = data.get("name")
        self.email = data.get("email")
        self.role = data.get("role", "user")

    @staticmethod
    def create_user(name, email, password=None, google_id=None, role="user"):
        return {
            "name": name,
            "email": email,
            "password": password,        # hashed password
            "google_id": google_id,
            "role": role
        }
