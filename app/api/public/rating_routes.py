from flask import jsonify
import logging
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import User, Team
from sqlalchemy import func, case

logger = logging.getLogger(__name__)


def init_rating_routes(app):
    @app.route('/participants-rating', methods=['GET'])
    def participants():
        try:
            with get_session() as session:
                league_order = case(
                    (User.league == 'gold', 1),
                    (User.league == 'silver', 2),
                    else_=3
                )
                rows = session.query(
                    User.id, User.surname, User.name, User.points, User.league, Team.name
                ).join(Team, Team.id == User.team_id, isouter=True).filter(
                    User.role.notin_(['admin', 'moderator'])
                ).order_by(User.points.desc(), league_order.asc()).all()
            leaderboard = []
            for row in rows:
                team_name = row[5] if row[5] is not None else "не определена"
                leaderboard.append({
                    'id': row[0],
                    'lastName': row[1],
                    'firstName': row[2],
                    'progress': row[3],
                    'league': row[4],
                    'team': team_name
                })
            return jsonify({'status': 200, 'message': 'Users rating created successfully', 'leaderboard': leaderboard})
        except Exception as e:
            logger.error(f"Error fetching participants rating: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/teams-rating', methods=['GET'])
    def teams():
        try:
            with get_session() as session:
                rows = session.query(
                    Team.id, Team.name, func.sum(User.points).label('points'), func.count(User.id).label('members')
                ).join(User, Team.id == User.team_id).filter(
                    User.role.notin_(['admin', 'moderator'])
                ).group_by(Team.id, Team.name).order_by(func.sum(User.points).desc()).all()
            leaderboard = []
            for row in rows:
                leaderboard.append({
                    'id': row[0],
                    'name': row[1],
                    'totalProgress': int(row[2] or 0),
                    'members': int(row[3] or 0)
                })
            return jsonify({'status': 200, 'message': 'Teams rating created successfully', 'leaderboard': leaderboard})
        except Exception as e:
            logger.error(f"Error fetching teams rating: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

