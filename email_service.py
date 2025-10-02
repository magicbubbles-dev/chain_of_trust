import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import logging
from dotenv import load_dotenv

load_dotenv()

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "gmail").lower()

# Configure SMTP settings based on provider
if EMAIL_PROVIDER == "gmail":
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("SENDER_PASS")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_card_email(recipient_email, subject_no, card_path, unique_key, username):
    try:
        # Check if we have email credentials
        if not SENDER_EMAIL or not SENDER_PASS:
            logger.error("Missing email credentials. Check your .env file.")
            return False

        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = recipient_email
        msg["Subject"] = f"⚠️ WELCOME TO THE LAB | Subject #{subject_no} | CONFIDENTIAL"

        # imma exchanging personal access key and username here
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

        if not os.path.exists(card_path):
            logger.error(f"Card file not found: {card_path}")
            return False

        # Attach card
        with open(card_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(card_path)}")
            msg.attach(part)

        logger.info(f"Sending email to {recipient_email} with card {os.path.basename(card_path)}")

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.send_message(msg)
            logger.info(f"Email sent successfully to {recipient_email}")
            return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to send email: {error_msg}")
        
        # Provide more helpful error messages based on error type
        if "535" in error_msg and "Username and Password not accepted" in error_msg:
            logger.error(f"Authentication failed for {EMAIL_PROVIDER}. Check your credentials.")
        
        return False
