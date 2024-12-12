from flask import Flask, request, jsonify, redirect, url_for
from .. import app, redis_client
from .functions import generate_token, token_required

# Fix for pylsp
app: Flask


@app.post("/profile/login")
def login():
    auth = request.get_json()

    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'token': None, 'message': 'Could not verify'}), 401

    # In real app you should query database here
    if auth.get('username') == "test" and auth.get('password') == "password":
        token = generate_token(1)  # Replace 1 with actual user_id
        return jsonify({'token': token, "message": "success"}), 200

    return jsonify({'token': None, 'message': 'Invalid credentials'}), 401


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
