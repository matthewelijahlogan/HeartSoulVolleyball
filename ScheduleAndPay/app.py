import sqlite3
from flask import Flask, render_template, request, redirect, url_for
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

# --- Create DB if not exists ---
def init_db():
    conn = sqlite3.connect('reservations.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            date TEXT,
            time TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return redirect(url_for('schedule'))

@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        date = request.form['date']
        time = request.form['time']

        conn = sqlite3.connect('reservations.db')
        c = conn.cursor()
        c.execute('INSERT INTO reservations (name, email, phone, date, time) VALUES (?, ?, ?, ?, ?)',
                  (name, email, phone, date, time))
        conn.commit()
        conn.close()

        # Send email notification
        send_email_notification(name, email, date, time)

        # Redirect to Venmo
        return redirect(f"https://venmo.com/?txn=pay&audience=private&recipients=YourVenmoUsername&amount=50&note=Training+Session+on+{date}+{time}")
    
    return render_template('schedule.html')

@app.route('/confirmation')
def confirmation():
    return render_template('confirmation.html')

def send_email_notification(name, email, date, time):
    msg = MIMEText(f'New reservation:\n\nName: {name}\nEmail: {email}\nDate: {date}\nTime: {time}')
    msg['Subject'] = 'New Training Reservation'
    msg['From'] = 'youremail@example.com'
    msg['To'] = 'operator@example.com'

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.starttls()
        smtp.login('youremail@example.com', 'yourpassword')
        smtp.send_message(msg)

if __name__ == '__main__':
    app.run(debug=True)
