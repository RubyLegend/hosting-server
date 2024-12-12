#!/usr/bin/env python3
from flask import Flask
import redis
from dotenv import load_dotenv
import os

load_dotenv()

app: Flask = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# Redis configuration
redis_host = os.getenv("REDIS_HOST") or "localhost"
redis_port = int(os.getenv("REDIS_PORT") or 6379)
redis_db = int(os.getenv("REDIS_DB") or 0)

redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)


@app.route("/")
def home():
    return "<h1>Hello World!</h1>"
