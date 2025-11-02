# ScheduleAndPay/gmail_oauth.py

import os
import pickle
import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the token.json file.
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def gmail_send_message(subject, body, sender, recipient):
    creds = None
    token_path = os.path.join(BASE_DIR, "token.json")
    credentials_path = os.path.join(BASE_DIR, "credentials.json")

    # Load or create credentials
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    # Build service
    service = build("gmail", "v1", credentials=creds)

    # Create MIME email
    message = MIMEText(body)
    message["to"] = recipient
    message["from"] = sender
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Send
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
