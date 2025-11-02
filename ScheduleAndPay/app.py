from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json, os, datetime, smtplib
from email.mime.text import MIMEText

app = FastAPI()

# Paths
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "../db/bookings.json")

app.mount("/static", StaticFiles(directory="ScheduleAndPay/static"), name="static")
templates = Jinja2Templates(directory="ScheduleAndPay/templates")

# Hours of operation (editable)
HOURS = ["08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
         "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM"]

def load_bookings():
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH, "r") as f:
        return json.load(f)

def save_bookings(data):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)

def send_email(to_email, subject, body):
    sender_email = "heartsoulvolleyball@gmail.com"
    password = os.getenv("EMAIL_PASSWORD")  # store securely in .env
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, password)
        smtp.send_message(msg)

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
        "week_offset": week_offset
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

    # Email both admin and user
    subject = "Heart Soul Volleyball Training Reservation"
    body = f"""
        <h2>Reservation Confirmed</h2>
        <p>{name}, your session for <strong>{slot}</strong> has been reserved!</p>
        <p>Please complete your payment here: <a href="{venmo_link}">{venmo_link}</a></p>
        <p>Thank you for booking with Heart Soul Volleyball!</p>
    """
    send_email(email, subject, body)
    send_email("heartsoulvolleyball@gmail.com", "New Reservation", body)

    return templates.TemplateResponse("confirmation.html", {
        "request": request,
        "slot": slot,
        "venmo_link": venmo_link
    })
