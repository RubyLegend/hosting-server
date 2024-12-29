from flask import jsonify
from ..database.tags import Tags
from .. import app, Session
from ..user.functions import token_required, after_token_required


@app.get('/video/tags')
@token_required
@after_token_required
def get_all_tags(current_user, session):
    """
Retrieves a list of all available tags.
---
security:
  - bearerAuth: []
tags:
  - Video
responses:
  200:
    description: List of tags retrieved successfully.
    content:
      application/json:
        schema:
          type: object
          properties:
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
  500:
    description: Error retrieving tags.
"""
    try:
        tags = session.query(Tags).all()
        tag_list = [{"id": tag.IdTag, "name": tag.TagName} for tag in tags]
        return jsonify({'tags': tag_list}), 200
    except Exception as e:
        app.logger.exception(f"Error retrieving tags: {e}")
        return jsonify({'message': 'Error retrieving tags'}), 500
