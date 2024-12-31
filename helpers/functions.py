import jwt
import datetime
import redis
from ..database.accessLevels import AccessLevels
from ..database.users import Users
from flask import Flask, request, jsonify
from functools import wraps


def generate_token(app: Flask, redis_client: redis.Redis, user_id):
    """Generates a JWT token for a given user ID."""
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60),  # Token expiration time
        'iat': datetime.datetime.utcnow()  # Issued at time
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

    # Store the token in Redis with an expiration time
    redis_client.setex(f"user:{user_id}:token", datetime.timedelta(minutes=60), token)

    return token

def after_token_required(f):
    @wraps(f)
    def decorated_function(user, session, *args, **kwargs):
        try:
            result = f(user, session, *args, **kwargs)  # Call the original function
            return result
        finally:
            # Code to be executed AFTER the function call, ALWAYS
            session.close()

    return decorated_function


def token_required(app: Flask, redis_client: redis.Redis, Session):
    def token_required_outer(f):
        @wraps(f)
        def token_required_inner(*args, **kwargs):
            token = None
            if 'Authorization' in request.headers:
                token = request.headers['Authorization'].split(" ")[1]  # Extract token from Bearer header
            if not token:
                return jsonify({'message': 'Token is missing!'}), 401

            session = Session()
            try:
                # Check if the token exists in Redis
                user_id_bytes = redis_client.get(f"token:{token}")

                if user_id_bytes:
                    try:
                        user_id = int(user_id_bytes.decode('utf-8'))
                        user = session.query(Users).filter_by(IdUser=user_id).first() # Retrieve user object
                        if not user:
                            return jsonify({'message': 'User not found'}), 401

                    except Exception:
                        return jsonify({'message': 'Token is invalid!'}), 401

                    # Latest auth token
                    current_auth_token = redis_client.get(f"user:{user_id}:token")
                    if current_auth_token:
                        current_auth_token = current_auth_token.decode('utf-8')
                    else:
                        return jsonify({'message': 'Token has expired!'}), 401
                    if current_auth_token is not None and current_auth_token != token:
                        # If tokens mismatch - then we have second authentication
                        # Invalidating last one
                        redis_client.setex(f"token:{token}", datetime.timedelta(minutes=60), "INVALID")
                        redis_client.setex(f"token:{current_auth_token}", datetime.timedelta(minutes=30), str(user_id))
                        return jsonify({'message': 'Token has expired!'}), 401
                else:
                    try:
                        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                        user_id = data['user_id']
                        user = session.query(Users).filter_by(IdUser=user_id).first() # Retrieve user object
                        if not user or not user.IsActive:
                            return jsonify({'message': 'User not found'}), 401

                        redis_client.setex(f"user:{user_id}:token", datetime.timedelta(minutes=60), token)
                        redis_client.setex(f"token:{token}", datetime.timedelta(minutes=60), str(user_id))
                    except jwt.ExpiredSignatureError:
                        return jsonify({'message': 'Token has expired!'}), 401
                    except jwt.InvalidTokenError:
                        return jsonify({'message': 'Token is invalid!'}), 401

                return f(user, session, *args, **kwargs)

            except Exception as e:
                session.rollback()
                return jsonify({'message': 'Something went wrong!' + str(e)}), 500

        return token_required_inner
    return token_required_outer


def get_access_level_by_name(session, access_name):
    access_level_record = session.query(AccessLevels).filter_by(AccessName=access_name).first()
    return access_level_record if access_level_record else None

def user_has_access_level(user, required_level, session, weak_comparison=True):
    """Helper function to check if a user has at least the required access level."""
    for role in user.user_roles:  # Iterate through user's roles
        if role.access_levels == required_level:
            return True
        elif weak_comparison and role.access_levels.AccessLevel >= required_level.AccessLevel:
            return True
    return False

def admin_level(f):
    @wraps(f)
    def decorated_function(user, session, *args, **kwargs):
        try:
            if not user_has_access_level(user, get_access_level_by_name(session, "Admin"), session):
                return jsonify({'message': 'Admin access required'}), 403
            return f(user, session, *args, **kwargs)
        except Exception as e:
            return jsonify({'message': 'Error checking rights'}), 500
    return decorated_function


def user_or_admin_required(f):
    @wraps(f)
    def decorated_function(user, session, *args, **kwargs):
        user_id_to_update = kwargs.get('id')

        if user.IdUser != user_id_to_update and not user_has_access_level(user, get_access_level_by_name(session, "Admin"), session):
            return jsonify({'message': 'Forbidden. You can only access your own data or request for admin access.'}), 403

        return f(user, session, *args, **kwargs)
    return decorated_function



def moderator_level(f):
    @wraps(f)
    def decorated_function(user, session, *args, **kwargs):
        try:
            if not user_has_access_level(user, get_access_level_by_name(session, "Moderator"), session):
                return jsonify({'message': 'Moderator access required'}), 403
            return f(user, session, *args, **kwargs)
        except Exception as e:
            return jsonify({'message': 'Error checking rights'}), 500
    return decorated_function


def company_owner_level(f):
    @wraps(f)
    def decorated_function(user, session, *args, **kwargs): # Now accepts user object
        company_id = request.headers.get('X-idCompany')
        if not company_id:
            return jsonify({'message': 'Company id is missing'}), 400
        try:
            company_id = int(company_id)
        except ValueError:
            return jsonify({'message': 'Invalid company id'}), 400

        for role in user.user_roles: # Use user.user_roles
            if role.access_levels.AccessName == "Admin":
                return f(user, session, *args, **kwargs)
            if role.IdCompany == company_id and role.access_levels.AccessName == "Company Owner":
                return f(user, session, *args, **kwargs)
        return jsonify({'message': 'You are not the owner of this company'}), 403
    return decorated_function


def has_admin_access(user, session):
    """Checks if the user has admin access."""
    return user_has_access_level(user, get_access_level_by_name(session, "Admin"), session)


def has_moderator_access(user, session, weak_comparison=True):
    """Checks if the user has moderator or higher access."""
    return user_has_access_level(user, get_access_level_by_name(session, "Moderator"), session, weak_comparison)


def has_company_owner_access(user, session):
    """Checks if the user has company owner or higher access."""
    return user_has_access_level(user, get_access_level_by_name(session, "Company Owner"), session)
