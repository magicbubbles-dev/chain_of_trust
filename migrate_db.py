"""
Migration script to transfer data from local SQLite database to Turso.
To use:
1. Make sure you have both databases configured in .env
2. Run this script: python3 migrate_db.py
"""

import logging
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from datetime import datetime
import libsql

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

Base = declarative_base()

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

def migrate_data():
    # Source SQLite database
    source_url = "sqlite:///./chain_of_trust.db"
    source_engine = create_engine(source_url)
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()
    
    # Target Turso database
    target_url = os.getenv("DATABASE_URL", "libsql://chainoftrust-magicbubbles-dev.aws-ap-south-1.turso.io")
    db_token = os.getenv("DB_TOKEN")
    
    if not db_token:
        logger.error("DB_TOKEN not found in .env file")
        return
    
    # Transform URL using the proven method
    transformed_url = target_url.replace('libsql://', 'sqlite+libsql://')
    
    if '?secure=true' not in transformed_url:
        transformed_url += '?secure=true'
        
    target_engine = create_engine(
        transformed_url,
        connect_args={
            "auth_token": db_token,
            "check_same_thread": False
        }
    )
    Base.metadata.create_all(bind=target_engine)
    TargetSession = sessionmaker(bind=target_engine)
    target_session = TargetSession()
    
    # Get all users from source database
    logger.info("Getting users from SQLite database...")
    try:
        users = source_session.query(Users).all()
        logger.info(f"Found {len(users)} users in SQLite database")
    except Exception as e:
        logger.error(f"Error reading from SQLite: {e}")
        return
    
    # Insert users into target database
    logger.info("Migrating users to Turso database...")
    for user in users:
        try:
            # Create new user object for target database
            new_user = Users(
                username=user.username,
                name=user.name,
                email=user.email,
                subject_no=user.subject_no,
                unique_key=user.unique_key,
                card_path=user.card_path,
                created_at=user.created_at
            )
            target_session.add(new_user)
            target_session.commit()
            logger.info(f"Migrated user {user.username}")
        except Exception as e:
            logger.error(f"Error migrating user {user.username}: {e}")
            target_session.rollback()
    
    logger.info("Migration complete!")
    source_session.close()
    target_session.close()

if __name__ == "__main__":
    logger.info("Starting database migration...")
    migrate_data()