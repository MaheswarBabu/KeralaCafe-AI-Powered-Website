"""
email_service.py
-----------------
Sends order/reservation notification emails via SMTP.

Configure with environment variables:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL

If SMTP isn't configured, emails are printed to the console instead of
sent (a "dry run") so the rest of the app keeps working during local
development/testing without needing real email credentials.
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "no-reply@keralacafe.local")
FROM_NAME = os.getenv("FROM_NAME", "Kerala Cafe")


def _send(to_email: str, subject: str, body: str) -> bool:
    if not to_email:
        return False

    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        try:
            print(f"\n----- [email dry-run: SMTP not configured] -----")
            print(f"To: {to_email}\nSubject: {subject}\n\n{body}")
            print("--------------------------------------------------\n")
        except UnicodeEncodeError:
            safe_body = body.encode("ascii", errors="replace").decode("ascii")
            safe_subject = subject.encode("ascii", errors="replace").decode("ascii")
            print(f"To: {to_email}\nSubject: {safe_subject}\n\n{safe_body}")
            print("--------------------------------------------------\n")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to_email

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[email_service] Failed to send email to {to_email}: {e}")
        return False


def order_code(order_id: int) -> str:
    return f"KC{1000 + order_id}"


def send_order_confirmation(order) -> bool:
    items_lines = "\n".join(
        f"  - {i.food.food_name if i.food else 'Item'} x{i.quantity} - ₹{i.price * i.quantity}"
        for i in order.items
    )
    body = f"""Hi {order.customer_name},

Thanks for your order at Kerala Cafe! Here's your confirmation:

Order #{order_code(order.order_id)}
{items_lines}

Total: ₹{order.total_amount}
Payment: {order.payment_method.upper()}
Delivery Address: {order.address}

We'll notify you as your order moves through preparation and delivery.
You can track it any time at /profile.

- Kerala Cafe
"""
    return _send(order.email, f"Kerala Cafe Order Confirmed - #{order_code(order.order_id)}", body)


def send_order_cancellation(order, reason: str = "") -> bool:
    reason_block = f"\nReason: {reason}\n" if reason else ""
    body = f"""Hi {order.customer_name},

Your order #{order_code(order.order_id)} has been cancelled.
{reason_block}
If you didn't request this or have any questions, please contact the
restaurant directly.

- Kerala Cafe
"""
    return _send(order.email, f"Kerala Cafe Order Cancelled - #{order_code(order.order_id)}", body)


def send_order_change_request(order, message: str) -> bool:
    body = f"""Hi {order.customer_name},

We need to let you know about a change regarding your order
#{order_code(order.order_id)}:

"{message}"

Please reply to this email or call the restaurant so we can confirm
how you'd like to proceed. We'll hold your order in the meantime.

- Kerala Cafe
"""
    return _send(order.email, f"Action Needed - Order #{order_code(order.order_id)}", body)


def send_reservation_confirmation(reservation) -> bool:
    body = f"""Hi {reservation.customer_name},

Your table reservation is confirmed!

Reservation #{reservation.reservation_id}
Date: {reservation.reservation_date}
Time: {reservation.reservation_time}
Guests: {reservation.guests}

See you soon!
- Kerala Cafe
"""
    return _send(reservation.email, f"Kerala Cafe Reservation Confirmed - #{reservation.reservation_id}", body)


def send_reservation_cancellation(reservation, reason: str = "") -> bool:
    reason_block = f"\nReason: {reason}\n" if reason else ""
    body = f"""Hi {reservation.customer_name},

Your reservation #{reservation.reservation_id} for {reservation.reservation_date}
at {reservation.reservation_time} has been cancelled.
{reason_block}
If you didn't request this or have any questions, please contact the
restaurant directly.

- Kerala Cafe
"""
    return _send(reservation.email, f"Kerala Cafe Reservation Cancelled - #{reservation.reservation_id}", body)

