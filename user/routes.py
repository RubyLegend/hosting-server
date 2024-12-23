from flask import Flask, request, jsonify, redirect, url_for
import datetime
import bcrypt
from sqlalchemy import exc
from .. import app, redis_client, Session
from .functions import generate_token, token_required
from ..database.users import Users
from ..database.companies import Companies
from ..database.accessLevels import AccessLevels
from ..database.userRoles import UserRoles

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
            return jsonify({'user_id': user.IdUser, 'token': token, 'message': "success"}), 200
        return jsonify({'message': 'Invalid credentials'}), 401
    except Exception as e:
        app.logger.error(f"Error during login: {e}") # Log the full error
        return jsonify({'message': 'Login failed'}), 500
    finally:
        session.close()


@app.post("/profile/logout")
@token_required
def logout(current_user, owned_companies):
    token = request.headers['Authorization'].split(" ")[1]
    redis_client.delete(f"user:{current_user}:token")
    redis_client.delete(f"token:{token}")
    return jsonify({'message': 'Logged out successfully'}), 200


@app.get("/profile/")
def profile_redir():
    return redirect(url_for('profile'), 302)


@app.get("/profile")
@token_required
def profile(current_user, owned_companies):
    session = Session()
    try:
        user = session.query(Users).filter_by(IdUser=current_user).first()
        if not user:
            return jsonify({'message': 'User not found'}), 404  # Should not happen if token_required is working correctly

        subscriptions = []
        for subscription in user.subscribers:
            company = session.query(Companies).filter_by(IdCompany=subscription.IdCompany).first()
            if company: # Handle cases where company might have been deleted
                subscriptions.append({
                    "company_id": subscription.IdCompany,
                    "company_name": company.Name
                })

        user_info = {
            "user_id": user.IdUser,
            "login": user.LoginUser,
            "name": user.NameUser,
            "surname": user.Surname,
            "subscriptions": subscriptions
        }

        return jsonify(user_info), 200

    except exc.SQLAlchemyError as e:
        app.logger.exception(f"Database error getting user profile: {e}")
        return jsonify({'message': 'Database error'}), 500
    except Exception as e:
        app.logger.exception(f"Error getting user profile: {e}")
        return jsonify({'message': 'Error getting user profile'}), 500
    finally:
        session.close()


@app.get("/profile/subscriptions")
@token_required
def get_profile_subscriptions(current_user, owned_companies):
    session = Session()
    try:
        user = session.query(Users).filter_by(IdUser=current_user).first()
        if not user:
            return jsonify({'message': 'User not found'}), 404  # Should not happen if token_required is working correctly

        subscriptions = []
        for subscription in user.subscribers:
            company = session.query(Companies).filter_by(IdCompany=subscription.IdCompany).first()
            if company: # Handle cases where company might have been deleted
                subscriptions.append({
                    "company_id": subscription.IdCompany,
                    "company_name": company.Name
                })

        return jsonify(subscriptions), 200

    except exc.SQLAlchemyError as e:
        app.logger.exception(f"Database error getting user profile: {e}")
        return jsonify({'message': 'Database error'}), 500
    except Exception as e:
        app.logger.exception(f"Error getting user profile: {e}")
        return jsonify({'message': 'Error getting user profile'}), 500
    finally:
        session.close()



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
        session.flush()

         # Add default user role
        user_level = session.query(AccessLevels).filter_by(AccessName="User").first()
        if not user_level:
            app.logger.error("User access level not found in database. Critical error!")
            session.rollback()
            return jsonify({'message': 'Internal server error'}), 500

        new_user_role = UserRoles(IdUser=new_user.IdUser, IdAccessLevel=user_level.IdAccessLevel)
        session.add(new_user_role)

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
