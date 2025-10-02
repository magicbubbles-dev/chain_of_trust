from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
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
logger.info(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'NOT SET')}")
logger.info(f"DB_TOKEN: {'***SET***' if os.getenv('DB_TOKEN') else 'NOT SET'}")

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

# Configure CORS to allow both localhost (development) and production domain
origins = [
    "http://localhost:8000",  # Development
    "http://127.0.0.1:8000",  # Development alternative
    "https://chainoftrust.onrender.com",  # Production
    "https://www.chainoftrust.onrender.com",  # Production with www
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("cards", exist_ok=True)
app.mount("/cards", StaticFiles(directory="cards"), name="cards")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint to verify database connection"""
    try:
        # Test database connection
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        
        # Get user count
        user_count = db.query(Users).count()
        
        return {
            "status": "healthy",
            "environment": ENV.upper(),
            "database": "Turso" if ENV == "production" else "SQLite",
            "user_count": user_count,
            "database_url": os.getenv("DATABASE_URL", "NOT SET")[:50] + "..." if os.getenv("DATABASE_URL") else "NOT SET"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "environment": ENV.upper(),
            "database": "Turso" if ENV == "production" else "SQLite"
        }

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

    try:
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")

        # Create new user record
        new_user = Users(username=username, email=email, name=name)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"User created with ID: {new_user.id}, using database: {'Turso' if ENV == 'production' else 'SQLite'}")

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
        logger.info(f"User data committed successfully: {new_user.username} (ID: {new_user.id})")

        # Email will be sent separately via the /send-email endpoint
        # to avoid blocking the response

        return JSONResponse({
            "success": True,
            "subject_no": new_user.subject_no,
            "card_path": card_path,
            "user_id": new_user.id,
            "unique_key": raw_key 
        })
        
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        db.rollback()  # Rollback on error
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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


# SPA Fallback Route - Catch all other routes and serve index.html
# This ensures that client-side routing works properly on platforms like Render
@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """
    Catch-all route for Single Page Application.
    Serves index.html for any route that doesn't match API endpoints or static files.
    This prevents 404 errors when users reload the page or navigate directly to routes.
    """
    if full_path.startswith(("static/", "cards/")):
        # Let FastAPI handle static files normally
        raise HTTPException(status_code=404, detail="File not found")
    
    # For all other routes, serve the main page (SPA routing)
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

