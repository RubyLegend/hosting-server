from flask import jsonify, request
from datetime import datetime
from ..database.comments import Comments
from ..database.media import Media
from ..database.users import Users
from ..database.reports import Reports
from .. import app, Session, redis_client
from ..user.functions import token_required, after_token_required, has_moderator_access
from sqlalchemy import exc


@app.get("/video/<int:v>/comments")
@token_required(app, redis_client, Session)
@after_token_required
def get_video_comments(user, session, v):
    """
    Retrieves all comments for a specific video.
    ---
    security:
      - bearerAuth: []
    tags:
      - Video
      - Comments
    parameters:
      - in: path
        name: v
        type: integer
        required: true
        description: The ID of the video for which to retrieve comments.
    responses:
      200:
        description: List of video comments retrieved successfully.
        content:
          application/json:
            schema:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    description: The ID of the comment.
                  user_id:
                    type: integer
                    description: The ID of the user who posted the comment.
                  user_login:
                    type: string
                    nullable: true
                    description: The username and surname of the user who posted the comment (if available).
                  text:
                    type: string
                    description: The text content of the comment.
                  date:
                    type: string
                    format: date-time
                    nullable: true
                    description: The date and time the comment was posted (in ISO 8601 format).
                  can_delete:
                    type: boolean
                    description: Whether current user can delete this comment.
                  reported:
                    type: boolean
                    description: Whether this message is reported. This is for moderators only.
      404:
        description: Video not found.
      500:
        description: Error retrieving comments.
    """
    try:
        media = session.query(Media).filter_by(IdMedia=v).first()
        if not media:
            return jsonify({"message": "Video not found"}), 404

        comments = session.query(Comments).filter_by(IdMedia=v).all()

        has_weak_moderator = has_moderator_access(user, session, media.IdCompany)
        has_strong_moderator = has_moderator_access(
            user, session, media.IdCompany, False
        )

        comment_list = []
        for comment in comments:
            # comment_user = session.query(Users).filter_by(IdUser=comment.IdUser).first()
            comment_list.append(
                {
                    "id": comment.IdComment,
                    "user_id": comment.IdUser,
                    "user_login": (
                        comment.users.NameUser + " " + comment.users.Surname
                        if comment.users.NameUser or comment.users.Surname
                        else "No Name"
                    ),
                    "text": comment.TextComment,
                    "date": comment.Date.isoformat() if comment.Date else None,
                    "can_delete": has_weak_moderator or comment.IdUser == user.IdUser,
                    "reported": (
                        True if comment.reports and has_strong_moderator else False
                    ),
                }
            )

        return jsonify(comment_list), 200

    except Exception as e:
        app.logger.exception(f"Error retrieving comments: {e}")
        return jsonify({"message": "Error retrieving comments"}), 500


@app.post("/video/<int:v>/comments")
@token_required(app, redis_client, Session)
@after_token_required
def add_video_comment(current_user, session, v):
    """
    Adds a new comment to a video.
    ---
    security:
      - bearerAuth: []
    tags:
      - Video
      - Comments
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              message:
                type: string
                required: true
                description: The text content of the comment.
    parameters:
      - in: path
        name: v
        type: integer
        required: true
        description: The ID of the video to which the comment is added.
    responses:
      201:
        description: Comment added successfully.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  description: Progress message.
                comment:
                  type: object
                  properties:
                    id:
                      type: integer
                      description: The ID of the newly added comment.
                    user_id:
                      type: integer
                      description: The ID of the user who posted the comment.
                    user_login:
                      type: string
                      nullable: true
                      description: The username and surname of the user who posted the comment (if available).
                    text:
                      type: string
                      description: The text content of the comment.
                    date:
                      type: string
                      format: date-time
                      description: The date and time the comment was posted (in ISO 8601 format).
      400:
        description: Comment text is required.
      404:
        description: Video not found.
      500:
        description: Error adding comment.
    """
    data = request.get_json()
    text_comment = data.get("message")

    if not text_comment:
        return jsonify({"message": "Comment text is required"}), 400

    try:
        media = session.query(Media).filter_by(IdMedia=v).first()
        if not media:
            return jsonify({"message": "Video not found"}), 404

        new_comment = Comments(
            IdUser=current_user.IdUser,
            IdMedia=v,
            TextComment=text_comment,
            Date=datetime.now(),
        )
        session.add(new_comment)
        session.flush()

        # user = session.query(Users).filter_by(IdUser=current_user.IdUser).first()

        session.commit()
        return (
            jsonify(
                {
                    "message": "Comment added successfully",
                    "comment": {
                        "id": new_comment.IdComment,
                        "user_id": new_comment.IdUser,
                        "user_login": (
                            current_user.NameUser + " " + current_user.Surname
                            if current_user.NameUser or current_user.Surname
                            else "No Name"
                        ),
                        "text": new_comment.TextComment,
                        "date": new_comment.Date.isoformat(),
                    },
                }
            ),
            201,
        )

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error adding comment: {e}")
        return jsonify({"message": "Error adding comment"}), 500


@app.delete("/comments/<int:comment_id>")
@token_required(app, redis_client, Session)
@after_token_required
def delete_video_comment(current_user, session, comment_id):
    """
    Deletes a specific comment.
    ---
    security:
      - bearerAuth: []
    tags:
      - Comments
    parameters:
      - in: path
        name: comment_id
        type: integer
        required: true
        description: The ID of the comment to delete.
    responses:
      200:
        description: Comment deleted successfully.
      400:
        description:
          - Comment ID is required.
          - Invalid comment ID. Must be an integer.
      403:
        description: You do not have permission to delete this comment.
      404:
        description: Comment not found.
      500:
        description:
          - Database integrity error during comment deletion.
          - Error deleting comment.
    """
    if not comment_id:
        return jsonify({"message": "Comment ID is required"}), 400

    try:
        comment_id = int(comment_id)
    except ValueError:
        return jsonify({"message": "Invalid comment ID. Must be an integer"}), 400

    try:
        comment = session.query(Comments).filter_by(IdComment=comment_id).first()
        if not comment:
            return jsonify({"message": "Comment not found"}), 404

        if comment.IdUser != current_user.IdUser and not has_moderator_access(
            current_user, session
        ):
            return (
                jsonify(
                    {"message": "You do not have permission to delete this comment"}
                ),
                403,
            )

        # Search for linked reports
        reports = comment.reports
        for report in reports:
            session.delete(report)

        session.delete(comment)
        session.commit()
        return jsonify({"message": "Comment deleted successfully"}), 200

    except exc.IntegrityError as e:
        session.rollback()
        app.logger.exception(f"Database integrity error during comment deletion: {e}")
        return jsonify({"message": "Database integrity error"}), 500
    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error deleting comment: {e}")
        return jsonify({"message": "Error deleting comment"}), 500


@app.post("/comments/<int:id>/report")
@token_required(app, redis_client, Session)
@after_token_required
def report_comment(user, session, id):
    """
    Creates a new report for a comment.
    ---
    security:
      - bearerAuth: []
    tags:
      - Reports
    parameters:
      - in: path
        name: id
        type: integer
        required: true
        description: The ID of the comment to report.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              report_reason:
                type: string
                required: true
                description: The reason for reporting the comment.
    responses:
      201:
        description: Report created successfully.
      400:
        description: Report reason is required.
      404:
        description: Comment not found.
      500:
        description: Internal server error.
    """
    try:
        comment = session.query(Comments).filter_by(IdComment=id).first()
        if not comment:
            return jsonify({"message": "Comment not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"message": "No data provided"}), 400
        report_reason = data.get("report_reason")

        if not report_reason:
            report_reason = ""

        new_report = Reports(
            IdComment=id,
            IdUser=user.IdUser,
            ReportReason=report_reason,
            ReportTime=datetime.now(),
        )
        session.add(new_report)
        session.commit()

        return jsonify({"message": "Report created successfully"}), 201

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error creating report: {e}")
        return jsonify({"message": "Internal server error"}), 500
