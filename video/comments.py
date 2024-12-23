from flask import jsonify, request
from datetime import datetime
from ..database.comments import Comments
from ..database.media import Media
from ..database.users import Users
from .. import app, Session
from ..user.functions import token_required, has_moderator_access
from sqlalchemy import exc


@app.get('/video/<int:v>/comments')
@token_required
def get_video_comments(current_user, owned_companies, v):
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


@app.post('/video/<int:v>/comments')
@token_required
def add_video_comment(current_user, owned_companies, v):
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
        session.flush()

        user = session.query(Users).filter_by(IdUser=current_user).first()

        session.commit()
        return jsonify({'message': 'Comment added successfully', 
                        'comment': {
                            'id': new_comment.IdComment,
                            'user_id': new_comment.IdUser,
                            'user_login': user.LoginUser if user else None,
                            'text': new_comment.TextComment,
                            'date': new_comment.Date.isoformat()
                        }}), 201

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error adding comment: {e}")
        return jsonify({'message': 'Error adding comment'}), 500
    finally:
        session.close()


@app.delete('/comments/<int:comment_id>')
@token_required
def delete_video_comment(current_user, owned_companies, comment_id):
    if not comment_id:
        return jsonify({'message': 'Comment ID is required'}), 400

    try:
        comment_id = int(comment_id)
    except ValueError:
        return jsonify({'message': 'Invalid comment ID. Must be an integer'}), 400

    session = Session()
    try:
        comment = session.query(Comments).filter_by(IdComment=comment_id).first()
        if not comment:
            return jsonify({'message': 'Comment not found'}), 404

        if comment.IdUser != current_user and not has_moderator_access(current_user, session):
            return jsonify({'message': 'You do not have permission to delete this comment'}), 403

        session.delete(comment)
        session.commit()
        return jsonify({'message': 'Comment deleted successfully'}), 200

    except exc.IntegrityError as e:
        session.rollback()
        app.logger.exception(f"Database integrity error during comment deletion: {e}")
        return jsonify({'message': 'Database integrity error'}), 500
    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error deleting comment: {e}")
        return jsonify({'message': 'Error deleting comment'}), 500
    finally:
        session.close()
