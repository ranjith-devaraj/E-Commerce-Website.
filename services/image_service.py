import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(image, folder="uploads"):
    if not image or not image.filename:
        return None

    filename = secure_filename(image.filename)
    ext = filename.rsplit(".", 1)[-1]

    unique_name = f"{uuid.uuid4().hex}.{ext}"

    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        folder
    )

    os.makedirs(upload_folder, exist_ok=True)

    image_path = os.path.join(upload_folder, unique_name)
    image.save(image_path)

    # 🔥 RETURN RELATIVE PATH (used everywhere)
    return f"/static/{folder}/{unique_name}"
