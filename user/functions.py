import jwt
import datetime
import redis
from .. import app, redis_client
from flask import Flask, request, jsonify
from functools import wraps
import redis

app: Flask
redis_client: redis.Redis

def generate_token(user_id):
    """Generates a JWT token for a given user ID."""
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30),  # Token expiration time
        'iat': datetime.datetime.utcnow()  # Issued at time
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

    # Store the token in Redis with an expiration time
    redis_client.setex(f"user:{user_id}:token", datetime.timedelta(minutes=30), token)

    return token

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]  # Extract token from Bearer header
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            # Check if the token exists in Redis
            user_id_bytes = redis_client.get(f"token:{token}")

            if user_id_bytes:
                try:
                    user_id = int(user_id_bytes.decode('utf-8'))
                except Exception:
                    return jsonify({'message': 'Token is invalid!'}), 401

                # Latest auth token
                current_auth_token = redis_client.get(f"user:{user_id}:token").decode("utf-8")
                if current_auth_token != token:
                    # If tokens mismatch - then we have second authentication
                    # Invalidating last one
                    redis_client.setex(f"token:{token}", datetime.timedelta(minutes=30), "INVALID")
                    redis_client.setex(f"token:{current_auth_token}", datetime.timedelta(minutes=30), str(user_id))
                    return jsonify({'message': 'Token has expired!'}), 401
            else:
                try:
                    data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                    user_id = data['user_id']
                    redis_client.setex(f"user:{user_id}:token", datetime.timedelta(minutes=30), token)
                    redis_client.setex(f"token:{token}", datetime.timedelta(minutes=30), str(user_id))
                except jwt.ExpiredSignatureError:
                    return jsonify({'message': 'Token has expired!'}), 401
                except jwt.InvalidTokenError:
                    return jsonify({'message': 'Token is invalid!'}), 401
            
        except Exception as e:
            return jsonify({'message': 'Something went wrong!' + str(e)}), 500

        return f(user_id, *args, **kwargs)
    return decorated
