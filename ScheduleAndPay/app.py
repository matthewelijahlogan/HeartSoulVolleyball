from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.sessions import SessionMiddleware
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import json, os, datetime, smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# ========================================
# SETUP
# ========================================
load_dotenv()
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="super_secret_key")  # Change this!

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "../db/bookings.json")

app.mount("/static", StaticFiles(directory="ScheduleAndPay/static"), name="static")
templates = Jinja2Templates(directory="ScheduleAndPay/templates")

# ========================================
# HOURS OF OPERATION
# ========================================
HOURS = [
    "08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM"
]

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
# EMAIL FUNCTION
# ========================================
def send_email(to_email, subject, body):
    sender_email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("EMAIL_PASSWORD")
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, password)
        smtp.send_message(msg)

# ========================================
# GOOGLE OAUTH CONFIG
# ========================================
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # dev mode only

GOOGLE_CLIENT_SECRETS = os.path.join(BASE_DIR, "credentials.json")
GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/callback"

flow = Flow.from_client_secrets_file(
    GOOGLE_CLIENT_SECRETS,
    scopes=["https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri=GOOGLE_REDIRECT_URI
)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

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
        "user": request.session.get("user")
    })

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

    # Send confirmation emails
    subject = "Heart Soul Volleyball Training Reservation"
    body = f"""
        <h2>Reservation Confirmed</h2>
        <p>{name}, your session for <strong>{slot}</strong> has been reserved!</p>
        <p>Please complete your payment here: <a href="{venmo_link}">{venmo_link}</a></p>
    """
    send_email(email, subject, body)
    send_email(ADMIN_EMAIL, "New Reservation", body)

    return templates.TemplateResponse("confirmation.html", {
        "request": request,
        "slot": slot,
        "venmo_link": venmo_link
    })

# ========================================
# GOOGLE OAUTH LOGIN / LOGOUT
# ========================================

@app.get("/login")
def login():
    authorization_url, state = flow.authorization_url()
    return RedirectResponse(url=authorization_url)

@app.get("/auth/callback")
def auth_callback(request: Request):
    flow.fetch_token(authorization_response=str(request.url))
    credentials = flow.credentials
    token = credentials.id_token
    info = id_token.verify_oauth2_token(token, grequests.Request())
    user_email = info.get("email")

    if user_email == ADMIN_EMAIL:
        request.session["user"] = user_email
        return RedirectResponse(url="/admin/hours")
    else:
        return HTMLResponse("<h3>Access denied. Not an authorized admin.</h3>")

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

# ========================================
# ADMIN HOURS EDITOR (Protected)
# ========================================
@app.get("/admin/hours", response_class=HTMLResponse)
async def edit_hours(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("admin_hours.html", {"request": request, "hours": HOURS, "user": user})

@app.post("/admin/hours", response_class=HTMLResponse)
async def update_hours(request: Request, new_hours: str = Form(...)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    global HOURS
    HOURS = [h.strip() for h in new_hours.split(",") if h.strip()]
    return RedirectResponse(url="/admin/hours", status_code=303)
