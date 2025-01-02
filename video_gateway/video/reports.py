from .. import app, redis_client, Session
from flask import Flask, jsonify
from ..helpers.functions import token_required, after_token_required, moderator_level, get_access_level_by_name
from ..database.userRoles import UserRoles
from ..database.reports import Reports
from ..database.comments import Comments
from ..database.media import Media
from ..database.companies import Companies
from ..database.accessLevels import AccessLevels

app: Flask


@app.get('/reports')
@token_required(app, redis_client, Session)
@moderator_level
@after_token_required
def get_reports(user, session):
    """
    Retrieves all reports for companies where the current user is a moderator.
    ---
    security:
      - bearerAuth: []
    tags:
      - Reports
    responses:
      200:
        description: List of reports retrieved successfully.
        content:
          application/json:
            schema:
              type: array
              items:
                type: object
                properties:
                  report_id:
                    type: integer
                    description: The ID of the report.
                  report_date:
                    type: string
                    format: date-time
                    description: The time the report was created.
                  comment_id:
                    type: integer
                    description: The ID of the reported comment.
                  user_id:
                    type: integer
                    description: The ID of the user who created the report.
                  report_reason:
                    type: string
                    description: The reason for the report.
                  comment:
                    type: string
                    description: Text of reported comment.
                  user_login:
                      type: string
                      description: Login of user, who reported this comment.
                  video_id:
                      type: integer
                      description: Id of a media, which was reported.
                  video_name:
                      type: string
                      description: Name of a reported video.
      500:
        description: Internal server error.
    """
    try:
        # Get the "Moderator" access level
        moderator_level = get_access_level_by_name(session, "Moderator")
        if not moderator_level:
            app.logger.error("Moderator Access Level not found in database")
            return jsonify({'message': 'Internal server error'}), 500

        # Get companies where the current user is a moderator
        moderated_companies = session.query(UserRoles).join(UserRoles.access_levels).filter(
            UserRoles.IdUser == user.IdUser,
            AccessLevels.AccessLevel >= moderator_level.AccessLevel
        ).all()

        if not moderated_companies:
            return jsonify([]), 200

        company_ids = [mc.IdCompany for mc in moderated_companies]

        # Get reports for comments from videos from moderated companies
        reports = session.query(Reports).join(Reports.comments)\
                         .join(Comments.media).join(Media.companies)\
                         .filter(Companies.IdCompany.in_(company_ids)).all()

        report_list = []
        for report in reports:
            report_list.append({
                "report_id": report.IdReport,
                "report_time": report.ReportTime.isoformat() if report.ReportTime else None,
                "comment_id": report.IdComment,
                "user_id": report.comments.users.IdUser,
                "report_reason": report.ReportReason,
                "comment": report.comments.TextComment,
                "user_name": report.comments.users.NameUser + " " + report.comments.users.Surname,
                "video_id": report.comments.media.IdMedia,
                "video_name": report.comments.media.NameV,
            })

        return jsonify(report_list), 200

    except Exception as e:
        app.logger.exception(f"Error retrieving reports: {e}")
        return jsonify({'message': 'Internal server error'}), 500


@app.post('/reports/<int:id>/approve')
@token_required(app, redis_client, Session)
@moderator_level
@after_token_required
def approve_report(user, session, id):
    """
    Approves a report and deletes the reported comment. (>Moderator)
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
        description: The ID of the report to approve.
    responses:
      200:
        description: Report approved and comment deleted successfully.
      404:
        description: Report not found.
      403:
        description: Forbidden. Admin/Moderator access required.
      500:
        description: Internal server error.
    """
    try:
        report = session.query(Reports).join(Reports.comments).filter(Reports.IdReport==id).first()
        if not report:
            return jsonify({'message': 'Report not found'}), 404

        comment_to_delete = report.comments  # Get the related comment
        if not comment_to_delete:
            return jsonify({'message': 'Comment associated with this report not found'}), 404

        session.delete(report) # Delete the report
        linked_reports = comment_to_delete.reports
        for report_ in linked_reports:
            session.delete(report_)
        session.delete(comment_to_delete)
        session.commit()

        return jsonify({'message': 'Report approved and comment deleted successfully'}), 200

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error approving report: {e}")
        return jsonify({'message': 'Internal server error'}), 500


@app.post('/reports/<int:id>/dismiss')
@token_required(app, redis_client, Session)
@moderator_level
@after_token_required
def dismiss_report(user, session, id):
    """
    Dismisses a report (removes the report without deleting the comment). (>Moderator)
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
        description: The ID of the report to dismiss.
    responses:
      200:
        description: Report dismissed successfully.
      404:
        description: Report not found.
      403:
        description: Forbidden. Admin/Moderator access required.
      500:
        description: Internal server error.
    """
    try:
        report = session.query(Reports).filter_by(IdReport=id).first()
        if not report:
            return jsonify({'message': 'Report not found'}), 404

        session.delete(report)  # Delete the report
        session.commit()

        return jsonify({'message': 'Report dismissed successfully'}), 200

    except Exception as e:
        session.rollback()
        app.logger.exception(f"Error dismissing report: {e}")
        return jsonify({'message': 'Internal server error'}), 500

