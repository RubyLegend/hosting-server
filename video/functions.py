from flask import Flask, url_for
import datetime
import math
import os
from typing import Optional, Tuple
from collections import Counter
from .. import (
    app,
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    ALLOWED_EXTENSIONS,
    ALLOWED_PREVIEW_EXTENSIONS,
    redis_client,
)
from ..database.media import Media
from ..database.mediaPreview import MediaPreview
from ..database.ratings import Ratings
from ..database.ratingTypes import RatingTypes
from ..database.tags import Tags
from ..database.mediaTagsConnector import MediaTagsConnector
import uuid
from sqlalchemy import func, and_, or_

app: Flask


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_preview_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_PREVIEW_EXTENSIONS
    )


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


def get_unique_filepath_preview(filepath, session):
    """Generates a unique filename by appending a counter if necessary."""
    base, ext = os.path.splitext(filepath)
    counter = 1

    while True:
        existing_media = (
            session.query(MediaPreview).filter_by(PreviewPath=filepath).first()
        )
        if not existing_media:
            return filepath

        filepath = f"{base}({counter}){ext}"
        counter += 1


# Configuration for link expiration (e.g., 1 hour)
LINK_EXPIRATION_SECONDS = 3600


def generate_temporary_link(media_id, filename, host):
    """Generates a temporary link with filename."""
    link_id = str(uuid.uuid4())
    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(
        seconds=LINK_EXPIRATION_SECONDS
    )
    redis_client.setex(
        f"temp_link:{link_id}:{filename}", LINK_EXPIRATION_SECONDS, str(media_id)
    )

    # URL encode the filename to handle special characters
    # encoded_filename = urllib.parse.quote(filename)

    return url_for(
        "stream_video_from_link", link_id=link_id, filename=filename, _external=True
    )


def get_rating_counts(session, media_id, user_id):
    """Retrieves like/dislike counts and user's rating."""
    likes = (
        session.query(func.count(Ratings.IdRating))
        .filter(Ratings.IdMedia == media_id, Ratings.IdRatingType == 2)  # Like
        .scalar()
        or 0
    )

    dislikes = (
        session.query(func.count(Ratings.IdRating))
        .filter(Ratings.IdMedia == media_id, Ratings.IdRatingType == 3)  # Dislike
        .scalar()
        or 0
    )

    user_rating = (
        session.query(Ratings).filter_by(IdUser=user_id, IdMedia=media_id).first()
    )
    user_rating_value = 0  # Default: no rating
    if user_rating:
        if user_rating.IdRatingType == 2:
            user_rating_value = 1  # Like
        elif user_rating.IdRatingType == 3:
            user_rating_value = -1  # Dislike

    return likes, dislikes, user_rating_value


def get_chunk(
    byte1: Optional[int] = None, byte2: Optional[int] = None, filepath: str = None
) -> Tuple[bytes, int, int, int]:
    """
    Safely reads a chunk of data from a file.

    Args:
        byte1 (Optional[int]): Starting byte position (inclusive). Defaults to None (start from beginning).
        byte2 (Optional[int]): Ending byte position (exclusive). Defaults to None (read until end).
        filepath (str): Path to the file.

    Returns:
        Tuple[bytes, int, int, int]: A tuple containing the chunk data (bytes), starting byte position, chunk length, and total file size.

    Raises:
        FileNotFoundError: If the file path is invalid or the file doesn't exist.
        ValueError: If byte1 is greater than byte2 or either byte position is negative.
    """

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    file_size = os.path.getsize(filepath)
    start = 0

    if byte1 is not None:
        if byte1 < 0:
            raise ValueError("Starting byte position (byte1) cannot be negative")
        start = min(byte1, file_size)  # Clamp byte1 to file size

    if byte2 is not None:
        if byte2 < 0:
            raise ValueError("Ending byte position (byte2) cannot be negative")
        if byte1 is not None and byte1 > byte2:
            raise ValueError(
                "Starting byte position (byte1) cannot be greater than ending position (byte2)"
            )
        length = min(byte2 + 1 - start, file_size - start)  # Clamp length to file size
    else:
        length = file_size - start

    with open(filepath, "rb") as f:
        f.seek(start)
        chunk = f.read(length)

    return chunk, start, length, file_size


def calculate_time_decay(rating_time):
    """Calculates a time decay factor based on the rating time."""
    time_difference = datetime.datetime.now() - rating_time
    days_difference = time_difference.days

    # Example decay function (exponential decay)
    decay_factor = math.exp(-days_difference / 7)  # Decay by half each week

    return decay_factor


def recommendation_generator(
    user, session, num_recent_videos, recent_videos, is_audio=False
):
    recommended_videos = []

    if num_recent_videos > 0:
        recent_video_ids = [v.IdMedia for v in recent_videos]
        if num_recent_videos < 10:
            recent_videos = recent_videos[:num_recent_videos]
        else:
            recent_videos = recent_videos[:10]
        recent_video_ids = [v.IdMedia for v in recent_videos]

        recent_video_tags = (
            session.query(MediaTagsConnector.IdTag)
            .filter(MediaTagsConnector.IdMedia.in_(recent_video_ids))
            .distinct()
            .all()
        )
        if recent_video_tags:
            recent_tag_ids = [t[0] for t in recent_video_tags]
            tag_counts = Counter(recent_tag_ids)  # Count tag occurrences
            one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)

            personalized_recommendations = (
                session.query(Media)
                .join(Media.tags)
                .filter(
                    Tags.IdTag.in_(recent_tag_ids),
                    Media.UploadTime >= one_week_ago,
                    ~Media.IdMedia.in_(recent_video_ids),
                    or_(
                        *[
                            Media.VideoPath.ilike(f"%{ext}")
                            for ext in (
                                ALLOWED_AUDIO_EXTENSIONS
                                if is_audio
                                else ALLOWED_VIDEO_EXTENSIONS
                            )
                        ]
                    ),
                )
                .order_by(Media.UploadTime.desc())
                .all()
            )
        else:

            one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)

            personalized_recommendations = (
                session.query(Media)
                .filter(
                    Media.UploadTime >= one_week_ago,
                    ~Media.IdMedia.in_(recent_video_ids),
                    or_(
                        *[
                            Media.VideoPath.ilike(f"%{ext}")
                            for ext in (
                                ALLOWED_AUDIO_EXTENSIONS
                                if is_audio
                                else ALLOWED_VIDEO_EXTENSIONS
                            )
                        ]
                    ),
                )
                .order_by(Media.UploadTime.desc())
                .all()
            )

        weighted_videos = []
        for video in personalized_recommendations:
            weight = sum(
                tag_counts[tag.IdTag] for tag in video.tags if tag.IdTag in tag_counts
            )

            # Incorporate likes and dislikes
            likes = (
                session.query(Ratings)
                .join(Ratings.rating_types)
                .filter(Ratings.IdMedia == video.IdMedia, RatingTypes.RatingFactor == 1)
                .all()
            )
            dislikes = (
                session.query(Ratings)
                .join(Ratings.rating_types)
                .filter(
                    Ratings.IdMedia == video.IdMedia, RatingTypes.RatingFactor == -1
                )
                .all()
            )

            # Adjust weight based on likes and dislikes
            like_weight = (
                sum(calculate_time_decay(rating.RatingTime) for rating in likes)
                if likes
                else 0
            )
            dislike_weight = (
                sum(calculate_time_decay(rating.RatingTime) for rating in dislikes)
                if dislikes
                else 0
            )

            weight += like_weight * 0.5 - dislike_weight * 0.2
            weighted_videos.append((video, weight))

        weighted_videos.sort(key=lambda x: x[1], reverse=True)  # Sort by weight
        recommended_videos.extend([video for video, weight in weighted_videos])

    if len(recommended_videos) < 10:  # Cold start problem
        num_to_fill = 10 - len(recommended_videos)
        one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        coldstart_recommendations = (
            session.query(Media)
            .filter(
                ~Media.IdMedia.in_([video.IdMedia for video in recommended_videos]),
                or_(
                    *[
                        Media.VideoPath.ilike(f"%{ext}")
                        for ext in (
                            ALLOWED_AUDIO_EXTENSIONS
                            if is_audio
                            else ALLOWED_VIDEO_EXTENSIONS
                        )
                    ]
                ),
            )
            .order_by(Media.UploadTime.desc())
            .all()
        )
        weighted_coldstart_videos = []
        for video in coldstart_recommendations:
            likes = (
                session.query(Ratings)
                .join(Ratings.rating_types)
                .filter(Ratings.IdMedia == video.IdMedia, RatingTypes.RatingFactor == 1)
                .all()
            )
            dislikes = (
                session.query(Ratings)
                .join(Ratings.rating_types)
                .filter(
                    Ratings.IdMedia == video.IdMedia, RatingTypes.RatingFactor == -1
                )
                .all()
            )

            like_weight = (
                sum(calculate_time_decay(rating.RatingTime) for rating in likes)
                if likes
                else 0
            )
            dislike_weight = (
                sum(calculate_time_decay(rating.RatingTime) for rating in dislikes)
                if dislikes
                else 0
            )

            weight = like_weight * 0.5 - dislike_weight * 0.2
            weighted_coldstart_videos.append((video, weight))
        weighted_coldstart_videos.sort(key=lambda x: x[1], reverse=True)
        recommended_videos.extend(
            [video for video, weight in weighted_coldstart_videos[:num_to_fill]]
        )

    return recommended_videos
