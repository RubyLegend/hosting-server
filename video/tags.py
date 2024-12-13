from flask import jsonify
from ..database.tags import Tags
from .. import app, Session
from ..user.functions import token_required


@app.get('/video/tags')
@token_required
def get_all_tags(current_user):
    session = Session()
    try:
        tags = session.query(Tags).all()
        tag_list = [{"id": tag.IdTag, "name": tag.TagName} for tag in tags]
        return jsonify({'tags': tag_list}), 200
    except Exception as e:
        app.logger.exception(f"Error retrieving tags: {e}")
        return jsonify({'message': 'Error retrieving tags'}), 500
    finally:
        session.close()
