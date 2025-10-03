from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import logging
import base64

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Gmail API scope
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Path to token.json (generated locally and uploaded to your server)
TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_card_email(recipient_email, subject_no, card_path, unique_key, username):
    try:
        if not os.path.exists(TOKEN_PATH):
            logger.error("Missing token.json. Run the Gmail OAuth flow to generate it.")
            return False

        # Load Gmail credentials
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        service = build("gmail", "v1", credentials=creds)

        # Build email
        msg = MIMEMultipart()
        msg["To"] = recipient_email
        msg["From"] = creds.token_uri  # Gmail API fills this correctly when sending
        msg["Subject"] = f"⚠️ WELCOME TO THE LAB | Subject #{subject_no} | CONFIDENTIAL"

        # HTML body (kept same as your code)
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
                        Till then<br><br>
                        <strong>- The Lab<br>Chain of Trust</strong>
                        </p>
                    </body>
                </html>
                """
        msg.attach(MIMEText(body, "html"))

        # Attach card
        if not os.path.exists(card_path):
            logger.error(f"Card file not found: {card_path}")
            return False

        with open(card_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(card_path)}"
            )
            msg.attach(part)

        logger.info(f"Sending email to {recipient_email} with card {os.path.basename(card_path)}")

        # Encode and send via Gmail API
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        message = {"raw": raw_message}

        service.users().messages().send(userId="me", body=message).execute()

        logger.info(f"Email sent successfully to {recipient_email}")
        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to send email: {error_msg}")
        return False
