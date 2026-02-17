import smtplib
from email.message import EmailMessage
from flask import current_app


def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg["From"] = current_app.config["SMTP_EMAIL"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(
                current_app.config["SMTP_EMAIL"],
                current_app.config["SMTP_PASSWORD"]
            )
            smtp.send_message(msg)
    except Exception as e:
        print("Email error:", e)
