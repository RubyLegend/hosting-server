#!/usr/bin/env python3
from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()

app: Flask = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")


@app.route("/")
def home():
    return "<h1>Hello World!</h1>"
