from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
import base64, os, json

# Gmail API scope
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Path to your token.json file
TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")

def send_card_email(recipient_email: str, subject_no: int, card_path: str, unique_key: str, username: str):
    """
    Sends an email with an attached card file using Gmail API.
    """

    # --- Load credentials ---
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    else:
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # --- Build Gmail service ---
    service = build("gmail", "v1", credentials=creds)

    # --- Build the email ---
    msg = MIMEMultipart()
    msg["To"] = recipient_email
    msg["Subject"] = f"⚠️ WELCOME TO THE LAB | Subject #{subject_no} | CONFIDENTIAL"

    body = f"""
    <html>
      <body>
        <p><strong>Greetings, Subject {subject_no}.</strong></p>
        <p>Your registration has been acknowledged.<br>
        Enclosed is your Identification Card. Keep it secure — it will be required for entry.<br><br>
        <strong>Your username:</strong> <span style='font-size:1.2em'>{unique_key}</span><br>
        <strong>Your personal access key:</strong> <span style='font-size:1.2em'>{username}</span><br>
        <span style='font-weight:bold; color:#b00;'>*This is confidential. Do not share it. Do not lose it.*</span><br><br>
        You'll receive further instructions very soon.<br><br>
        <strong>- The Lab<br>Chain of Trust</strong>
        </p>
      </body>
    </html>
    """
    msg.attach(MIMEText(body, "html"))

    # --- Attach the card file ---
    with open(card_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(card_path)}"
        )
        msg.attach(part)

    # --- Encode and send ---
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
        return True  
    except HttpError as error:
        status = getattr(error, "status_code", "Unknown")
        reason = error._get_reason()
        content = error.content.decode() if hasattr(error.content, "decode") else str(error.content)

        print(f"Gmail API Error [{status}]: {reason}")
        print(content)
        raise
