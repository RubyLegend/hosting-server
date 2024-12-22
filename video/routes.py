from flask import Flask, Response, request, jsonify
import datetime
import os
import re
import json
import urllib
from werkzeug.utils import secure_filename  # For secure filename
from .. import app, Session, redis_client
from ..user.functions import token_required
from ..database.media import Media
from ..database.tags import Tags
from ..database.ratings import Ratings
from ..database.ratingTypes import RatingTypes
from ..database.viewHistory import ViewHistory
from .functions import allowed_file, get_unique_filepath, generate_temporary_link, get_rating_counts, get_chunk
from sqlalchemy import exc, func, distinct

app: Flask

@app.post('/video/upload')
@token_required  # Protect this endpoint
def upload_video(current_user):  # current_user is passed from decorator
    if 'file' not in request.files:
        app.logger.exception(f"Video: No Video part")
        return jsonify({'message': 'No video part'}), 400
    file = request.files['file']
    if file.filename == '':
        app.logger.exception(f"Video: No selected file")
        return jsonify({'message': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            original_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            filepath = get_unique_filepath(original_filepath, Session())
            try:
                app.logger.info(f"File upload started. Future filename: {filename}")
                with open(filepath, 'wb') as f:
                    while True:
                        chunk = file.read(4096)  # Read in chunks
                        if not chunk:
                            break
                        f.write(chunk)
            except Exception as e:
                app.logger.exception(f"Video: Failed to read file from client")
                return jsonify({'message': str(e)}), 500

            data = json.loads(list(request.form.values())[0])
            name = data.get('name')
            description = data.get('description')
            id_company = data.get('idCompany')
            tags = data.get('tags') # Get the tags string

            if not name:
                os.remove(filepath)
                app.logger.exception(f"Video: Video name not found")
                return jsonify({'message': 'Video name is required'}), 400

            session = Session()
            try:
                new_media = Media(
                    IdCompany=id_company,
                    NameV=name,
                    DescriptionV=description,
                    UploadTime=datetime.datetime.now(),
                    VideoPath=filepath
                )
                session.add(new_media)
                session.commit()
                session.flush()

                if tags and len(tags) != 0:  # If tags were provided
                    tags_list = [int(tag) for tag in tags]  # Split and clean tags
                    for tag_id in tags_list:
                        tag = session.query(Tags).filter_by(IdTag=tag_id).first()
                        if not tag:
                            session.rollback()
                            os.remove(filepath)
                            app.logger.exception(f"Video: Video tag not found")
                            return jsonify({'message': 'Tag not found'}), 400

                        new_media.tags.append(tag)
                session.commit()

                return jsonify({'message': 'File uploaded successfully'}), 201
            except Exception as e:
                session.rollback()
                os.remove(filepath)
                app.logger.exception(f"Database error during video upload: {e}")
                return jsonify({'message': 'Error saving to database'}), 500
            finally:
                session.close()

        except Exception as e:
            app.logger.exception(f"Error during video upload: {e}")
            return jsonify({'message': 'Error uploading file'}), 500
    else:
        app.logger.exception(f"Video: Invalid file type")
        return jsonify({'message': 'Invalid file type'}), 400


@app.route('/video/get/<int:id>')
@token_required
def get_video_link(current_user, id):
    session = Session()
    try:
        media = session.query(Media).filter_by(IdMedia=id).first()
        if not media:
            return jsonify({'message': 'Video not found'}), 404

        # View History Logic
        view_history_entry = session.query(ViewHistory).filter_by(IdUser=current_user, IdMedia=id).first()
        if view_history_entry:
            view_history_entry.ViewTime = datetime.datetime.now()
            view_history_entry.ViewCount += 1
        else:
            new_view_history = ViewHistory(
                IdUser=current_user,
                IdMedia=id,
                ViewTime=datetime.datetime.now()
            )
            session.add(new_view_history)
        session.commit()
        # End of View History Logic

        # Get total view count
        total_views = session.query(func.sum(ViewHistory.ViewCount)).filter(ViewHistory.IdMedia == id).scalar()
        total_views = int(total_views) if total_views is not None else 0 # Explicitly convert to int

        # Get unique viewer count
        unique_viewers = session.query(func.count(distinct(ViewHistory.IdUser))).filter(ViewHistory.IdMedia == id).scalar()
        unique_viewers = int(unique_viewers) if unique_viewers is not None else 0 # Explicitly convert to int

        temp_link = generate_temporary_link(id, media.NameV)

        tags = [{"id": tag.IdTag, "name": tag.TagName} for tag in media.tags] # Get tags
        likes, dislikes, user_rating_value = get_rating_counts(session, id, current_user)

        media_info = {
            "name": media.NameV,
            "description": media.DescriptionV,
            "temporary_link": temp_link,
            "tags": tags,
            'likes': likes,
            'dislikes': dislikes,
            'user_rating': user_rating_value,
            "total_views": total_views,  # Added total view count
            "unique_viewers": unique_viewers  # Added unique viewer count
        }

        return jsonify(media_info), 200

    except Exception as e:
        app.logger.exception(f"Error generating temporary link: {e}")
        return jsonify({'message': 'Error generating link'}), 500
    finally:
        session.close()


@app.post('/video/rating/<int:id>')
@token_required
def rate_video(current_user, id):
    data = request.get_json()
    rating_value = data.get('rating')  # 0, 1, or -1

    if rating_value is None:
        return jsonify({'message': 'Rating value is required'}), 400

    if rating_value not in (0, 1, -1):
        return jsonify({'message': 'Invalid rating value. Must be 0, 1, or -1'}), 400

    session = Session()
    try:
        media = session.query(Media).filter_by(IdMedia=id).first()
        if not media:
            return jsonify({'message': 'Video not found'}), 404

        existing_rating = session.query(Ratings).filter_by(IdUser=current_user, IdMedia=id).first()

        if rating_value == 0:  # Remove rating
            if existing_rating:
                session.delete(existing_rating)
                session.commit()
                likes, dislikes, user_rating_value = get_rating_counts(session, id, current_user)
                return jsonify({
                    'message': 'Rating removed',
                    'likes': likes,
                    'dislikes': dislikes,
                    'user_rating': user_rating_value
                }), 200
            else:
                return jsonify({'message': 'No rating to remove'}), 200 # Nothing to remove

        rating_type = None
        if rating_value == 1:
            rating_type = session.query(RatingTypes).filter_by(NameRating="Like").first()
        elif rating_value == -1:
            rating_type = session.query(RatingTypes).filter_by(NameRating="Dislike").first()

        if not rating_type:
            return jsonify({'message': 'Rating types not configured correctly'}), 500

        if existing_rating:
            if existing_rating.IdRatingType == rating_type.IdRatingType:
                return jsonify({'message': 'Rating cannot be the same as before.'}), 400

            existing_rating.IdRatingType = rating_type.IdRatingType
            existing_rating.RatingTime = datetime.datetime.now()
            session.commit()
            likes, dislikes, user_rating_value = get_rating_counts(session, id, current_user)
            return jsonify({
                'message': 'Rating updated',
                'likes': likes,
                'dislikes': dislikes,
                'user_rating': user_rating_value
            }), 201

        new_rating = Ratings(
            IdUser=current_user,
            IdMedia=id,
            IdRatingType=rating_type.IdRatingType,
            RatingTime=datetime.datetime.now()
        )
        session.add(new_rating)
        session.commit()
        likes, dislikes, user_rating_value = get_rating_counts(session, id, current_user)
        return jsonify({
            'message': 'Rating added',
            'likes': likes,
            'dislikes': dislikes,
            'user_rating': user_rating_value
        }), 201

    except exc.IntegrityError as e:
        session.rollback()
        app.logger.exception(f"Database integrity error during rating: {e}")
        return jsonify({'message': 'Database integrity error'}), 500
    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error adding/updating rating: {e}")
        return jsonify({'message': 'Error adding/updating rating'}), 500
    finally:
        session.close()


@app.route('/stream/<link_id>/<filename>') # Added filename parameter
def stream_video_from_link(link_id, filename):
    """Streams the video from a temporary link."""
    media_id_bytes = redis_client.get(f"temp_link:{link_id}:{filename}")
    if not media_id_bytes:
        return jsonify({'message': 'Invalid or expired link'}), 404

    media_id = int(media_id_bytes.decode('utf-8'))

    session = Session()
    try:
        media = session.query(Media).filter_by(IdMedia=media_id).first()
        if not media:
            return jsonify({'message': 'Video not found'}), 404

        filepath = media.VideoPath

        if not os.path.exists(filepath):
            return jsonify({'message': 'Video file not found on server'}), 404

        # Decode the filename from the URL
        decoded_filename = urllib.parse.unquote(filename)
        range_header = request.headers.get('Range', None)
        byte1, byte2 = 0, None
        
        if range_header:
            match = re.search(r'(\d+)-(\d*)', range_header)
            groups = match.groups()

            if groups[0]:
                byte1 = int(groups[0])
            if groups[1]:
                byte2 = int(groups[1])

        chunk, start, length, file_size = get_chunk(byte1, byte2, filepath)

        resp = Response(chunk, 206, content_type="video/mp4", mimetype="video/mp4", direct_passthrough=True)  # Set Content-Disposition header
        resp.headers.add('Content-Range', 'bytes {0}-{1}/{2}'.format(start, start + length - 1, file_size))
        return resp
    except Exception as e:
        app.logger.exception(f"Error streaming video: {e}")
        return jsonify({'message': 'Error streaming video'}), 500
    finally:
        session.close()


@app.get('/video')
def get_all_videos():
    session = Session()
    try:
        videos = session.query(Media).all()
        video_list = []
        for video in videos:
            tags = [{"id": tag.IdTag, "name": tag.TagName} for tag in video.tags]
            video_list.append({
                "id": video.IdMedia,
                "name": video.NameV,
                "description": video.DescriptionV,
                "upload_time": video.UploadTime.isoformat() if video.UploadTime else None,
                "tags": tags,
                "company_id": video.IdCompany
            })
        return jsonify(video_list), 200
    except Exception as e:
        app.logger.exception(f"Error retrieving videos: {e}")
        return jsonify({'message': 'Error retrieving videos'}), 500
    finally:
        session.close()
