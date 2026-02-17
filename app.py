import os
from flask import Flask
from config import Config
from extensions import mongo, bcrypt, login_manager

# Blueprints
from routes.auth import auth
from routes.shop import shop
from routes.cart import cart
from routes.orders import orders
from routes.payments import payments
from routes.admin import admin
from routes.auth import auth
from routes.notifications import notifications

# Models
from models.user_model import User

from bson.objectid import ObjectId

#helper 
from utils.helpers import product_image
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # ONLY FOR DEVELOPMENT

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    

    # Initialize extensions
    mongo.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # ✅ Auto-create admin if not exists
    ensure_admin(app)

    # Register blueprints
    app.register_blueprint(auth)
    app.register_blueprint(shop)
    app.register_blueprint(cart)
    app.register_blueprint(orders)
    app.register_blueprint(payments)
    app.register_blueprint(notifications)
    app.register_blueprint(admin, url_prefix="/admin")
    

    return app


def ensure_admin(app):
    """
    Creates a single admin account on startup
    if it does not already exist.
    """
    with app.app_context():
        admin = mongo.db.users.find_one({"role": "admin"})

        if not admin:
            mongo.db.users.insert_one({
                "name": "Admin",
                "email": app.config.get("ADMIN_EMAIL"),
                "password": app.config.get("ADMIN_PASSWORD_HASH"),
                "role": "admin"
            })
            print("✅ Admin account created")
        else:
            print("ℹ️ Admin account already exists")

        # CREATE FINANCE USER IF NOT EXISTS
        finance = mongo.db.users.find_one({"email": "finance@example.com"})
        if not finance:
            mongo.db.users.insert_one({
                "name": "Finance",
                "email": "finance@example.com",
                "password": app.config.get("FINANCE_PASSWORD_HASH"),
                "role": "finance"
            })
            print("✅ Finance account created")
        else:
            print("ℹ️ Finance account already exists")



@login_manager.user_loader
def load_user(user_id):
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    return User(user) if user else None





if __name__ == "__main__":
    app = create_app()
    #port = int(os.environ.get("PORT", 8000))
    #app.run(host="0.0.0.0", port=port, debug=True)
    app.run(debug=True)