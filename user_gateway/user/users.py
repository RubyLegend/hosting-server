from .. import app, redis_client, Session
from ..database.users import Users
from ..helpers.functions import (token_required, company_owner_level,
    user_or_admin_required, user_has_access_level,
    get_access_level_by_name, after_token_required)
from flask import Flask, request, jsonify
from sqlalchemy.exc import IntegrityError
import bcrypt
import redis

app: Flask
redis_client: redis.Redis


@app.get('/users/search')
@token_required(app, redis_client, Session)
@company_owner_level
@after_token_required
def search_users(user, session):
    """
Searches for users based on their email (company owners and higher).

Accepts a query parameter 's' containing the search string.
Returns a JSON array of user objects matching the search string.
Returns an empty array if no users are found.
Returns a 400 Bad Request if the 's' parameter is missing.
Returns a 500 Internal Server Error on database errors.
---
tags:
    - Users
security:
  - bearerAuth: []
parameters:
  - in: query
    name: s
    type: string
    description: The search string to filter users by email (case-insensitive substring match).
  - in: header
    name: X-idCompany
    description: ID of a company, for which the search will be performed
    type: integer
responses:
  200:
    description: User search results. Returns an empty array if no users are found.
    content:
      application/json:
        schema:
          type: array
          items:
            type: object
            properties:
              user_id:
                type: integer
                description: The ID of the matching user.
              Email:
                type: string
                format: email
                description: The email of the matching user.
  400:
    description: Bad request (search parameter "s" is missing).
  500:
    description: Internal server error during user search.
"""
    search_string = request.args.get('s')

    if not search_string:
        return jsonify([{}])

    try:
        users = session.query(Users).filter(Users.Email.like(f"%{search_string}%")).all()

        user_list = [{'user_id': user.IdUser, 'Email': user.Email} for user in users]
        return jsonify(user_list), 200

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error searching users: {e}")
        return jsonify({'message': 'Internal server error'}), 500

@app.get("/users/<int:id>")
@token_required(app, redis_client, Session)
@after_token_required
def get_user_info(user, session, id):
    """
Retrieves information about a specific user.
---
security:
  - bearerAuth: []
tags:
  - Users
parameters:
  - in: path
    name: id
    type: integer
    required: true
    description: The ID of the user to retrieve information for.
responses:
  200:
    description: User information retrieved successfully.
    content:
      application/json:
        schema:
          type: object
          properties:
            user_id:
              type: integer
              description: The ID of the user.
            email:
              type: string
              format: email
              description: The email address of the user.
            name:
              type: string
              description: The first name of the user.
            surname:
              type: string
              description: The last name of the user.
            patronymic:
              type: string
              description: The patronymic of the user.
            login:
              type: string
              description: The login username of the user.
            birthday:
              type: string
              format: date-time
              description: The birthday of the user in ISO 8601 format.
  403:
    description: Forbidden. User is not authorized to access user information (requires admin access).
  404:
    description: User not found.
  500:
    description: Internal server error.
"""
    try:
        user_to_get = session.query(Users).filter_by(IdUser=id).first()
        if not user_to_get:
            return jsonify({'message': 'User not found'}), 404

        user_info = { # Construct the user info dictionary
            'user_id': user_to_get.IdUser,
            'email': user_to_get.Email,
            'name': user_to_get.NameUser,
            'surname': user_to_get.Surname,
            'patronymic': user_to_get.Patronymic,
            'login': user_to_get.LoginUser,
            'birthday': user_to_get.Birthday.isoformat() if user_to_get.Birthday else None,
        }

        return jsonify(user_info), 200

    except Exception as e:
        app.logger.exception(f"Error getting user info: {e}")
        return jsonify({'message': 'Internal server error'}), 500


@app.put('/users/<int:id>')
@token_required(app, redis_client, Session)
@user_or_admin_required
@after_token_required
def update_user(user, session, id):
    """
Updates user information. Accessible to the user themselves or an admin.
---
security:
  - bearerAuth: []
tags:
  - Users
parameters:
  - in: path
    name: id
    type: integer
    required: true
    description: The ID of the user to retrieve information for.
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          email:
            type: string
            format: email
            description: The user's email address.
          login:
            type: string
            description: The user's login username.
          name:
            type: string
            description: The user's first name.
          surname:
            type: string
            description: The user's last name.
          patronymic:
            type: string
            description: The user's patronymic (middle name).
          birthday:
            type: string
            format: date
            description: The user's birthday (YYYY-MM-DD).
          oldPassword:
            type: string
            description: Current user's password.
          newPassword:
            type: string
            description: New user's password.
responses:
  200:
    description: User information retrieved successfully.
    content:
      application/json:
        schema:
          type: object
          properties:
            user_id:
              type: integer
              description: The ID of the user.
            email:
              type: string
              format: email
              description: The email address of the user.
            name:
              type: string
              description: The first name of the user.
            surname:
              type: string
              description: The last name of the user.
            patronymic:
              type: string
              description: The patronymic of the user.
            login:
              type: string
              description: The login username of the user.
            birthday:
              type: string
              format: date-time
              description: The birthday of the user in ISO 8601 format.
  400:
    description:
      - No data provided for JSON.
      - Missmatch between old password entered and in database.
      - Entered only new password or old password."
  403:
    description: 
      - Forbidden. User is not authorized to access this user's' information (requires admin access).
      - Forbidden. Username is already taken.
  404:
    description: User not found.
  500:
    description: Internal server error.
"""
    try:
        user_to_update = session.query(Users).filter_by(IdUser=id).first()
        if not user_to_update:
            return jsonify({'message': 'User not found'}), 404

        data = request.get_json()

        if not data:
            return jsonify({'message': 'No data provided for update'}), 400

        # Update user fields (except password)
        user_to_update.Email = data.get('email', user_to_update.Email)
        user_to_update.NameUser = data.get('name', user_to_update.NameUser)
        user_to_update.Surname = data.get('surname', user_to_update.Surname)
        user_to_update.Patronymic = data.get('patronymic', user_to_update.Patronymic)
        user_to_update.LoginUser = data.get('login', user_to_update.LoginUser)
        user_to_update.Birthday = data.get('birthday', user_to_update.Birthday.isoformat())

        # Password update logic
        old_password = data.get('oldPassword')
        new_password = data.get('newPassword')

        am_i_admin = user_has_access_level(user, get_access_level_by_name(session, "Admin"), session)

        if old_password and new_password and not am_i_admin:
            if bcrypt.checkpw(old_password.encode('utf-8'), user_to_update.Password.encode('utf-8')):
                user_to_update.Password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            else:
                return jsonify({'message': 'Incorrect current password'}), 400
        elif new_password and am_i_admin:
            user_to_update.Password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        elif old_password or new_password:
            return jsonify({'message': 'Both old and new passwords are required'}), 400

        session.commit()
        return jsonify({'message': 'User updated successfully'}), 200

    except IntegrityError as e:
        return jsonify({"message": "This username is already taken."}), 403

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error updating user: {e}")
        return jsonify({'message': 'Internal server error'}), 500


@app.delete('/users/<int:id>')
@token_required(app, redis_client, Session)
@user_or_admin_required
@after_token_required
def delete_user(user, session, id):
    """
    Marks a user as inactive (soft delete). Accessible to the user themselves or an admin.
    ---
    security:
      - bearerAuth: []
    tags:
      - Users
    parameters:
      - in: path
        name: id
        type: integer
        required: true
        description: The ID of the user to mark as inactive.
    responses:
      200:
        description: User marked as inactive successfully.
      403:
        description: Forbidden. You can only delete your own profile or require admin access.
      404:
        description: User not found.
      500:
        description: Internal server error.
    """
    try:
        user_to_delete = session.query(Users).filter_by(IdUser=id).first()
        if not user_to_delete:
            return jsonify({'message': 'User not found'}), 404

        user_to_delete.IsActive = False  # Soft delete: Mark as inactive
        session.commit()
        
        # Retrieving current user token, if exist
        current_token = redis_client.get(f"user:{user_to_delete.IdUser}:token")
        if current_token:
            redis_client.delete(f"user:{user_to_delete.IdUser}:token")
            redis_client.delete(f"token:{current_token.decode('utf-8')}")

        return jsonify({'message': 'User deleted successfully'}), 200

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error marking user as inactive: {e}")
        return jsonify({'message': 'Internal server error'}), 500
