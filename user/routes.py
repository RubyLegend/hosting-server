from .users import *
from flask import Flask, request, jsonify, redirect, url_for
import datetime
import bcrypt
from sqlalchemy import exc
from .. import app, redis_client, Session
from .functions import (
    generate_token,
    token_required,
    after_token_required,
    company_owner_level,
    has_admin_access,
    has_company_owner_access,
    has_moderator_access,
    get_access_level_by_name,
)
from ..database.users import Users
from ..database.companies import Companies
from ..database.accessLevels import AccessLevels
from ..database.userRoles import UserRoles

# Fix for pylsp
app: Flask


@app.post("/profile/login")
def login():
    """
    Logs a user into the application.
    ---
    tags:
      - User profile
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - User profilename
              - password
            properties:
              username:
                type: string
                description: The user's login username.
                example: "user"
              password:
                type: string
                description: The user's password.
                example: "password"
    responses:
      200:
        description: Login successful.
        content:
          application/json:
            schema:
              # $ref: "#/components/schemas/ProfileLoginResponse"
              type: object
              properties:
                user_id:
                  type: integer
                  description: The ID of the logged-in user.
                token:
                  type: string
                  description: The authentication token for the user.
                is_admin:
                  type: boolean
                  description: Whether the user has admin privileges.
                is_mod:
                  type: boolean
                  description: Whether the user has moderator privileges.
                is_comp_owner:
                  type: boolean
                  description: Whether the user is a company owner.
                message:
                  type: string
                  description: Success message.
      401:
        description: Invalid credentials or missing authorization header.
      500:
        description: Internal server error during login.
    """
    auth = request.get_json()

    if not auth or not auth.get("username") or not auth.get("password"):
        return jsonify({"token": None, "message": "Could not verify"}), 401

    username = auth.get("username")
    password = auth.get("password")

    session = Session()
    try:
        user = session.query(Users).filter_by(LoginUser=username).first()
        if (
            user
            and user.IsActive
            and bcrypt.checkpw(password.encode("utf-8"), user.Password.encode("utf-8"))
        ):
            token = generate_token(app, redis_client, user.IdUser)
            is_admin = has_admin_access(user, session)
            is_mod = has_moderator_access(user, session)
            is_comp_owner = has_company_owner_access(user, session)

            return (
                jsonify(
                    {
                        "user_id": user.IdUser,
                        "token": token,
                        "is_admin": is_admin,
                        "is_mod": is_mod,
                        "is_comp_owner": is_comp_owner,
                        "message": "success",
                    }
                ),
                200,
            )
        return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        app.logger.error(f"Error during login: {e}")  # Log the full error
        return jsonify({"message": "Login failed"}), 500
    finally:
        session.close()


@app.post("/profile/logout")
@token_required
@after_token_required
def logout(current_user, session):
    """
    Logs out a user from the application.
    ---
    tags:
        - User profile
    security:
      - bearerAuth: []
    responses:
      200:
        description: Logout successful.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  description: Logout success message.
      401:
        description: Unauthorized access (missing or invalid token).
    """
    token = request.headers["Authorization"].split(" ")[1]
    redis_client.delete(f"user:{current_user.IdUser}:token")
    redis_client.delete(f"token:{token}")
    return jsonify({"message": "Logged out successfully"}), 200


@app.get("/profile/")
def profile_redir():
    return redirect(url_for("profile"), 302)


@app.get("/profile")
@token_required
@after_token_required
def profile(current_user, session):
    """
    Retrieves the profile information of the currently logged-in user.
    ---
    tags:
        - User profile
    security:
      - bearerAuth: []
    responses:
      200:
        description: User profile retrieved successfully.
        content:
          application/json:
            schema:
              type: object
              properties:
                user_id:
                  type: integer
                  description: The ID of the user.
                login:
                  type: string
                  description: The user's login username.
                name:
                  type: string
                  description: The user's first name.
                surname:
                  type: string
                  description: The user's last name.
                is_admin:
                  type: boolean
                  description: Whether the user has admin privileges.
                mod:
                  type: array
                  description: List of companies the user moderates.
                  items:
                    type: object
                    properties:
                      company_id:
                        type: integer
                        description: The ID of the moderated company.
                      company_name:
                        type: string
                        description: The name of the moderated company.
                comp_owner:
                  type: array
                  description: List of companies the user owns.
                  items:
                    type: object
                    properties:
                      company_id:
                        type: integer
                        description: The ID of the owned company.
                      company_name:
                        type: string
                        description: The name of the owned company.
      404:
        description: User not found (should not happen with proper token authorization).
      500:
        description: Internal server error while retrieving user profile.
    """
    try:
        user = session.query(Users).filter_by(IdUser=current_user.IdUser).first()
        if not user:
            return (
                jsonify({"message": "User not found"}),
                404,
            )  # Should not happen if token_required is working correctly

        # subscriptions = []
        # for subscription in user.subscribers:
        #     company = session.query(Companies).filter_by(IdCompany=subscription.IdCompany).first()
        #     if company: # Handle cases where company might have been deleted
        #         subscriptions.append({
        #             "company_id": subscription.IdCompany,
        #             "company_name": company.Name
        #         })

        is_admin = has_admin_access(user, session)
        mod_access_level = get_access_level_by_name(session, "Moderator")
        mod = [
            {"company_id": x.companies.IdCompany, "company_name": x.companies.Name}
            for x in user.user_roles
            if x.access_levels == mod_access_level
        ]
        comp_owner_access_level = get_access_level_by_name(session, "Company Owner")
        comp_owner = [
            {"company_id": x.companies.IdCompany, "company_name": x.companies.Name}
            for x in user.user_roles
            if x.access_levels == comp_owner_access_level
        ]
        user_info = {
            "user_id": user.IdUser,
            "login": user.LoginUser,
            "name": user.NameUser,
            "surname": user.Surname,
            "is_admin": is_admin,
            "mod": mod,
            "comp_owner": comp_owner,
            # "subscriptions": subscriptions
        }

        return jsonify(user_info), 200

    except exc.SQLAlchemyError as e:
        app.logger.exception(f"Database error getting user profile: {e}")
        return jsonify({"message": "Database error"}), 500
    except Exception as e:
        app.logger.exception(f"Error getting user profile: {e}")
        return jsonify({"message": "Error getting user profile"}), 500


@app.get("/profile/subscriptions")
@token_required
@after_token_required
def get_profile_subscriptions(current_user, session):
    """
    Retrieves a list of companies the currently logged-in user is subscribed to.
    ---
    tags:
        - User profile
    security:
      - bearerAuth: []
    responses:
      200:
        description: List of user subscriptions retrieved successfully.
        content:
          application/json:
            schema:
              type: array
              items:
                type: object
                properties:
                  company_id:
                    type: integer
                    description: The ID of the subscribed company.
                  company_name:
                    type: string
                    description: The name of the subscribed company.
      404:
        description: User not found (should not happen with proper token authorization).
      500:
        description: Internal server error while retrieving user subscriptions.
    """
    try:
        user = session.query(Users).filter_by(IdUser=current_user.IdUser).first()
        if not user:
            return (
                jsonify({"message": "User not found"}),
                404,
            )  # Should not happen if token_required is working correctly

        subscriptions = []
        for subscription in user.subscribers:
            company = (
                session.query(Companies)
                .filter_by(IdCompany=subscription.IdCompany)
                .first()
            )
            if company:  # Handle cases where company might have been deleted
                subscriptions.append(
                    {"company_id": subscription.IdCompany, "company_name": company.Name}
                )

        return jsonify(subscriptions), 200

    except exc.SQLAlchemyError as e:
        app.logger.exception(f"Database error getting user profile: {e}")
        return jsonify({"message": "Database error"}), 500
    except Exception as e:
        app.logger.exception(f"Error getting user profile: {e}")
        return jsonify({"message": "Error getting user profile"}), 500


@app.post("/profile/register")
def register():
    """
    Registers a new user in the application.
    ---
    tags:
        - User profile
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
              loginUser:
                type: string
                description: The user's login username.
              nameUser:
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
              about:
                type: string
                description: A short description about the user.
              password:
                type: string
                description: The user's password.
              passwordAgain:
                type: string
                description: The user's password repeated for confirmation.
    responses:
      201:
        description: User registered successfully.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  description: Registration success message.
      400:
        description: Bad request (missing required fields, passwords do not match, or username already exists).
      500:
        description: Internal server error during registration.
    """
    data = request.get_json()
    email = data.get("email")
    loginUser = data.get("loginUser")
    nameUser = data.get("nameUser")
    surname = data.get("surname")
    patronymic = data.get("patronymic")
    birthday = data.get("birthday")
    registerTime = datetime.datetime.utcnow()
    password = data.get("password")
    passwordAgain = data.get("passwordAgain")

    if not loginUser or not password:
        return jsonify({"message": "Username and password are required"}), 400

    if password != passwordAgain:
        return jsonify({"message": "Passwords do not match"}), 400

    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )

    session = Session()
    try:
        new_user = Users(
            Email=email,
            LoginUser=loginUser,
            NameUser=nameUser,
            Surname=surname,
            Patronymic=patronymic,
            Birthday=birthday,
            RegisterTime=registerTime,
            Password=hashed_password,
        )
        session.add(new_user)
        session.commit()
        session.flush()

        # Add default user role
        user_level = session.query(AccessLevels).filter_by(AccessName="User").first()
        if not user_level:
            app.logger.error("User access level not found in database. Critical error!")
            session.rollback()
            return jsonify({"message": "Internal server error"}), 500

        new_user_role = UserRoles(
            IdUser=new_user.IdUser, IdAccessLevel=user_level.IdAccessLevel
        )
        session.add(new_user_role)

        session.commit()
        return jsonify({"message": "User registered successfully"}), 201
    except exc.IntegrityError as e:  # Catch IntegrityError (most common MySQL errors)
        session.rollback()
        app.logger.error(
            f"IntegrityError during registration: {e}"
        )  # Log the full error
        if "Duplicate entry" in str(e):
            return (
                jsonify({"message": "Username already exists"}),
                400,
            )  # More specific error
        else:
            return (
                jsonify({"message": "Registration failed due to database error"}),
                500,
            )  # Generic message
    except Exception as e:  # Catch other potential exceptions
        session.rollback()
        app.logger.exception(
            "An unexpected error occurred during registration:"
        )  # Log full traceback
        return jsonify({"message": "Registration failed"}), 500
    finally:
        session.close()
