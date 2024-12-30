import datetime
from .. import app, ALLOWED_VIDEO_EXTENSIONS, ALLOWED_AUDIO_EXTENSIONS
from ..user.functions import token_required, after_token_required
from ..database.users import Users
from ..database.media import Media
from ..database.tags import Tags
from ..database.companies import Companies
from ..database.searchHistory import SearchHistory
from flask import Flask, jsonify, request
from sqlalchemy import func, or_, and_

app: Flask


@app.post('/search')
@token_required
@after_token_required
def search(user, session):
    """
    Searches for data across users, videos, audio (if implemented), and companies.
    ---
    tags:
      - Search
    security:
      - bearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              type:
                type: array
                items:
                  type: string
                  enum: ["user", "video", "audio", "company"]
                description: Types of data to search.
              tags:
                type: array
                items:
                  type: integer
                description: IDs of tags to filter videos by.
              request:
                type: string
                description: The search text.
    responses:
      200:
        description: Search results.
        content:
          application/json:
            schema:
              type: object
              properties:
                user:
                  type: array
                  items:
                    type: object # Define user object properties
                video:
                  type: array
                  items:
                    type: object # Define video object properties
                audio:
                  type: array
                  items:
                    type: object # Define audio object properties
                company:
                  type: array
                  items:
                    type: object # Define company object properties
      500:
        description: Internal server error.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No data provided'}), 400
        search_types = data.get('type', [])
        tag_ids = data.get('tags', [])
        search_text = data.get('request', '')

        # Adding search_text to database
        existing_search = session.query(SearchHistory).filter_by(SearchQuery=search_text).first()
        user_searches = session.query(SearchHistory).filter_by(IdUser=user.IdUser).order_by(SearchHistory.SearchTime.desc()).all()
        count_of_searches = len(user_searches)

        if count_of_searches >= 10 and not existing_search:
            while count_of_searches >= 10:
                search_to_remove = user_searches[0]
                session.delete(search_to_remove)
                session.commit()
                session.flush()
                count_of_searches -= 1

        if len(search_text) != 0:
            if not existing_search:
                search = SearchHistory(
                    IdUser=user.IdUser,
                    SearchQuery=search_text,
                    SearchTime=datetime.datetime.now()
                )
                session.add(search)
            else:
                existing_search.SearchTime = datetime.datetime.now()
            session.commit()

        if not isinstance(search_types, list):
            return jsonify({'message': 'Type must be a list'}), 400

        if not isinstance(tag_ids, list):
            return jsonify({'message': 'Tags must be a list'}), 400

        if not all(isinstance(x, int) for x in tag_ids):
            return jsonify({'message': 'Tags must be integer'}), 400

        results = {
            "user": [],
            "video": [],
            "audio": [],
            "company": []
        }

        if not search_types:
            search_types = ["user", "video", "audio", "company"] # Search all types

        if "user" in search_types:
            user_results = session.query(Users).filter(
                or_(
                    Users.NameUser.ilike(f"%{search_text}%"),
                    Users.Surname.ilike(f"%{search_text}%"),
                    Users.LoginUser.ilike(f"%{search_text}%"),
                    Users.Email.ilike(f"%{search_text}%")
                )
            ).all()
            results["user"] = [{
                "user_id": user.IdUser,
                "name": user.NameUser + " " + user.Surname,
                "email": user.Email} for user in user_results]

        if "video" in search_types or "audio" in search_types:
            media_query = session.query(Media).filter(
                or_(
                    Media.NameV.ilike(f"%{search_text}%"),
                    Media.DescriptionV.ilike(f"%{search_text}%")
                ))

            if tag_ids:
                media_query = media_query.join(Media.tags).filter(Tags.IdTag.in_(tag_ids))

            # Splitting into video and audio
            media_results = media_query.all()

            video_results = media_query.filter(or_(*[Media.VideoPath.ilike(f"%{ext}") for ext in ALLOWED_VIDEO_EXTENSIONS])).all()
            audio_results = media_query.filter(or_(*[Media.VideoPath.ilike(f"%{ext}") for ext in ALLOWED_AUDIO_EXTENSIONS])).all()

            if "video" in search_types:
                results["video"] = [{
                    "id": video.IdMedia,
                    "name": video.NameV,
                    "description": video.DescriptionV,
                    "upload_time": video.UploadTime.isoformat(),
                    "company_id": video.companies.IdCompany,
                    "company_name": video.companies.Name} for video in video_results]

            if "audio" in search_types:
                results["audio"] = [{
                    "id": audio.IdMedia,
                    "name": audio.NameV,
                    "description": audio.DescriptionV,
                    "upload_time": audio.UploadTime.isoformat(),
                    "company_id": audio.companies.IdCompany,
                    "company_name": audio.companies.Name} for audio in audio_results]

        if "company" in search_types:
            company_results = session.query(Companies).filter(Companies.Name.ilike(f"%{search_text}%")).all()
            results["company"] = [{
                "company_id": company.IdCompany,
                "name": company.Name,
                "about": company.About} for company in company_results]

        return jsonify(results), 200

    except Exception as e:
        app.logger.exception(f"Search error: {e}")
        return jsonify({'message': 'Internal server error'}), 500


@app.get('/search/history')
@token_required
@after_token_required
def get_search_history(user, session):
    """
    Retrieves the search history for the current user.
    ---
    security:
      - bearerAuth: []
    tags:
      - Search
    responses:
      200:
        description: Search history retrieved successfully.
        content:
          application/json:
            schema:
              type: array
              items:
                type: object
                properties:
                  IdSearchHistory:
                    type: integer
                    description: The ID of the search history entry.
                  SearchQuery:
                    type: string
                    description: The search query.
                  SearchTime:
                    type: string
                    format: date-time
                    description: The time of the search in ISO 8601 format.
      500:
        description: Internal server error.
    """
    try:
        search_history = session.query(SearchHistory).filter_by(IdUser=user.IdUser).order_by(SearchHistory.SearchTime.desc()).all()

        history_list = []
        for history_entry in search_history:
            history_list.append({
                "IdSearchHistory": history_entry.IdSearchHistory,
                "SearchQuery": history_entry.SearchQuery,
                "SearchTime": history_entry.SearchTime.isoformat() if history_entry.SearchTime else None
            })

        return jsonify(history_list), 200

    except Exception as e:
        app.logger.exception(f"Error retrieving search history: {e}")
        return jsonify({'message': 'Internal server error'}), 500
