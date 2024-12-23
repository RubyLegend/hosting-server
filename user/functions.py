import jwt
import datetime
import redis
import json
from .. import app, redis_client, Session
from ..database.userRoles import UserRoles
from ..database.accessLevels import AccessLevels
from ..database.users import Users
from flask import Flask, request, jsonify
from functools import wraps
from sqlalchemy import or_
import redis

app: Flask
redis_client: redis.Redis

def generate_token(current_user):
    """Generates a JWT token for a given user ID."""
    session = Session()
    try:
        user = session.query(Users).filter_by(IdUser=current_user).first()
        if not user:
            return jsonify({"message": "Fatal error. User not found."}), 404

        payload = {
            'user_id': user.IdUser,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30),  # Token expiration time
            'iat': datetime.datetime.utcnow(),  # Issued at time
            'owned_companies': [role.IdCompany for role in user.user_roles if role.access_levels.AccessName == "Company Owner" and role.IdCompany is not None] # Add owned companies
        }
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

        # Store the token in Redis with an expiration time
        redis_client.setex(f"user:{current_user}:token", datetime.timedelta(minutes=30), token)

        return token

    except Exception as e:
        return jsonify({'message': 'Something went wrong!' + str(e)}), 500
    finally:
        session.close()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]  # Extract token from Bearer header
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            user_data_json = redis_client.get(f"token:{token}")  # Get JSON string from Redis

            if user_data_json:
                try:
                    user_data = json.loads(user_data_json)  # Decode JSON
                    user_id = user_data['user_id']
                    owned_companies = user_data.get('owned_companies', [])
                except (json.JSONDecodeError, KeyError): # Handle JSON decoding errors
                    return jsonify({'message': 'Invalid token data in Redis'}), 401
                current_auth_token = redis_client.get(f"user:{user_id}:token").decode("utf-8")
                if current_auth_token != token:
                    redis_client.setex(f"token:{token}", datetime.timedelta(minutes=30), "INVALID")
                    redis_client.setex(f"token:{current_auth_token}", datetime.timedelta(minutes=30), str(user_id))
                    return jsonify({'message': 'Token has expired!'}), 401
            else:
                try:
                    data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                    user_id = data['user_id']
                    owned_companies = data.get('owned_companies', [])
                    redis_client.setex(f"user:{user_id}:token", datetime.timedelta(minutes=30), token)
                    redis_client.setex(f"token:{token}", datetime.timedelta(minutes=30), json.dumps(data)) # Store data as JSON
                except jwt.ExpiredSignatureError:
                    return jsonify({'message': 'Token has expired!'}), 401
                except jwt.InvalidTokenError:
                    return jsonify({'message': 'Token is invalid!'}), 401
            
        except Exception as e:
            return jsonify({'message': 'Something went wrong!' + str(e)}), 500

        return f(user_id, owned_companies, *args, **kwargs)
    return decorated


def get_access_level_by_name(session, access_name):
    access_level_record = session.query(AccessLevels).filter_by(AccessName=access_name).first()
    return access_level_record.AccessLevel if access_level_record else None

def user_has_access_level(current_user, required_level, session):
    """Helper function to check if a user has at least the required access level."""
    for role in current_user.user_roles:  # Iterate through user's roles
        if role.access_levels.AccessLevel >= required_level:
            return True
    return False

def admin_level(f):
    @wraps(f)
    def decorated_function(current_user, *args, **kwargs):
        session = Session()
        try:
            user = session.query(Users).filter_by(IdUser=current_user).first()
            if not user:
                return jsonify({'message': 'User not found'}), 404
                
            if not user_has_access_level(user, get_access_level_by_name(session, "Admin"), session):
                return jsonify({'message': 'Admin access required'}), 403
            return f(current_user, *args, **kwargs)
        except Exception as e:
            app.logger.exception(f"Error checking admin rights: {e}")
            return jsonify({'message': 'Error checking rights'}), 500
        finally:
            session.close()
    return decorated_function

def moderator_level(f):
    @wraps(f)
    def decorated_function(current_user, *args, **kwargs):
        session = Session()
        try:
            user = session.query(Users).filter_by(IdUser=current_user).first()
            if not user:
                return jsonify({'message': 'User not found'}), 404

            if not user_has_access_level(user, get_access_level_by_name(session, "Moderator"), session):
                return jsonify({'message': 'Moderator access required'}), 403
            return f(current_user, *args, **kwargs)
        except Exception as e:
            app.logger.exception(f"Error checking moderator rights: {e}")
            return jsonify({'message': 'Error checking rights'}), 500
        finally:
            session.close()
    return decorated_function


def company_owner_level(f):
    @wraps(f)
    def decorated_function(current_user, owned_companies, *args, **kwargs):
        session = Session()
        try:
            user = session.query(Users).filter_by(IdUser=current_user).first()
            if not user:
                return jsonify({'message': 'User not found'}), 404

            for role in user.user_roles:
                app.logger.info(f"User role: {role.access_levels.AccessName}")
                app.logger.info(f"Company id: {owned_companies}")
                if role.IdCompany in owned_companies and user_has_access_level(user, get_access_level_by_name(session, "Company Owner"), session):
                    return f(current_user, owned_companies, *args, **kwargs)
            return jsonify({'message': 'Company owner access required'}), 403

        except Exception as e:
            app.logger.exception(f"Error checking company owner rights: {e}")
            return jsonify({'message': 'Error checking rights'}), 500
        finally:
            session.close()
    return decorated_function


def has_moderator_access(current_user, session):
    """Checks if the user has moderator or higher access."""
    user = session.query(Users).filter_by(IdUser=current_user).first()
    if not user:
        return False

    return user_has_access_level(user, get_access_level_by_name(session, "Moderator"), session)
