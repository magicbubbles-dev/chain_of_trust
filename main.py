from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from datetime import datetime
import os
import logging
from email_service import send_card_email
from hashing import generate_unique_key 
import hashlib
from dotenv import load_dotenv


load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from card_maker import generate_card

Base = declarative_base()

ENV = os.getenv("ENVIRONMENT", "development").lower()
logger.info(f"Running in {ENV.upper()} environment")

if ENV == "production":
    # Production: Use Turso DB
    DATABASE_URL = os.getenv("DATABASE_URL", "libsql://chainoftrust-magicbubbles-dev.aws-ap-south-1.turso.io")
    DB_TOKEN = os.getenv("DB_TOKEN")

    if not DB_TOKEN:
        logger.error("DB_TOKEN not found in .env file")
        raise ValueError("DB_TOKEN environment variable is required")

    # Create SQLAlchemy engine with Turso connection using the proven method of git hotornot
    logger.info("Using Turso DB for database")
    transformed_url = DATABASE_URL.replace('libsql://', 'sqlite+libsql://')
    
    if '?secure=true' not in transformed_url:
        transformed_url += '?secure=true'
        
    engine = create_engine(
        transformed_url,
        connect_args={
            "auth_token": DB_TOKEN,
            "check_same_thread": False
        }
    )
else:
    # Development: Use local SQLite DB
    logger.info("Using local SQLite database")
    DATABASE_URL = "sqlite:///./chain_of_trust.db"
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    name = Column(String, default="Anon")
    email = Column(String, unique=True, index=True)
    subject_no = Column(String, unique=True, index=True)
    unique_key = Column(String, unique=True, index=True)
    card_path = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

################################################
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

os.makedirs("cards", exist_ok=True)
app.mount("/cards", StaticFiles(directory="cards"), name="cards")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def home():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/create_user")
def create_user(
    username: str = Form(...),
    email: str = Form(...),
    name: str = Form("Anon"),
    pfp_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    logger.info(f"Processing card generation request (ID: {abs(hash(username)) % 1000000 if username else 'unknown'})")

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    # Create new user record
    new_user = Users(username=username, email=email, name=name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    new_user.subject_no = f"{new_user.id:03d}"

    # --- Generate card ---
    os.makedirs("cards", exist_ok=True)
    card_filename = f'{username}_{new_user.id}.png'
    card_path = os.path.join("cards", card_filename)
    new_user.card_path = card_path

    if pfp_file and pfp_file.filename:
        temp_pfp_path = f"temp_{username}.png"
        with open(temp_pfp_path, "wb") as buffer:
            buffer.write(pfp_file.file.read())
        generate_card(temp_pfp_path, new_user.subject_no, new_user.name, card_path)
        os.remove(temp_pfp_path)
    else:
        generate_card(None, new_user.subject_no, new_user.name, card_path)

    # --- Generate unique key ---
    raw_key = generate_unique_key()
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    new_user.unique_key = hashed_key

    db.commit()
    db.refresh(new_user)

    # Email will be sent separately via the /send-email endpoint
    # to avoid blocking the response

    return JSONResponse({
        "success": True,
        "subject_no": new_user.subject_no,
        "card_path": card_path,
        "user_id": new_user.id,
        "unique_key": raw_key 
    })

@app.post("/send-email")
def send_email(
    user_id: int = Form(...),
    unique_key: str = Form(...),
    username: str = Form(...),  # Get the username from the frontend
    db: Session = Depends(get_db)
):
    """
    Separate endpoint to send email with the generated card.
    This allows the main card generation to complete quickly.
    """
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not os.path.exists(user.card_path):
        raise HTTPException(status_code=404, detail="Card not found")
        
    try:
        # Pass the unique_key to the email service
        success = send_card_email(user.email, user.subject_no, user.card_path, user.username, unique_key)
        if success:
            logger.info(f"Email sent to {user.email}")
            return JSONResponse({
                "success": True,
                "message": "Email sent successfully"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

