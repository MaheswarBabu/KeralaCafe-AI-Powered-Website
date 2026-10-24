"""
app.py
------
TasteHub Smart Restaurant Platform - FastAPI backend.

Run with:
    python seed.py          # once, to create + populate the DB
    uvicorn app:app --reload

Then open http://127.0.0.1:8000
Default admin login (change after first run): see seed.py output.
"""

import os
import uuid
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Request, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from database import engine, Base, get_db
import models
import schemas
import ai_service
import auth
import email_service
import tts_service

Base.metadata.create_all(bind=engine)

UPLOAD_DIR = "static/images/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Kerala Cafe - Smart Restaurant Platform")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me-in-production"))

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def order_code(order_id: int) -> str:
    """Display-friendly order code, e.g. 24 -> KC1024."""
    return f"KC{1000 + order_id}"


def render(request: Request, template_name: str, db: Session, extra: Optional[dict] = None):
    """TemplateResponse wrapper that always makes current_user available to templates."""
    ctx = dict(extra or {})
    ctx["current_user"] = auth.get_current_user(request, db)
    return templates.TemplateResponse(request, template_name, ctx)


def _save_upload(image_file: Optional[UploadFile]) -> Optional[str]:
    if not image_file or not image_file.filename:
        return None
    ext = os.path.splitext(image_file.filename)[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, filename)
    with open(dest_path, "wb") as f:
        f.write(image_file.file.read())
    return f"/{dest_path}"


# =====================================================================
# PAGE ROUTES (server-rendered HTML via Jinja2)
# =====================================================================

@app.get("/")
def home_page(request: Request, db: Session = Depends(get_db)):
    specials = db.query(models.Food).filter(models.Food.availability == True).order_by(models.Food.rating.desc()).limit(3).all()  # noqa: E712
    return render(request, "home.html", db, {"specials": specials})


@app.get("/menu")
def menu_page(request: Request, db: Session = Depends(get_db)):
    foods = db.query(models.Food).all()
    categories = sorted({f.category for f in foods})
    return render(request, "menu.html", db, {"foods": foods, "categories": categories})


@app.get("/reserve")
def reserve_page(request: Request, db: Session = Depends(get_db)):
    # Browsable without login - only confirming a reservation requires it.
    user = auth.get_current_user(request, db)
    return render(request, "reservation.html", db, {"user": user})


@app.get("/order")
def order_page_redirect():
    # The standalone "Order Online" page was merged into /menu (cart sidebar
    # + "Proceed to Checkout" live right there now). Kept as a redirect so
    # any old bookmarks/links still work.
    return RedirectResponse(url="/menu", status_code=303)


@app.get("/checkout")
def checkout_page(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login?next=/checkout", status_code=303)
    return render(request, "checkout.html", db, {"user": user})


@app.get("/profile")
def profile_page(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(request, db)
    return render(request, "profile.html", db, {"user": user})


@app.get("/orders")
def orders_page_redirect():
    return RedirectResponse(url="/profile", status_code=303)


@app.get("/ai-assistant")
def ai_assistant_page(request: Request, db: Session = Depends(get_db)):
    categories = sorted({f.category for f in db.query(models.Food).filter(models.Food.availability == True).all()})  # noqa: E712
    return render(request, "ai_assistant.html", db, {"categories": categories})


# ---------------------- Auth pages ----------------------

@app.get("/login")
def login_page(request: Request, next: str = "/", db: Session = Depends(get_db)):
    if auth.get_current_user(request, db):
        return RedirectResponse(url=next, status_code=303)
    return render(request, "login.html", db, {"next": next})


@app.get("/register")
def register_page(request: Request, next: str = "/", db: Session = Depends(get_db)):
    if auth.get_current_user(request, db):
        return RedirectResponse(url=next, status_code=303)
    return render(request, "register.html", db, {"next": next})


@app.get("/logout")
def logout_page(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


# ---------------------- Admin pages ----------------------

@app.get("/admin")
def admin_home(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/admin/orders", status_code=303)


@app.get("/admin/orders")
def admin_orders_page(request: Request, db: Session = Depends(get_db)):
    admin = auth.get_current_user(request, db)
    if not admin:
        return RedirectResponse(url="/login?next=/admin/orders", status_code=303)
    if not admin.is_admin:
        raise HTTPException(status_code=403, detail="Admin access only.")
    orders = db.query(models.Order).order_by(models.Order.order_date.desc()).all()
    return render(request, "admin_orders.html", db, {"orders": orders, "order_code": order_code})


@app.get("/admin/reservations")
def admin_reservations_page(request: Request, db: Session = Depends(get_db)):
    admin = auth.get_current_user(request, db)
    if not admin:
        return RedirectResponse(url="/login?next=/admin/reservations", status_code=303)
    if not admin.is_admin:
        raise HTTPException(status_code=403, detail="Admin access only.")
    reservations = db.query(models.Reservation).order_by(models.Reservation.created_at.desc()).all()
    return render(request, "admin_reservations.html", db, {"reservations": reservations})


@app.get("/admin/menu")
def admin_menu_page(request: Request, db: Session = Depends(get_db)):
    admin = auth.get_current_user(request, db)
    if not admin:
        return RedirectResponse(url="/login?next=/admin/menu", status_code=303)
    if not admin.is_admin:
        raise HTTPException(status_code=403, detail="Admin access only.")
    foods = db.query(models.Food).order_by(models.Food.food_id).all()
    return render(request, "admin_menu.html", db, {"foods": foods})


# =====================================================================
# AUTH API
# =====================================================================

@app.post("/api/auth/register")
def register(payload: schemas.RegisterRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(
        or_(models.User.email == payload.email, models.User.phone == payload.phone)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with that email or phone already exists.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    user = models.User(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=auth.hash_password(payload.password),
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.user_id
    return {"user_id": user.user_id, "name": user.name, "is_admin": user.is_admin}


@app.post("/api/auth/login")
def login(payload: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        or_(models.User.email == payload.identifier, models.User.phone == payload.identifier)
    ).first()
    if not user or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email/phone or password.")

    request.session["user_id"] = user.user_id
    return {"user_id": user.user_id, "name": user.name, "is_admin": user.is_admin}


@app.post("/api/auth/logout")
def logout_api(request: Request):
    request.session.clear()
    return {"ok": True}


# =====================================================================
# API ROUTES
# =====================================================================

# ---------------------- Foods ----------------------

@app.get("/api/foods", response_model=List[schemas.FoodOut])
def list_foods(
    category: Optional[str] = None,
    is_veg: Optional[bool] = None,
    max_price: Optional[float] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Food)
    if category:
        q = q.filter(models.Food.category == category)
    if is_veg is not None:
        q = q.filter(models.Food.is_veg == is_veg)
    if max_price is not None:
        q = q.filter(models.Food.price <= max_price)
    if search:
        q = q.filter(models.Food.food_name.ilike(f"%{search}%"))
    return q.all()


@app.get("/api/foods/{food_id}", response_model=schemas.FoodOut)
def get_food(food_id: int, db: Session = Depends(get_db)):
    food = db.query(models.Food).filter(models.Food.food_id == food_id).first()
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")
    return food


# ---------------------- Table Reservation ----------------------

@app.get("/api/tables/availability")
def check_availability(date: str, time: str, guests: int, db: Session = Depends(get_db)):
    """
    Returns the first free table that fits the party size and isn't
    already booked for that date + time slot.
    """
    booked_table_ids = {
        r.table_id for r in db.query(models.Reservation).filter(
            and_(
                models.Reservation.reservation_date == date,
                models.Reservation.reservation_time == time,
                models.Reservation.status == "confirmed",
            )
        ) if r.table_id
    }

    candidate = (
        db.query(models.RestaurantTable)
        .filter(models.RestaurantTable.capacity >= guests)
        .filter(~models.RestaurantTable.table_id.in_(booked_table_ids) if booked_table_ids else True)
        .order_by(models.RestaurantTable.capacity.asc())
        .first()
    )

    if not candidate:
        return {"available": False, "message": "No tables available for that date, time and party size."}

    return {
        "available": True,
        "table_id": candidate.table_id,
        "table_number": candidate.table_number,
        "capacity": candidate.capacity,
    }


@app.post("/api/reservations", response_model=schemas.ReservationOut)
def create_reservation(payload: schemas.ReservationCreate, request: Request, db: Session = Depends(get_db)):
    current_user = auth.get_current_user(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Please log in to reserve a table.")

    table_id = payload.table_id
    if table_id is None:
        avail = check_availability(payload.reservation_date, payload.reservation_time, payload.guests, db)
        if not avail["available"]:
            raise HTTPException(status_code=409, detail="No tables available for that slot.")
        table_id = avail["table_id"]

    reservation = models.Reservation(
        user_id=current_user.user_id,
        customer_name=payload.customer_name,
        phone=payload.phone,
        email=payload.email or current_user.email,
        reservation_date=payload.reservation_date,
        reservation_time=payload.reservation_time,
        guests=payload.guests,
        special_request=payload.special_request or "",
        table_id=table_id,
        status="confirmed",
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    email_service.send_reservation_confirmation(reservation)
    return reservation


def _serialize_reservation(r: models.Reservation):
    return {
        "reservation_id": r.reservation_id,
        "customer_name": r.customer_name,
        "phone": r.phone,
        "email": r.email,
        "reservation_date": r.reservation_date,
        "reservation_time": r.reservation_time,
        "guests": r.guests,
        "special_request": r.special_request,
        "table_id": r.table_id,
        "table_number": r.table.table_number if r.table else None,
        "status": r.status,
        "admin_note": r.admin_note,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@app.get("/api/reservations/mine")
def get_my_reservations(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in to view your reservations.")
    reservations = db.query(models.Reservation).filter(
        or_(models.Reservation.user_id == user.user_id, models.Reservation.phone == user.phone)
    ).order_by(models.Reservation.created_at.desc()).all()
    return [_serialize_reservation(r) for r in reservations]


@app.get("/api/reservations/phone/{phone}")
def get_reservations_by_phone(phone: str, db: Session = Depends(get_db)):
    reservations = db.query(models.Reservation).filter(models.Reservation.phone == phone).order_by(models.Reservation.created_at.desc()).all()
    if not reservations:
        raise HTTPException(status_code=404, detail="No reservations found for this phone number.")
    return [_serialize_reservation(r) for r in reservations]


@app.post("/api/reservations/{reservation_id}/cancel")
def cancel_reservation_api(reservation_id: int, request: Request, db: Session = Depends(get_db)):
    reservation = db.query(models.Reservation).filter(models.Reservation.reservation_id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    current_user = auth.get_current_user(request, db)
    if current_user and reservation.user_id and reservation.user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to cancel this reservation.")

    if reservation.status == "cancelled":
        return {"ok": True, "message": "Reservation is already cancelled", "status": "cancelled"}

    reservation.status = "cancelled"
    db.commit()
    db.refresh(reservation)

    try:
        email_service.send_reservation_cancellation(reservation, "Cancelled by customer")
    except Exception as e:
        print(f"[email_service] Error sending cancellation email: {e}")

    return {"ok": True, "message": "Reservation cancelled successfully", "status": "cancelled"}


@app.get("/api/reservations/{reservation_id}", response_model=schemas.ReservationOut)
def get_reservation(reservation_id: int, db: Session = Depends(get_db)):
    r = db.query(models.Reservation).filter(models.Reservation.reservation_id == reservation_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return r


# ---------------------- Online Ordering ----------------------

@app.post("/api/orders")
def create_order(payload: schemas.OrderCreate, request: Request, db: Session = Depends(get_db)):
    current_user = auth.get_current_user(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Please log in to place an order.")

    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty.")

    total = 0.0
    line_items = []
    for item in payload.items:
        food = db.query(models.Food).filter(models.Food.food_id == item.food_id).first()
        if not food or not food.availability:
            raise HTTPException(status_code=400, detail=f"Item {item.food_id} is unavailable.")
        total += food.price * item.quantity
        line_items.append((food, item.quantity))

    delivery_fee = 40.0
    total += delivery_fee

    order = models.Order(
        user_id=current_user.user_id,
        customer_name=payload.customer_name,
        phone=payload.phone,
        email=payload.email or current_user.email,
        address=payload.address,
        landmark=payload.landmark or "",
        delivery_instructions=payload.delivery_instructions or "",
        payment_method=payload.payment_method,
        total_amount=total,
        status="Order Placed",
    )
    db.add(order)
    db.flush()  # get order.order_id before commit

    for food, qty in line_items:
        db.add(models.OrderItem(order_id=order.order_id, food_id=food.food_id, quantity=qty, price=food.price))

    db.commit()
    db.refresh(order)

    email_service.send_order_confirmation(order)

    return {
        "order_id": order.order_id,
        "order_code": order_code(order.order_id),
        "total_amount": order.total_amount,
        "status": order.status,
        "payment_method": order.payment_method,
    }


def _serialize_order(order: models.Order):
    return {
        "order_id": order.order_id,
        "order_code": order_code(order.order_id),
        "customer_name": order.customer_name,
        "phone": order.phone,
        "address": order.address,
        "total_amount": order.total_amount,
        "status": order.status,
        "admin_note": order.admin_note,
        "order_date": order.order_date.isoformat() if order.order_date else None,
        "items": [
            {
                "food_id": i.food_id,
                "food_name": i.food.food_name if i.food else "Item",
                "quantity": i.quantity,
                "price": i.price,
            }
            for i in order.items
        ],
    }


@app.get("/api/orders/mine")
def get_my_orders(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in to view your orders.")
    orders = db.query(models.Order).filter(models.Order.user_id == user.user_id).order_by(models.Order.order_date.desc()).all()
    return [_serialize_order(o) for o in orders]


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _serialize_order(order)


@app.get("/api/orders/phone/{phone}")
def get_orders_by_phone(phone: str, db: Session = Depends(get_db)):
    orders = db.query(models.Order).filter(models.Order.phone == phone).order_by(models.Order.order_date.desc()).all()
    if not orders:
        raise HTTPException(status_code=404, detail="No orders found for this phone number.")
    return [_serialize_order(o) for o in orders]


@app.post("/api/orders/{order_id}/cancel")
def cancel_order_api(order_id: int, request: Request, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    current_user = auth.get_current_user(request, db)
    if current_user and order.user_id and order.user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to cancel this order.")

    if order.status == "Cancelled":
        return {"ok": True, "message": "Order is already cancelled", "status": "Cancelled"}

    if order.status == "Delivered":
        raise HTTPException(status_code=400, detail="Cannot cancel an order that has already been delivered.")

    order.status = "Cancelled"
    order.admin_note = (order.admin_note + "\n" if order.admin_note else "") + "Cancelled by customer"
    db.commit()
    db.refresh(order)

    try:
        email_service.send_order_cancellation(order, "Cancelled by customer")
    except Exception as e:
        print(f"[email_service] Error sending order cancellation email: {e}")

    return {"ok": True, "message": "Order cancelled successfully", "status": "Cancelled"}


# ---------------------- AI Food Assistant ----------------------

@app.post("/api/ai/recommend", response_model=schemas.AIRecommendResponse)
def ai_recommend(payload: schemas.AIRecommendRequest, db: Session = Depends(get_db)):
    reply, recommendations = ai_service.get_recommendation(db, payload.message)
    return {"reply": reply, "recommendations": recommendations}


@app.post("/api/tts")
async def text_to_speech(payload: schemas.TTSRequest):
    """
    Server-side speech for CafeMate (English + Malayalam neural voices).
    Returns MP3 audio; returns 204 (no body) if speech couldn't be produced,
    so the page quietly falls back to the browser's built-in voice.
    """
    audio = await tts_service.synthesize(payload.text, payload.lang)
    if not audio:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg")


# =====================================================================
# ADMIN ACTIONS (orders, reservations, menu)
# =====================================================================

def _require_admin_or_redirect(request: Request, db: Session):
    admin = auth.get_current_user(request, db)
    if not admin or not admin.is_admin:
        raise HTTPException(status_code=403, detail="Admin access only.")
    return admin


@app.post("/admin/orders/{order_id}/status")
def admin_update_order_status(order_id: int, request: Request, status: str = Form(...), db: Session = Depends(get_db)):
    _require_admin_or_redirect(request, db)
    order = db.query(models.Order).filter(models.Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = status
    db.commit()
    return RedirectResponse(url="/admin/orders", status_code=303)


@app.post("/admin/orders/{order_id}/cancel")
def admin_cancel_order(order_id: int, request: Request, reason: str = Form(""), db: Session = Depends(get_db)):
    _require_admin_or_redirect(request, db)
    order = db.query(models.Order).filter(models.Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = "Cancelled"
    order.admin_note = reason
    db.commit()
    email_service.send_order_cancellation(order, reason)
    return RedirectResponse(url="/admin/orders", status_code=303)


@app.post("/admin/orders/{order_id}/request-change")
def admin_request_order_change(order_id: int, request: Request, message: str = Form(...), db: Session = Depends(get_db)):
    _require_admin_or_redirect(request, db)
    order = db.query(models.Order).filter(models.Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = "Change Requested"
    order.admin_note = message
    db.commit()
    email_service.send_order_change_request(order, message)
    return RedirectResponse(url="/admin/orders", status_code=303)


@app.post("/admin/reservations/{reservation_id}/cancel")
def admin_cancel_reservation(reservation_id: int, request: Request, reason: str = Form(""), db: Session = Depends(get_db)):
    _require_admin_or_redirect(request, db)
    reservation = db.query(models.Reservation).filter(models.Reservation.reservation_id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    reservation.status = "cancelled"
    reservation.admin_note = reason
    db.commit()
    email_service.send_reservation_cancellation(reservation, reason)
    return RedirectResponse(url="/admin/reservations", status_code=303)


@app.post("/admin/reservations/{reservation_id}/request-change")
def admin_request_reservation_change(reservation_id: int, request: Request, message: str = Form(...), db: Session = Depends(get_db)):
    _require_admin_or_redirect(request, db)
    reservation = db.query(models.Reservation).filter(models.Reservation.reservation_id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    reservation.admin_note = message
    db.commit()
    email_service.send_order_change_request(reservation, message)  # same template shape works generically
    return RedirectResponse(url="/admin/reservations", status_code=303)


@app.post("/admin/menu/add")
async def admin_add_food(
    request: Request,
    food_name: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    description: str = Form(""),
    is_veg: Optional[str] = Form(None),
    spice_level: int = Form(1),
    availability: Optional[str] = Form(None),
    image_url: str = Form(""),
    image_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    _require_admin_or_redirect(request, db)
    uploaded_url = _save_upload(image_file)
    food = models.Food(
        food_name=food_name,
        category=category,
        price=price,
        description=description,
        is_veg=bool(is_veg),
        spice_level=spice_level,
        image_url=uploaded_url or image_url or "",
        availability=bool(availability),
        rating=4.5,
    )
    db.add(food)
    db.commit()
    return RedirectResponse(url="/admin/menu", status_code=303)


@app.post("/admin/menu/{food_id}/edit")
async def admin_edit_food(
    food_id: int,
    request: Request,
    food_name: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    description: str = Form(""),
    is_veg: Optional[str] = Form(None),
    spice_level: int = Form(1),
    availability: Optional[str] = Form(None),
    image_url: str = Form(""),
    image_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    _require_admin_or_redirect(request, db)
    food = db.query(models.Food).filter(models.Food.food_id == food_id).first()
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")

    uploaded_url = _save_upload(image_file)

    food.food_name = food_name
    food.category = category
    food.price = price
    food.description = description
    food.is_veg = bool(is_veg)
    food.spice_level = spice_level
    food.availability = bool(availability)
    if uploaded_url:
        food.image_url = uploaded_url
    elif image_url:
        food.image_url = image_url

    db.commit()
    return RedirectResponse(url="/admin/menu", status_code=303)


@app.post("/admin/menu/{food_id}/delete")
def admin_delete_food(food_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin_or_redirect(request, db)
    food = db.query(models.Food).filter(models.Food.food_id == food_id).first()
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")
    db.delete(food)
    db.commit()
    return RedirectResponse(url="/admin/menu", status_code=303)
