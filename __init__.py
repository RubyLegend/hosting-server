#!/usr/bin/env python3
from flask import Flask
import redis
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

load_dotenv()

app: Flask = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# Redis configuration
redis_host = os.getenv("REDIS_HOST") or "localhost"
redis_port = int(os.getenv("REDIS_PORT") or 6379)
redis_db = int(os.getenv("REDIS_DB") or 0)

redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)

# Database connection
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")

DATABASE_URL = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

from .database import users, companies, subscribers
Base.metadata.create_all(engine)

@app.route("/")
def home():
    return "<h1>Hello World!</h1>"
