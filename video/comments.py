from flask import jsonify, request
from datetime import datetime
from ..database.comments import Comments
from ..database.media import Media
from ..database.users import Users
from .. import app, Session
from ..user.functions import token_required


@app.get('/video/comments/<int:v>')
@token_required
def get_video_comments(current_user, v):
    session = Session()
    try:
        media = session.query(Media).filter_by(IdMedia=v).first()
        if not media:
            return jsonify({'message': 'Video not found'}), 404

        comments = session.query(Comments).filter_by(IdMedia=v).all()

        comment_list = []
        for comment in comments:
            user = session.query(Users).filter_by(IdUser=comment.IdUser).first()
            comment_list.append({
                "id": comment.IdComment,
                "user_id": comment.IdUser,
                "user_login": user.NameUser + " " + user.Surname if user else None,
                "text": comment.TextComment,
                "date": comment.Date.isoformat() if comment.Date else None
            })

        return jsonify(comment_list), 200

    except Exception as e:
        app.logger.exception(f"Error retrieving comments: {e}")
        return jsonify({'message': 'Error retrieving comments'}), 500
    finally:
        session.close()


@app.post('/video/comments/<int:v>')
@token_required
def add_video_comment(current_user, v):
    data = request.get_json()
    text_comment = data.get('message')

    if not text_comment:
        return jsonify({'message': 'Comment text is required'}), 400

    session = Session()
    try:
        media = session.query(Media).filter_by(IdMedia=v).first()
        if not media:
            return jsonify({'message': 'Video not found'}), 404

        new_comment = Comments(
            IdUser=current_user,
            IdMedia=v,
            TextComment=text_comment,
            Date=datetime.now()
        )
        session.add(new_comment)
        session.commit()
        return jsonify({'message': 'Comment added successfully'}), 201

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error adding comment: {e}")
        return jsonify({'message': 'Error adding comment'}), 500
    finally:
        session.close()
