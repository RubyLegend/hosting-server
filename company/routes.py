import os
import json
from flask import Flask, request, jsonify, send_from_directory
from sqlalchemy import exc, func
from .functions import allowed_logo_file, get_unique_filepath_logo
from ..database.companies import Companies
from ..database.subscribers import Subscribers
from ..database.media import Media
from ..database.userRoles import UserRoles
from ..database.logos import CompanyLogo
from .. import app
from werkzeug.utils import secure_filename  # For secure filename
from ..user.functions import company_owner_level, token_required, after_token_required, get_access_level_by_name

app: Flask


@app.get('/company/<int:id>')
@token_required
@after_token_required
def get_company_info(current_user, session, id):
    try:
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        # Count subscribers
        subscriber_count = session.query(func.count(Subscribers.IdSubscriber)).filter(Subscribers.IdCompany == id).scalar() or 0
        is_subscribed = False
        existing_subscription = session.query(Subscribers).filter_by(IdUser=current_user.IdUser, IdCompany=id).first()
        if existing_subscription:
            is_subscribed = True

        company_info = {
            "id": company.IdCompany,
            "name": company.Name,
            "about": company.About,
            "owner": company.Owner if company.Owner else "Not set",
            "subscribers": subscriber_count,
            "is_subscribed": is_subscribed
        }

        return jsonify(company_info), 200

    except exc.SQLAlchemyError as e:  # Catch SQLAlchemy-specific exceptions
        app.logger.exception(f"Database error getting company info: {e}")
        return jsonify({'message': 'Database error'}), 500
    except Exception as e:
        app.logger.exception(f"Error getting company info: {e}")
        return jsonify({'message': 'Error getting company info'}), 500


@app.put('/company/<int:id>')
@token_required
@company_owner_level
@after_token_required
def update_company(user, session, id):
    """
    Updates a company's information (name, description, and/or image).

    Receives a multipart form data. The JSON data (name, description) is expected in the first part of the form.
    The image file (optional) is expected in the 'image' part of the form.

    Returns a 400 Bad Request if the request data is invalid.
    Returns a 404 Not Found if the company is not found.
    Returns a 403 Forbidden if the current user is not an admin.
    Returns a 500 Internal Server Error on database errors.
    """
    try:
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        if request.form:
            try:
                data = json.loads(list(request.form.values())[0])
                name = data.get('name')
                description = data.get('about')

                if name:
                    company.Name = name
                if description:
                    company.About = description

            except (json.JSONDecodeError, IndexError):
                return jsonify({'message': 'Invalid JSON data in form'}), 400

        if 'logo' in request.files:
            image_file = request.files['logo']
            if image_file.filename == '':
                return jsonify({'message': 'No selected image file'}), 400

            if image_file and allowed_logo_file(image_file.filename):
                image_filename = secure_filename(image_file.filename)
                image_path = os.path.join(app.config['LOGO_FOLDER'], image_filename)
                image_path = get_unique_filepath_logo(image_path, session)

                if company.companyLogo.LogoPath and company.companyLogo.IdCompanyLogo != 1: # Delete old logo if exists
                    try:
                        os.remove(company.companyLogo.LogoPath)
                    except FileNotFoundError:
                        pass
                    except Exception as e:
                        app.logger.exception(f"Error while removing old company logo: {e}")

                image_file.save(image_path)

                new_logo = CompanyLogo(
                    LogoPath=image_path
                )
                session.add(new_logo)
                session.commit()
                session.flush()
                id_logo = new_logo.IdCompanyLogo
                # Add company logo link
                prev_logo = company.companyLogo
                company.IdCompanyLogo = id_logo
                session.commit()
                session.delete(prev_logo)
            else:
                return jsonify({'message': 'Invalid image file type'}), 400
        session.commit()
        return jsonify({'message': 'Company updated successfully'}), 200

    except exc.SQLAlchemyError as e:
        session.rollback()
        app.logger.exception(f"Database error updating company: {e}")
        return jsonify({'message': 'Database error'}), 500
    except Exception as e:
        app.logger.exception(f"Error updating company: {e}")
        return jsonify({'message': 'Error updating company'}), 500


@app.get('/company/<int:id>/logo')
@token_required
@after_token_required
def get_company_preview(current_user, session, id):
    try:
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        if company.companyLogo:
            preview_path = company.companyLogo.LogoPath
            if os.path.exists(preview_path):
                return send_from_directory(os.path.dirname(preview_path), os.path.basename(preview_path))
            else:
                return jsonify({'message': 'Logo file not found'}), 404
        else:
            return jsonify({'message': 'No logo available'}), 404

    except Exception as e:
        app.logger.exception(f"Error getting logo: {e}")
        return jsonify({'message': 'Error getting logo'}), 500


@app.get('/company/<int:id>/moderators')
@token_required
@company_owner_level
@after_token_required
def get_company_moderators(user, session, id):
    """
    Retrieves a list of moderators for a given company.

    Returns a JSON array of moderator objects, each containing the moderator's ID and email.
    Returns a 404 Not Found if the company does not exist.
    Returns a 500 Internal Server Error on database errors.
    """
    try:
        # Check if the company exists
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        # Get the "Moderator" access level ID
        moderator_level = get_access_level_by_name(session, "Moderator")
        if not moderator_level:
            app.logger.error("Moderator Access Level not found in database")
            return jsonify({'message': 'Internal server error'}), 500

        users_in_company = company.user_roles

        moderators = [{'user_id': x.users.IdUser, 'Email': x.users.Email} for x in users_in_company if x.access_levels == moderator_level]

        return jsonify(moderators), 200

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error retrieving company moderators: {e}")
        return jsonify({'message': 'Internal server error'}), 500


@app.post('/company/<int:id>/moderators/<int:user_id>')
@token_required
@company_owner_level # Only admins can manage moderators
@after_token_required
def update_company_moderators(user, session, id, user_id):
    """
    Adds the moderators for a given company.

    Receives a JSON array of actions, where each action specifies a user ID and an action ('add' or 'remove').
    Returns a 400 Bad Request if the request data is invalid.
    Returns a 404 Not Found if the company or a user is not found.
    Returns a 403 Forbidden if the current user is not an admin.
    Returns a 500 Internal Server Error on database errors.
    """

    if user.IdUser == user_id:
        return jsonify("Cannot modify yourself, otherwise you will lose access."), 403

    try:
        moderator_level = get_access_level_by_name(session, "Moderator")
        if not moderator_level:
            app.logger.error("Moderator Access Level not found in database")
            return jsonify({'message': 'Internal server error'}), 500

        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        user_role = session.query(UserRoles).filter_by(IdUser=user_id, IdCompany=id).first()

        if not user_role:
            new_user_role = UserRoles(IdUser=user_id, IdCompany=id, IdAccessLevel=moderator_level.IdAccessLevel)
            session.add(new_user_role)
        else:
            user_role.IdAccessLevel = moderator_level.IdAccessLevel
            session.commit()

        session.commit()
        return jsonify({'message': 'Moderators updated successfully'}), 200

    except exc.SQLAlchemyError as e:
        session.rollback()
        app.logger.exception(f"Database error updating moderators: {e}")
        return jsonify({'message': 'Database error'}), 500
    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error updating moderators: {e}")
        return jsonify({'message': 'Error updating moderators'}), 500


@app.delete('/company/<int:id>/moderators')
@token_required
@company_owner_level # Only admins can manage moderators
@after_token_required
def delete_company_moderators(user, session, id):
    """
    Adds the moderators for a given company.

    Receives a JSON array of actions, where each action specifies a user ID and an action ('add' or 'remove').
    Returns a 400 Bad Request if the request data is invalid.
    Returns a 404 Not Found if the company or a user is not found.
    Returns a 403 Forbidden if the current user is not an admin.
    Returns a 500 Internal Server Error on database errors.
    """

    try:
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({'message': 'Invalid request data. Expected a JSON array.'}), 400

        moderator_level = get_access_level_by_name(session, "Moderator")
        if not moderator_level:
            app.logger.error("Moderator Access Level not found in database")
            return jsonify({'message': 'Internal server error'}), 500

        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        for item in data:
            user_role = session.query(UserRoles).filter_by(IdUser=item, IdCompany=id).first()

            if user_role and user_role.access_levels == moderator_level:
                session.delete(user_role)
            else:
                return jsonify({"message": "User does not have that role. No changes."}), 200

        session.commit()
        return jsonify({'message': 'Moderators updated successfully'}), 200

    except exc.SQLAlchemyError as e:
        session.rollback()
        app.logger.exception(f"Database error updating moderators: {e}")
        return jsonify({'message': 'Database error'}), 500
    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error updating moderators: {e}")
        return jsonify({'message': 'Error updating moderators'}), 500


@app.post('/company/<int:id>/subscribe')
@token_required
@after_token_required
def subscribe_to_company(current_user, session, id):
    try:
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        subscriber_count = session.query(func.count(Subscribers.IdSubscriber)).filter(Subscribers.IdCompany == id).scalar() or 0
        existing_subscription = session.query(Subscribers).filter_by(IdUser=current_user.IdUser, IdCompany=id).first()
        if existing_subscription:
            return jsonify({'message': 'Already subscribed',
                            "is_subscribed": True,
                            "subscribers": subscriber_count}), 200

        new_subscription = Subscribers(IdUser=current_user.IdUser, IdCompany=id)
        session.add(new_subscription)
        session.commit()
        return jsonify({'message': 'Subscribed successfully',
                        "is_subscribed": True,
                        "subscribers": subscriber_count+1}), 201

    except exc.IntegrityError as e:
        session.rollback()
        app.logger.exception(f"Database integrity error during subscription: {e}")
        return jsonify({'message': 'Database integrity error'}), 500
    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error subscribing to company: {e}")
        return jsonify({'message': 'Error subscribing to company'}), 500


@app.post('/company/<int:id>/unsubscribe')
@token_required
@after_token_required
def unsubscribe_from_company(current_user, session, id):
    try:
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        subscriber_count = session.query(func.count(Subscribers.IdSubscriber)).filter(Subscribers.IdCompany == id).scalar() or 0
        existing_subscription = session.query(Subscribers).filter_by(IdUser=current_user.IdUser, IdCompany=id).first()
        if not existing_subscription:
            return jsonify({'message': 'Not subscribed',
                            "is_subscribed": False,
                            "subcribers": subscriber_count}), 200

        session.delete(existing_subscription)
        session.commit()
        return jsonify({'message': 'Unsubscribed successfully',
                        "is_subscribed": False,
                        "subscribers": subscriber_count-1}), 201

    except exc.IntegrityError as e:
        session.rollback()
        app.logger.exception(f"Database integrity error during unsubscription: {e}")
        return jsonify({'message': 'Database integrity error'}), 500
    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error unsubscribing from company: {e}")
        return jsonify({'message': 'Error unsubscribing from company'}), 500


@app.get('/company/<int:id>/videos')
@token_required
@after_token_required
def get_company_videos(currrent_user, session, id):
    try:
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        videos = session.query(Media).filter_by(IdCompany=id).all()

        video_list = []
        for video in videos:
            tags = [{"id": tag.IdTag, "name": tag.TagName} for tag in video.tags]
            video_list.append({
                "id": video.IdMedia,
                "name": video.NameV,
                "description": video.DescriptionV,
                "upload_time": video.UploadTime.isoformat() if video.UploadTime else None,
                "tags": tags
            })

        return jsonify(video_list), 200

    except exc.SQLAlchemyError as e:
        app.logger.exception(f"Database error getting company videos: {e}")
        return jsonify({'message': 'Database error'}), 500
    except Exception as e:
        app.logger.exception(f"Error getting company videos: {e}")
        return jsonify({'message': 'Error getting company videos'}), 500
