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
elif EMAIL_PROVIDER == "sendgrid":
    SMTP_SERVER = "smtp.sendgrid.net"
    SMTP_PORT = 587
elif EMAIL_PROVIDER == "mailgun":
    SMTP_SERVER = "smtp.mailgun.org"
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

        logger.info(f"Connecting to SMTP server {SMTP_SERVER}:{SMTP_PORT} with provider {EMAIL_PROVIDER}")
        
        # Add timeout to prevent hanging
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            logger.info("SMTP connection established, starting TLS")
            server.starttls()
            
            # Log authentication attempt (without sensitive data)
            logger.info(f"Attempting login for {EMAIL_PROVIDER} with user: {SENDER_EMAIL if EMAIL_PROVIDER != 'sendgrid' else 'apikey'}")
            
            # Handle different authentication methods
            if EMAIL_PROVIDER == "sendgrid":
                # SendGrid uses "apikey" as username and API key as password
                server.login("apikey", SENDER_PASS)
            elif EMAIL_PROVIDER == "mailgun":
                # Mailgun uses full email as username and API key as password
                server.login(SENDER_EMAIL, SENDER_PASS)
            else:
                # Default Gmail authentication
                server.login(SENDER_EMAIL, SENDER_PASS)
                
            logger.info("Authentication successful")
                
            server.send_message(msg)
            logger.info(f"Email sent successfully to {recipient_email}")
            return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to send email: {error_msg}")
        
        # Provide more helpful error messages based on error type
        if "535" in error_msg and "Username and Password not accepted" in error_msg:
            logger.error(f"Authentication failed for {EMAIL_PROVIDER}. Check your credentials.")
        elif "socket.gaierror" in error_msg or "getaddrinfo" in error_msg:
            logger.error(f"DNS resolution failed for {SMTP_SERVER}. Check network connectivity.")
        elif "Connection refused" in error_msg:
            logger.error(f"Connection refused to {SMTP_SERVER}:{SMTP_PORT}. The server might be blocking requests.")
        elif "timeout" in error_msg.lower():
            logger.error(f"Connection timed out to {SMTP_SERVER}:{SMTP_PORT}.")
        elif "certificate" in error_msg.lower() or "ssl" in error_msg.lower():
            logger.error(f"SSL/TLS error connecting to {SMTP_SERVER}. This may be due to security restrictions.")
        
        # Print all environment variables (redacted) to help with debugging
        logger.error(f"Environment check: EMAIL_PROVIDER={EMAIL_PROVIDER}, SENDER_EMAIL={'[SET]' if SENDER_EMAIL else '[MISSING]'}, SENDER_PASS={'[SET]' if SENDER_PASS else '[MISSING]'}")
        
        return False
