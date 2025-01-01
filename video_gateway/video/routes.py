from flask import Flask, Response, request, jsonify, send_from_directory, redirect, url_for
import datetime
import os
import re
import json
import urllib
import mimetypes
from collections import Counter
from werkzeug.utils import secure_filename  # For secure filename
from . import tags, comments, reports
from .. import app, Session, redis_client, ALLOWED_VIDEO_EXTENSIONS, ALLOWED_AUDIO_EXTENSIONS
from ..helpers.functions import token_required, after_token_required, company_owner_level
from ..database.media import Media
from ..database.mediaPreview import MediaPreview
from ..database.tags import Tags
from ..database.ratings import Ratings
from ..database.ratingTypes import RatingTypes
from ..database.viewHistory import ViewHistory
from .functions import (allowed_file, allowed_preview_file,
                        get_unique_filepath, generate_temporary_link,
                        get_rating_counts, get_chunk, get_unique_filepath_preview,
                        recommendation_generator)
from sqlalchemy import exc, func, distinct, or_, and_

app: Flask

@app.post('/video/upload')
@token_required(app, redis_client, Session)  # Protect this endpoint
@company_owner_level
@after_token_required
def upload_video(current_user, session):  # current_user is passed from decorator
    """
Uploads a video to the application.
---
tags:
  - Video
security:
  - bearerAuth: []
requestBody:
  required: true
  content:
    multipart/form-data:
      schema:
        type: object
        properties:
          file:
            type: string
            description: The video file to upload. (form-data)
            format: binary
          preview:
            type: string
            description: The preview image for the video (optional, form-data).
            format: binary
          name:
            type: string
            description: The name of the video. (form-data)
          description:
            type: string
            description: A description of the video. (form-data)
          idCompany:
            type: integer
            description: The ID of the company the video belongs to. (form-data)
          tags:
            type: string
            description: A comma-separated list of tag IDs to associate with the video. (form-data)
responses:
  201:
    description: Video uploaded successfully.
  400:
    description: Bad request (missing video file, missing video name, invalid file type, or invalid tag).
  500:
    description: Internal server error during video upload.
"""

    if 'file' not in request.files:
        app.logger.exception(f"Video: No Video part")
        return jsonify({'message': 'No video part'}), 400
    file = request.files['file']
    if file.filename == '':
        app.logger.exception(f"Video: No selected file")
        return jsonify({'message': 'No selected file'}), 400
    if not file or not allowed_file(file.filename):
        app.logger.exception(f"Video: Invalid file type")
        return jsonify({'message': 'Invalid file type'}), 400

    if 'preview' in request.files:
        preview_file = request.files['preview'] # Get preview file
    else:
        preview_file = None

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

        new_preview_file = False
        if preview_file:
            if allowed_preview_file(preview_file.filename):  # Proceed only if file has correct extension
                # Save preview
                preview_filename = secure_filename(preview_file.filename)
                preview_path = os.path.join(app.config['PREVIEW_FOLDER'], preview_filename)
                preview_path = get_unique_filepath_preview(preview_path, Session())
                preview_file.save(preview_path)
                new_preview_file = True
            else:  # If preview file is not of allowed type
                file_extension = os.path.splitext(filename)[1][1:].lower()
                if file_extension in ALLOWED_VIDEO_EXTENSIONS:
                    id_media_preview = 1
                elif file_extension in ALLOWED_AUDIO_EXTENSIONS:
                    id_media_preview = 2
        else:  # If preview file is not provided
            file_extension = os.path.splitext(filename)[1][1:].lower()
            if file_extension in ALLOWED_VIDEO_EXTENSIONS:
                id_media_preview = 1
            elif file_extension in ALLOWED_AUDIO_EXTENSIONS:
                id_media_preview = 2

        try:
            if new_preview_file:
                new_preview = MediaPreview(
                    PreviewPath=preview_path
                )
                session.add(new_preview)
                session.commit()
                session.flush()
                id_media_preview = new_preview.IdMediaPreview

            new_media = Media(
                IdCompany=id_company,
                NameV=name,
                DescriptionV=description,
                UploadTime=datetime.datetime.now(),
                VideoPath=filepath,
                IdMediaPreview=id_media_preview
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
                        app.logger.exception("Video: Video tag not found")
                        return jsonify({'message': 'Tag not found'}), 400

                    new_media.tags.append(tag)
            session.commit()

            return jsonify({'message': 'File uploaded successfully'}), 201
        except Exception as e:
            session.rollback()
            os.remove(filepath)
            app.logger.exception(f"Database error during video upload: {e}")
            return jsonify({'message': 'Error saving to database'}), 500

    except Exception as e:
        app.logger.exception(f"Error during video upload: {e}")
        return jsonify({'message': 'Error uploading file'}), 500


@app.put('/video/<int:id>')
@token_required(app, redis_client, Session)
@company_owner_level
@after_token_required
def update_video(user, session, id):
    """
Updates a video's information (name, description, tags, and/or preview).

Receives multipart form data. The JSON data (name, description, tags) is expected in the first part of the form.
The preview image file (optional) is expected in the 'preview' part of the form.

Returns a 400 Bad Request if the request data is invalid.
Returns a 404 Not Found if the video is not found.
Returns a 500 Internal Server Error on database errors.
---
security:
  - bearerAuth: []
tags:
  - Video
parameters:
  - in: path
    name: id
    type: integer
    required: true
    description: The ID of the video to update.
requestBody:
  required: false  # Because preview is optional
  content:
    multipart/form-data:
      schema:
        type: object
        properties:
          name:
            type: string
            description: The updated name for the video.
          description:
            type: string
            description: The updated description for the video.
          tags:
            type: string
            description: A comma-separated list of tag IDs to associate with the video.
          preview:
            type: string
            description: The updated preview image for the video (optional, form-data).
            format: binary
      examples:
        example-update-name-description:
          name: My Updated Video Title
          description: This is an updated description for the video.
        example-update-tags:
          tags: "123, 456"  # Example comma-separated tag IDs

responses:
  200:
    description: Video updated successfully.
  400:
    description: Bad request (video not found, invalid JSON data, invalid tag format, or invalid preview file type).
  404:
    description: Video not found.
  500:
    description: Internal server error during video update.
"""
    try:
        video = session.query(Media).filter_by(IdMedia=id).first()
        if not video:
            return jsonify({'message': 'Video not found'}), 404

        # if video.IdCompany != request.headers.get("X-idCompany"):
        #     return jsonify({'message': 'video not found'}), 404

        if request.form:
            try:
                data = json.loads(list(request.form.values())[0])
                name = data.get('name')
                description = data.get('description')
                tags = data.get('tags')

                if name:
                    video.NameV = name
                if description:
                    video.DescriptionV = description

                if tags:
                    try:
                        tags_list = [int(tag) for tag in tags]
                    except ValueError:
                        return jsonify({'message': 'Invalid tag format. Tags must be integers.'}), 400
                    
                    # Clear existing tags and add new ones
                    video.tags = []
                    for tag_id in tags_list:
                        tag = session.query(Tags).filter_by(IdTag=tag_id).first()
                        if not tag:
                            return jsonify({'message': f'Tag with ID {tag_id} not found'}), 400
                        video.tags.append(tag)


            except (json.JSONDecodeError, IndexError):
                return jsonify({'message': 'Invalid JSON data in form'}), 400

        if 'preview' in request.files:
            preview_file = request.files['preview']
            if preview_file.filename == '':
                return jsonify({'message': 'No selected preview file'}), 400

            if preview_file and allowed_preview_file(preview_file.filename):
                preview_filename = secure_filename(preview_file.filename)
                preview_path = os.path.join(app.config['PREVIEW_FOLDER'], preview_filename)
                preview_path = get_unique_filepath_preview(preview_path, session)

                if video.IdMediaPreview and video.IdMediaPreview != 1 and video.IdMediaPreview != 2:  # Check if video has preview
                    old_preview = session.query(MediaPreview).filter_by(IdMediaPreview=video.IdMediaPreview).first()
                    if old_preview:
                        try:
                            os.remove(old_preview.PreviewPath)
                        except FileNotFoundError:
                            pass
                        except Exception as e:
                            app.logger.exception(f"Error removing old preview: {e}")
                preview_file.save(preview_path)
                new_preview = MediaPreview(PreviewPath=preview_path)
                session.add(new_preview)
                session.commit()
                session.flush()
                old_preview = video.preview
                video.IdMediaPreview = new_preview.IdMediaPreview
                session.commit()
                session.refresh(video)
                if old_preview.IdMediaPreview != 1 and old_preview.IdMediaPreview != 2:
                    session.delete(old_preview)
            else:
                return jsonify({'message': 'Invalid preview file type'}), 400
        session.commit()
        return jsonify({'message': 'Video updated successfully'}), 200

    except exc.SQLAlchemyError as e:
        session.rollback()
        app.logger.exception(f"Database error updating video: {e}")
        return jsonify({'message': 'Database error'}), 500
    except Exception as e:
        app.logger.exception(f"Error updating video: {e}")
        return jsonify({'message': 'Error updating video'}), 500


@app.delete('/video/<int:id>')
@token_required(app, redis_client, Session)
@company_owner_level
@after_token_required
def delete_video(user, session, id):
    """
Deletes a video and its associated data (preview, tags, comments, ratings, view history).

Returns a 404 Not Found if the video is not found.
Returns a 500 Internal Server Error on database errors.
---
security:
  - bearerAuth: []
tags:
  - Video
parameters:
  - in: path
    name: id
    type: integer
    required: true
    description: The ID of the video to delete.
responses:
  200:
    description: Video deleted successfully.
  404:
    description: Video not found.
  500:
    description: Internal server error during video deletion.
"""
    try:
        video = session.query(Media).filter_by(IdMedia=id).first()
        if not video:
            return jsonify({'message': 'Video not found'}), 404

        # if video.IdCompany != request.headers.get("X-idCompany"):
        #     return jsonify({'message': 'video not found'}), 404

        # Remove associated preview if exists
        if video.IdMediaPreview and video.IdMediaPreview != 1 and video.IdMediaPreview != 2:
            preview = video.preview
            if preview:
                try:
                    os.remove(preview.PreviewPath)
                except FileNotFoundError:
                    pass
                except Exception as e:
                    app.logger.exception(f"Error removing video preview: {e}")

        # Remove video tags
        video.tags = []

        for rating in video.ratings:
            session.delete(rating)

        for comment in video.comments:
            session.delete(comment)

        for view in video.view_history:
            session.delete(view)

        try:
            os.remove(video.VideoPath)
        except FileNotFoundError:
            pass
        except Exception as e:
            app.logger.exception(f"Error removing video file: {e}")
            return jsonify({'message': 'Error while removing video file'}), 500

        preview = video.preview
        session.delete(video)
        if preview.IdMediaPreview != 1 and preview.IdMediaPreview != 2:
            session.delete(preview)
        session.commit()

        return jsonify({'message': 'Video deleted successfully'}), 200

    except exc.SQLAlchemyError as e:
        session.rollback()
        app.logger.exception(f"Database error deleting video: {e}")
        return jsonify({'message': 'Database error'}), 500
    except Exception as e:
        app.logger.exception(f"Error deleting video: {e}")
        return jsonify({'message': 'Error deleting video'}), 500


@app.route('/video/<int:id>/get')
@token_required(app, redis_client, Session)
@after_token_required
def get_video_link(user, session, id):
    """
Get temporary link to stream video

Retrieves information about a video, including:

  - Video name
  - Company ID
  - Description
  - Temporary access link
  - Tags associated with the video (list of objects with `id` and `name` properties)
  - Like/dislike counts for the video
  - User's rating for the video (if any)
  - Total view count
  - Unique viewer count

---
security:
  - bearerAuth: []
tags:
  - Video
parameters:
  - in: path
    name: id
    type: integer
    required: true
    description: The ID of the video to retrieve information for.
responses:
  200:
    description: Video information retrieved successfully.
    content:
      application/json:
        schema:
          type: object
          properties:
            name:
              type: string
              description: The video name.
            company_id:
              type: integer
              description: The ID of the company that owns the video.
            company_name:
              type: string
              description: Name of the company that owns the video.
            description:
              type: string
              description: The video description.
            temporary_link:
              type: string
              description: A temporary access link for the video.
            tags:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    description: The ID of the tag.
                  name:
                    type: string
                    description: The name of the tag.
            likes:
              type: integer
              description: Total number of likes for the video.
            dislikes:
              type: integer
              description: Total number of dislikes for the video.
            user_rating:
              type: integer  # Assuming user rating is also an integer
              description: The user's rating for the video (if any).
            total_views:
              type: integer
              description: Total number of times this video has been viewed.
            unique_viewers:
              type: integer
              description: Number of unique users who have viewed this video.
  404:
    description: Video not found.
  500:
    description: Internal server error during video information retrieval.
"""
    try:
        media = session.query(Media).filter_by(IdMedia=id).first()
        if not media:
            return jsonify({'message': 'Video not found'}), 404

        # View History Logic
        view_history_entry = session.query(ViewHistory).filter_by(IdUser=user.IdUser, IdMedia=id).first()
        if view_history_entry:
            view_history_entry.ViewTime = datetime.datetime.now()
            view_history_entry.ViewCount += 1
        else:
            new_view_history = ViewHistory(
                IdUser=user.IdUser,
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

        temp_link = generate_temporary_link(id, media.NameV, request.headers['host'])

        tags = [{"id": tag.IdTag, "name": tag.TagName} for tag in media.tags] # Get tags
        likes, dislikes, user_rating_value = get_rating_counts(session, id, user.IdUser)

        media_info = {
            "name": media.NameV,
            "company_id": media.IdCompany,
            "company_name": media.companies.Name,
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


@app.get('/video/<int:id>/preview')
@token_required(app, redis_client, Session)
@after_token_required
def get_video_preview(current_user, session, id):
    """
Retrieves the preview image for a video, if available.
---
security:
  - bearerAuth: []
tags:
  - Video
parameters:
  - in: path
    name: id
    type: integer
    required: true
    description: The ID of the video for which to retrieve the preview.
responses:
  200:
    description: Preview image retrieved successfully.
    content:
      image/*  # Assuming the preview image can be of various formats
  404:
    description: 
      - Video not found.
      - Preview file not found.
  500:
    description: Internal server error during preview retrieval.
"""
    try:
        media = session.query(Media).filter_by(IdMedia=id).first()
        if not media:
            return jsonify({'message': 'Video not found'}), 404

        if media.preview:
            preview_path = media.preview.PreviewPath
            if os.path.exists(preview_path):
                return send_from_directory(os.path.dirname(preview_path), os.path.basename(preview_path))
            else:
                 return jsonify({'message': 'Preview file not found'}), 404
        else:
            return jsonify({'message': 'No preview available'}), 404

    except Exception as e:
        app.logger.exception(f"Error getting video preview: {e}")
        return jsonify({'message': 'Error getting video preview'}), 500


@app.post('/video/<int:id>/rating')
@token_required(app, redis_client, Session)
@after_token_required
def rate_video(current_user, session, id):
    """
Rates a video (like, dislike, or remove rating).
---
security:
  - bearerAuth: []
tags:
  - Video
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          rating:
            type: integer
            description: "The rating value (0: remove rating, 1: like, -1: dislike)."
responses:
  200:
    description: 
      - Rating removed successfully (if rating is 0).
      - Rating updated successfully (if existing rating is updated).
  201:
    description: Rating added successfully (if no prior rating exists).
  400:
    description: 
      - Rating value is missing in the request body.
      - Invalid rating value (must be 0, 1, or -1).
      - Rating cannot be the same as the previous rating.
  500:
    description: 
      - Database integrity error during rating.
      - Error adding/updating rating.
"""
    data = request.get_json()
    rating_value = data.get('rating')  # 0, 1, or -1

    if rating_value is None:
        return jsonify({'message': 'Rating value is required'}), 400

    if rating_value not in (0, 1, -1):
        return jsonify({'message': 'Invalid rating value. Must be 0, 1, or -1'}), 400

    try:
        media = session.query(Media).filter_by(IdMedia=id).first()
        if not media:
            return jsonify({'message': 'Video not found'}), 404

        existing_rating = session.query(Ratings).filter_by(IdUser=current_user.IdUser, IdMedia=id).first()

        if rating_value == 0:  # Remove rating
            if existing_rating:
                session.delete(existing_rating)
                session.commit()
                likes, dislikes, user_rating_value = get_rating_counts(session, id, current_user.IdUser)
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
            likes, dislikes, user_rating_value = get_rating_counts(session, id, current_user.IdUser)
            return jsonify({
                'message': 'Rating updated',
                'likes': likes,
                'dislikes': dislikes,
                'user_rating': user_rating_value
            }), 201

        new_rating = Ratings(
            IdUser=current_user.IdUser,
            IdMedia=id,
            IdRatingType=rating_type.IdRatingType,
            RatingTime=datetime.datetime.now()
        )
        session.add(new_rating)
        session.commit()
        likes, dislikes, user_rating_value = get_rating_counts(session, id, current_user.IdUser)
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


@app.route('/stream/<link_id>/<filename>') # Added filename parameter
def stream_video_from_link(link_id, filename):
    """
Streams a video from a temporary link.
---
tags:
  - Video
parameters:
  - in: path
    name: link_id
    type: string
    required: true
    description: The unique identifier for the temporary link.
  - in: path
    name: filename
    type: string
    required: true
    description: The original filename of the video encoded in the URL.
responses:
  206:
    description: Partial video content streamed successfully.
    headers:
      Content-Type:
        type: string
        description: The MIME type of the video content.
      Content-Range:
        type: string
        description: The byte range of the video content being streamed (e.g., bytes 0-1023/10240).
  404:
    description: 
      - Invalid or expired link.
      - Video not found.
      - Video file not found on server.
  500:
    description: Error streaming video.
"""
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

        content_type, _ = mimetypes.guess_type(media.NameV)
        if not content_type:
            content_type = 'application/octet-stream'  # Default if type is unknown

        resp = Response(chunk, 206, content_type=content_type, direct_passthrough=True)
        resp.headers.add('Content-Range', 'bytes {0}-{1}/{2}'.format(start, start + length - 1, file_size))
        return resp
    except Exception as e:
        app.logger.exception(f"Error streaming video: {e}")
        return jsonify({'message': 'Error streaming video'}), 500
    finally:
        session.close()


@app.get("/video/")
def redirect_video():
    return redirect("/video", 302)

@app.get('/video')
@token_required(app, redis_client, Session)
@after_token_required
def get_all_videos(current_user, session):
    """
Retrieves a list of all videos.
---
security:
  - bearerAuth: []
tags:
  - Video
responses:
  200:
    description: List of videos retrieved successfully.
    content:
      application/json:
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                description: The ID of the video.
              name:
                type: string
                description: The name of the video.
              description:
                type: string
                description: The description of the video.
              upload_time:
                type: string
                format: date-time
                description: The time the video was uploaded (in ISO 8601 format).
              tags:
                type: array
                items:
                  type: object
                  properties:
                    id:
                      type: integer
                      description: The ID of the tag associated with the video.
                    name:
                      type: string
                      description: The name of the tag.
              company_id:
                type: integer
                description: The ID of the company that owns the video.
  500:
    description: Error retrieving videos.
"""
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


@app.get('/video/recommendations')
@token_required(app, redis_client, Session)
@after_token_required
def get_video_recommendations(user, session):
    """
    Retrieves personalized video recommendations for the current user.

    This endpoint implements a weighted tag-based approach with the following steps:

    1. **Retrieving Recently Watched Videos (up to 10):**
       - Fetches the user's most recently watched videos (maximum of 10) from the `ViewHistory` table, ordered by `ViewTime` (most recent first).
       - Stores the retrieved video IDs in a list (`recent_video_ids`).

    2. **Counting Tag Occurrences:**
       - Queries for the tags associated with the user's recently watched videos using the `MediaTagsConnector` table.
       - Filters out duplicate tags using `distinct()`.
       - Extracts the tag IDs from the results and stores them in a list (`recent_tag_ids`).
       - Creates a `Counter` object (`tag_counts`) to efficiently count the occurrences of each tag across the recently watched videos.

    3. **Finding New Videos with Matching Tags (within the last 7 days):**
       - Sets a time threshold (`one_week_ago`) to identify recently uploaded videos (within the last 7 days).
       - Queries for videos from the `Media` table that meet the following criteria:
           - Their tags (`IdTag`) must be present in the `recent_tag_ids` list, indicating relevance to the user's watched videos.
           - Their upload time (`UploadTime`) must be greater than or equal to `one_week_ago`, ensuring they are recently uploaded.
           - They must not be among the user's recently watched videos (`~Media.IdMedia.in_(recent_video_ids)`), avoiding duplicates.
       - Orders the retrieved videos by their upload time in descending order (`order_by(Media.UploadTime.desc())`), prioritizing the newest ones.
       - Stores the retrieved video objects in a list (`personalized_recommendations`).

    4. **Calculating Weighted Scores for Recommended Videos:**
       - Iterates through each video in `personalized_recommendations`:
           - Initializes a weight variable (`weight`) to zero.
           - For each tag (`tag`) associated with the current video, checks if its ID (`tag.IdTag`) exists in the `tag_counts` dictionary.
           - If the tag exists, adds its count (`tag_counts[tag.IdTag]`) to the `weight`, giving more weight to videos with more matching tags from the user's history.

       - **Incorporating Time-Weighted Likes and Dislikes (Optional):**
           - Optionally, retrieves the user's likes and dislikes (ratings) for each video in `personalized_recommendations`.
           - Uses the `calculate_time_decay` function (assumed to be implemented elsewhere) to adjust the weight based on the rating time (more recent ratings have higher influence).
           - Sums the adjusted weights for likes (`like_weight`) and dislikes (`dislike_weight`) and adds `like_weight * 0.5 - dislike_weight * 0.2` to the overall `weight`. This gives a slight preference to videos the user has liked recently.

       - Appends a tuple containing the video object and its calculated weight (`(video, weight)`) to a list (`weighted_videos`).

    5. **Sorting and Selecting Top Recommendations:**
       - Sorts the `weighted_videos` list by weight in descending order (`sort(key=lambda x: x[1], reverse=True)`), prioritizing videos with higher weights (more relevant tags and potentially more recent likes).

    6. **Handling Cold Start (if less than 10 recommendations):**
       - Checks if the number of recommended videos (`len(recommended_videos)`) is less than 10 (desired number of recommendations).
       - If there are fewer than 10 recommendations, calculates the number of videos needed to fill the gap (`num_to_fill`).
       - Queries for additional videos from the `Media` table, excluding the videos already recommended (`~Media.IdMedia.in_([video.IdMedia for video in recommended_videos])`).
       - Sorts these cold start recommendations by upload time in descending order, prioritizing newer videos.
       - Calculates weights for these cold start videos similar to step 4, optionally incorporating time-weighted likes and dislikes.
       - Sorts the cold start recommendations by weight in descending order.
       - Extends the `recommended

    ---
    security:
      - bearerAuth: []
    tags:
      - Video
      - Recommendations
    responses:
      200:
        description: Video recommendations retrieved successfully. Returns a list of video objects.
        content:
          application/json:
            schema:
              type: object
              properties:
                audio:
                    type: array
                    items:
                      type: object
                      properties:
                        id:
                          type: integer
                          description: the id of the recommended video.
                        name:
                          type: string
                          description: the name of the recommended video.
                        description:
                          type: string
                          description: The description of the recommended video.
                        company_id:
                          type: integer
                          description: the id of the company, that uploaded video.
                        company_name:
                          type: string
                          description: the name of the company, that recommended video.
                        upload_time:
                          type: string
                          format: date-time
                          description: The time the video was uploaded (in ISO 8601 format).

                        tags:
                          type: array
                          items:
                            type: object
                            properties:
                              id:
                                type: integer
                                description: The ID of the tag associated with the video.
                              name:
                                type: string
                                description: The name of the tag.
                video:
                    type: array
                    items:
                      type: object
                      properties:
                        id:
                          type: integer
                          description: the id of the recommended video.
                        name:
                          type: string
                          description: the name of the recommended video.
                        description:
                          type: string
                          description: The description of the recommended video.
                        company_id:
                          type: integer
                          description: the id of the company, that uploaded video.
                        company_name:
                          type: string
                          description: the name of the company, that recommended video.
                        upload_time:
                          type: string
                          format: date-time
                          description: The time the video was uploaded (in ISO 8601 format).

                        tags:
                          type: array
                          items:
                            type: object
                            properties:
                              id:
                                type: integer
                                description: The ID of the tag associated with the video.
                              name:
                                type: string
                                description: The name of the tag.
      500:
        description: Internal server error.
    """
    try:
        recent_videos = session.query(ViewHistory).join(ViewHistory.media).filter(and_(or_(*[Media.VideoPath.ilike(f"%{ext}") for ext in ALLOWED_VIDEO_EXTENSIONS]), ViewHistory.IdUser == user.IdUser)).order_by(ViewHistory.ViewTime.desc()).all()
        num_recent_videos = len(recent_videos)

        recommended_videos = recommendation_generator(user, session, num_recent_videos, recent_videos)

        recent_audios = session.query(ViewHistory).join(ViewHistory.media).filter(and_(or_(*[Media.VideoPath.ilike(f"%{ext}") for ext in ALLOWED_AUDIO_EXTENSIONS]), ViewHistory.IdUser == user.IdUser)).order_by(ViewHistory.ViewTime.desc()).all()
        num_recent_audios = len(recent_audios)

        recommended_audios = recommendation_generator(user, session, num_recent_audios, recent_audios, is_audio=True)

        video_list = [{
            "id": video.IdMedia,
            "name": video.NameV,
            "description": video.DescriptionV,
            "company_id": video.companies.IdCompany,
            "company_name": video.companies.Name,
            "upload_time": video.UploadTime.isoformat(),
            "tags": [{"id": tag.IdTag, "name": tag.TagName} for tag in video.tags]
        } for video in recommended_videos]
        audio_list = [{
            "id": audio.IdMedia,
            "name": audio.NameV,
            "description": audio.DescriptionV,
            "company_id": audio.companies.IdCompany,
            "company_name": audio.companies.Name,
            "upload_time": audio.UploadTime.isoformat(),
            "tags": [{"id": tag.IdTag, "name": tag.TagName} for tag in audio.tags]
        } for audio in recommended_audios]
        return jsonify({
            "video": video_list,
            "audio": audio_list
        }), 200

    except Exception as e:
        app.logger.exception(f"Error getting recommendations: {e}")
        return jsonify({'message': 'Internal server error'}), 500
