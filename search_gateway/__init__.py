#!/usr/bin/env python3
from flask import Flask
from flasgger import Swagger
import redis
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

load_dotenv()

app: Flask = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["TOKEN_TIMEOUT"] = os.getenv("TOKEN_TIMEOUT")
swagger_template = {
    "uiversion": 3,
    "openapi": "3.0.3",
    "swagger": "3.0.3",
    "info": {
        "title": "Search API",
        "description": "API for testing search related endpoints for Media Hosting application",
        "version": "1.0.0"
    },
    "basePath": "/",  # base bash for blueprint registration
    "schemes": [
        "http",
        "https"
    ],
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
            }
        },
    }
}

swagger = Swagger(app, template=swagger_template)

# Redis configuration
redis_host = os.getenv("REDIS_HOST") or "localhost"
redis_port = int(os.getenv("REDIS_PORT") or 6379)
redis_username = os.getenv("REDIS_USER") or "none"
redis_password = os.getenv("REDIS_PASSWORD") or "none"
redis_db = int(os.getenv("REDIS_DB") or 0)

redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, username=redis_username, password=redis_password)

# Database connection
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")

DATABASE_URL = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

from .database import accessLevels, comments, companies, \
    media, mediaTagsConnector, ratings, ratingTypes, searchHistory, \
    subscribers, tags, userRoles, users, viewHistory, mediaPreview, \
    logos, reports
Base.metadata.create_all(engine)

# Configuration for uploads
# UPLOAD_FOLDER = 'uploads'  # Directory to store uploaded files
# PREVIEW_FOLDER = 'previews'
# LOGO_FOLDER = 'logos'

# mid files currently not working as expected
# WMP infinitely loading file without actually caching it
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'}
ALLOWED_EXTENSIONS = ALLOWED_VIDEO_EXTENSIONS.union(ALLOWED_AUDIO_EXTENSIONS)  # Allowed file extensions
# ALLOWED_PREVIEW_EXTENSIONS = {'jpg', 'jpeg', 'png'}  # Allowed preview extensions

# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Create the upload directory if it doesn't exist
# app.config['PREVIEW_FOLDER'] = PREVIEW_FOLDER
# os.makedirs(PREVIEW_FOLDER, exist_ok=True)  # Create the preview directory if it doesn't exist
# app.config['LOGO_FOLDER'] = LOGO_FOLDER
# os.makedirs(LOGO_FOLDER, exist_ok=True)  # Create the logo directory if it doesn't exist
# app.config['MAX_CONTENT_LENGTH'] = None  # Disable limit in Flask

@app.route("/")
def home():
    return "<h1>Hello World from search routes!</h1>"
