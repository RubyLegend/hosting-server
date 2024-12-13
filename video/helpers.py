from flask import url_for
import datetime
import os
import urllib
from .. import app, ALLOWED_EXTENSIONS, redis_client
from ..database.media import Media
import uuid

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_unique_filepath(filepath, session):
    """Generates a unique filename by appending a counter if necessary."""
    base, ext = os.path.splitext(filepath)
    counter = 1

    while True:
        existing_media = session.query(Media).filter_by(VideoPath=filepath).first()
        if not existing_media:
            return filepath

        filepath = f"{base}({counter}){ext}"
        counter += 1


# Configuration for link expiration (e.g., 1 hour)
LINK_EXPIRATION_SECONDS = 3600


def generate_temporary_link(media_id, filename):
    """Generates a temporary link with filename."""
    link_id = str(uuid.uuid4())
    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=LINK_EXPIRATION_SECONDS)
    redis_client.setex(f"temp_link:{link_id}:{filename}", LINK_EXPIRATION_SECONDS, str(media_id))

    # URL encode the filename to handle special characters
    encoded_filename = urllib.parse.quote(filename)

    return url_for('stream_video_from_link', link_id=link_id, filename=encoded_filename, _external=True)