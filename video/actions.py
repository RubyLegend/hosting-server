from flask import Response, request, jsonify
import datetime
import os
import json
import urllib
from werkzeug.utils import secure_filename  # For secure filename
from .. import app, Session, redis_client
from ..user.functions import token_required
from ..database.media import Media
from ..database.tags import Tags
from .helpers import allowed_file, get_unique_filepath, generate_temporary_link


@app.post('/video/upload')
@token_required  # Protect this endpoint
def upload_video(current_user):  # current_user is passed from decorator
    if 'file' not in request.files:
        return jsonify({'message': 'No video part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            original_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            filepath = get_unique_filepath(original_filepath, Session())
            try:
                with open(filepath, 'wb') as f:
                    while True:
                        chunk = file.read(4096)  # Read in chunks
                        if not chunk:
                            break
                        f.write(chunk)
            except Exception as e:
                return jsonify({'message': str(e)}), 500

            data = json.loads(list(request.form.values())[0])
            name = data.get('name')
            description = data.get('description')
            id_company = data.get('idCompany')
            tags = data.get('tags') # Get the tags string

            if not name:
                os.remove(filepath)
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
        return jsonify({'message': 'Invalid file type'}), 400


@app.route('/video/get/<int:v>')
@token_required
def get_video_link(current_user, v):
    session = Session()
    try:
        media = session.query(Media).filter_by(IdMedia=v).first()
        if not media:
            return jsonify({'message': 'Video not found'}), 404

        temp_link = generate_temporary_link(v, media.NameV)

        tags = [{"id": tag.IdTag, "name": tag.TagName} for tag in media.tags] # Get tags

        media_info = {
            "name": media.NameV,
            "description": media.DescriptionV,
            "temporary_link": temp_link,
            "tags": tags
        }

        return jsonify(media_info), 200

    except Exception as e:
        app.logger.exception(f"Error generating temporary link: {e}")
        return jsonify({'message': 'Error generating link'}), 500
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

        def generate():
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    yield chunk

        return Response(generate(), mimetype="video/mp4")  # Set Content-Disposition header
    except Exception as e:
        app.logger.exception(f"Error streaming video: {e}")
        return jsonify({'message': 'Error streaming video'}), 500
    finally:
        session.close()
