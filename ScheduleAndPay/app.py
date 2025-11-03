# ScheduleAndPay/app.py

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import json, os, datetime
from dotenv import load_dotenv

# Gmail API helper
from ScheduleAndPay.gmail_oauth import gmail_send_message

# ========================================
# SETUP
# ========================================
load_dotenv()
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_KEY", "super_secret_key"))

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "../db/bookings.json")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ========================================
# HOURS OF OPERATION
# ========================================
DEFAULT_HOURS = [
    "08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM"
]
HOURS = DEFAULT_HOURS.copy()

# ========================================
# DATABASE HELPERS
# ========================================
def load_bookings():
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH, "r") as f:
        return json.load(f)

def save_bookings(data):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)

# ========================================
# EMAIL FUNCTION (GMAIL)
# ========================================
def send_email(to_email, subject, body):
    sender_email = os.getenv("ADMIN_EMAIL")
    if not sender_email:
        raise ValueError("ADMIN_EMAIL not set in .env")
    gmail_send_message(subject, body, sender_email, to_email)

# ========================================
# GOOGLE OAUTH CONFIG
# ========================================
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # dev mode only

GOOGLE_CLIENT_SECRETS = os.path.join(BASE_DIR, "credentials.json")
GOOGLE_REDIRECT_URI = "http://localhost:8001/auth/callback"

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "heartsoulvolleyballtraining@gmail.com")

# ========================================
# ROUTES
# ========================================
@app.get("/", response_class=HTMLResponse)
async def show_schedule(request: Request, week_offset: int = 0):
    today = datetime.date.today() + datetime.timedelta(weeks=week_offset)
    start_of_week = today - datetime.timedelta(days=today.weekday())
    bookings = load_bookings()

    week_days = []
    for i in range(7):
        day = start_of_week + datetime.timedelta(days=i)
        str_day = day.strftime("%Y-%m-%d")
        booked_slots = bookings.get(str_day, [])
        available_slots = [h for h in HOURS if h not in booked_slots]
        week_days.append({
            "date": str_day,
            "day_name": day.strftime("%A"),
            "slots": available_slots
        })

    return templates.TemplateResponse("schedule.html", {
        "request": request,
        "week_days": week_days,
        "week_offset": week_offset,
        "user": request.session.get("user"),
        "now": datetime.datetime.now
    })

# ========================================
# BOOKING FLOW
# ========================================
@app.post("/reserve", response_class=HTMLResponse)
async def reserve_session(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    date: str = Form(...),
    time: str = Form(...)
):
    bookings = load_bookings()
    day_slots = bookings.get(date, [])
    if time not in day_slots:
        day_slots.append(time)
    bookings[date] = day_slots
    save_bookings(bookings)

    slot = f"{date} at {time}"
    venmo_link = "https://venmo.com/heartsoulvolleyball"

    subject = "Heart Soul Volleyball Training Reservation"
    body = f"""
        <h2>Reservation Confirmed</h2>
        <p>{name}, your session for <strong>{slot}</strong> has been reserved!</p>
        <p>Please complete your payment here: <a href="{venmo_link}">{venmo_link}</a></p>
        <p>Thank you for booking with Heart Soul Volleyball!</p>
    """
    try:
        send_email(email, subject, body)
        send_email(ADMIN_EMAIL, "New Reservation", body)
    except Exception as e:
        print(f"Error sending email: {e}")

    return templates.TemplateResponse("confirmation.html", {
        "request": request,
        "slot": slot,
        "venmo_link": venmo_link
    })

# ========================================
# GOOGLE OAUTH LOGIN / LOGOUT
# ========================================
@app.get("/login")
def login(request: Request):
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS,
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ],
        redirect_uri=GOOGLE_REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(prompt="consent")
    request.session["state"] = state
    return RedirectResponse(url=authorization_url)

@app.get("/auth/callback")
def auth_callback(request: Request):
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS,
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ],
        redirect_uri=GOOGLE_REDIRECT_URI
    )
    flow.fetch_token(authorization_response=str(request.url))
    creds = flow.credentials
    idinfo = id_token.verify_oauth2_token(creds.id_token, grequests.Request())
    email = idinfo.get("email")
    name = idinfo.get("name")

    request.session["user"] = {"email": email, "name": name}

    if email == ADMIN_EMAIL:
        return RedirectResponse(url="/admin/hours")
    return RedirectResponse(url="/")

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

# ========================================
# ADMIN HOURS EDITOR
# ========================================
@app.get("/admin/hours", response_class=HTMLResponse)
async def edit_hours(request: Request):
    user = request.session.get("user")
    if not user or user.get("email") != ADMIN_EMAIL:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        "admin_hours.html",
        {"request": request, "hours": HOURS, "user": user, "DEFAULT_HOURS": DEFAULT_HOURS}
    )

@app.post("/admin/hours", response_class=HTMLResponse)
async def update_hours(request: Request, new_hours: str = Form(...)):
    user = request.session.get("user")
    if not user or user.get("email") != ADMIN_EMAIL:
        return RedirectResponse(url="/login")
    global HOURS
    HOURS = [h.strip() for h in new_hours.split(",") if h.strip()]
    if not HOURS:
        HOURS = DEFAULT_HOURS.copy()
    return RedirectResponse(url="/admin/hours", status_code=303)
