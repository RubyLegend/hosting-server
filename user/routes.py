from flask import Flask, request, jsonify, redirect, url_for
import datetime
import bcrypt
from sqlalchemy import exc
from .. import app, redis_client, Session
from .functions import generate_token, token_required
from ..database.users import Users

# Fix for pylsp
app: Flask


@app.post("/profile/login")
def login():
    auth = request.get_json()

    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'token': None, 'message': 'Could not verify'}), 401

    username = auth.get('username')
    password = auth.get('password')

    session = Session()
    try:
        user = session.query(Users).filter_by(LoginUser=username).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.Password.encode('utf-8')):
            token = generate_token(user.IdUser)
            return jsonify({'token': token, 'message': "success"}), 200
        return jsonify({'message': 'Invalid credentials'}), 401
    except Exception as e:
        app.logger.error(f"Error during login: {e}") # Log the full error
        return jsonify({'message': 'Login failed'}), 500
    finally:
        session.close()


@app.post("/profile/logout")
@token_required
def logout(current_user):
    token = request.headers['Authorization'].split(" ")[1]
    redis_client.delete(f"user:{current_user}:token")
    redis_client.delete(f"token:{token}")
    return jsonify({'message': 'Logged out successfully'}), 200


@app.get("/profile/")
def profile_redir():
    return redirect(url_for('profile'), 302)


@app.get("/profile")
@token_required
def profile(current_user):
    return jsonify({
        "user_id": current_user,
        'user': 'Ruby',
        'authorized': 'yes',
    }), 200

@app.post('/profile/register')
def register():
    data = request.get_json()
    email = data.get('email')
    loginUser = data.get('loginUser')
    nameUser = data.get('nameUser')
    surname = data.get('surname')
    patronymic = data.get('patronymic')
    birthday = data.get('birthday')
    registerTime = datetime.datetime.utcnow()
    about = data.get('about')
    password = data.get('password')
    passwordAgain = data.get('passwordAgain')


    if not loginUser or not password:
        return jsonify({'message': 'Username and password are required'}), 400


    if password != passwordAgain:
        return jsonify({'message': 'Passwords do not match'}), 400


    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    session = Session()
    try:
        new_user = Users(Email=email, LoginUser=loginUser, NameUser=nameUser, Surname=surname, Patronymic=patronymic, Birthday=birthday, RegisterTime=registerTime, About=about, Password=hashed_password)
        session.add(new_user)
        session.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except exc.IntegrityError as e: # Catch IntegrityError (most common MySQL errors)
        session.rollback()
        app.logger.error(f"IntegrityError during registration: {e}") # Log the full error
        if "Duplicate entry" in str(e):
            return jsonify({'message': 'Username already exists'}), 400 # More specific error
        else:
            return jsonify({'message': 'Registration failed due to database error'}), 500 # Generic message
    except Exception as e:  # Catch other potential exceptions
        session.rollback()
        app.logger.exception("An unexpected error occurred during registration:") # Log full traceback
        return jsonify({'message': 'Registration failed'}), 500
    finally:
        session.close()
