import os
from flask import Flask, request, jsonify, send_from_directory
from sqlalchemy import exc, func
from ..database.companies import Companies
from ..database.subscribers import Subscribers
from ..database.media import Media
from .. import app, Session
from ..user.functions import token_required

app: Flask


@app.get('/company/<int:id>')
@token_required
def get_company_info(current_user, id):
    session = Session()
    try:
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        # Count subscribers
        subscriber_count = session.query(func.count(Subscribers.IdSubscriber)).filter(Subscribers.IdCompany == id).scalar() or 0
        is_subscribed = False
        existing_subscription = session.query(Subscribers).filter_by(IdUser=current_user, IdCompany=id).first()
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
    finally:
        session.close()


@app.get('/company/<int:id>/logo')
@token_required
def get_company_preview(current_user, id):
    session = Session()
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
    finally:
        session.close()


@app.post('/company/<int:id>/subscribe')
@token_required
def subscribe_to_company(current_user, id):
    session = Session()
    try:
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        subscriber_count = session.query(func.count(Subscribers.IdSubscriber)).filter(Subscribers.IdCompany == id).scalar() or 0
        existing_subscription = session.query(Subscribers).filter_by(IdUser=current_user, IdCompany=id).first()
        if existing_subscription:
            return jsonify({'message': 'Already subscribed',
                            "is_subscribed": True,
                            "subscribers": subscriber_count}), 200

        new_subscription = Subscribers(IdUser=current_user, IdCompany=id)
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
    finally:
        session.close()


@app.post('/company/<int:id>/unsubscribe')
@token_required
def unsubscribe_from_company(current_user, id):
    session = Session()
    try:
        company = session.query(Companies).filter_by(IdCompany=id).first()
        if not company:
            return jsonify({'message': 'Company not found'}), 404

        subscriber_count = session.query(func.count(Subscribers.IdSubscriber)).filter(Subscribers.IdCompany == id).scalar() or 0
        existing_subscription = session.query(Subscribers).filter_by(IdUser=current_user, IdCompany=id).first()
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
    finally:
        session.close()


@app.get('/company/<int:id>/videos')
def get_company_videos(id):
    session = Session()
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
    finally:
        session.close()
