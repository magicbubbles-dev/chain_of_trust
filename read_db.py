from sqlalchemy import create_engine  
from sqlalchemy.orm import sessionmaker  
from main import Users, engine, SessionLocal
from dotenv import load_dotenv
import os
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def get_users():
    session = SessionLocal()
    users = session.query(Users).all()
    for user in users:
        print(user.id, user.username, user.name, user.email, user.card_path, user.unique_key)
    session.close()

print(get_users())



