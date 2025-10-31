from flask import Flask, jsonify, request
import logging
from app.api.public.auth_routes import token_required
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import Challenge, UserChallenge, UserChallengeStatus

app = Flask(__name__)
logger = logging.getLogger(__name__)


def init_challenges_routes(app):
    @app.route('/api/user_challenge_statuses', methods=['GET'])
    @token_required
    def get_statuses():
        user_id = request.user_id
        try:
            with get_session() as session:
                row = session.query(UserChallengeStatus).filter_by(user_id=user_id).first()
            if row:
                status = {
                    'status_challenge1': row.status_challenge1,
                    'status_challenge2': row.status_challenge2,
                    'status_challenge3': row.status_challenge3
                }
            else:
                status = {
                    'status_challenge1': 'нет участия',
                    'status_challenge2': 'нет участия',
                    'status_challenge3': 'нет участия'
                }
            return jsonify({'status': 200, 'data': status})
        except Exception as e:
            logger.error(f'Error fetching statuses: {e}', exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/api/user_challenge_statuses/participate', methods=['POST'])
    @token_required
    def participate():
        user_id = request.user_id
        data = request.json
        challenge_id = data.get('challenge_id')
        if not challenge_id or challenge_id not in [1, 2, 3]:
            return jsonify({'status': 400, 'message': 'Invalid challenge_id'}), 400
        column = f'status_challenge{challenge_id}'
        try:
            with get_session() as session:
                row = session.query(UserChallengeStatus).filter(UserChallengeStatus.user_id == user_id).first()
                if row:
                    setattr(row, column, 'участвует')
                else:
                    new_row = UserChallengeStatus(user_id=user_id)
                    setattr(new_row, column, 'участвует')
                    session.add(new_row)
                session.commit()
            return jsonify({'status': 200, 'message': 'Статус обновлен'})
        except Exception as e:
            logger.error(f'Error updating status: {e}', exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/user/available-challenges', methods=['GET'])
    @token_required
    def available_challenges():
        user_id = request.user_id
        try:
            with get_session() as session:
                sub = session.query(UserChallenge.challenge_id).filter(UserChallenge.user_id == user_id)
                rows = session.query(Challenge.id, Challenge.name, Challenge.points).filter(~Challenge.id.in_(sub)).all()
            available = [{'id': r[0], 'name': r[1], 'points': r[2]} for r in rows]
            return jsonify({'status': 200, 'message': 'Available challenges fetched successfully', 'available_challenges': available})
        except Exception as e:
            return jsonify({'status': 500, 'message': f'Error fetching data: {str(e)}'}), 500

    @app.route('/user/current-challenges', methods=['GET'])
    @token_required
    def current_challenges():
        user_id = request.user_id
        try:
            with get_session() as session:
                rows = session.query(Challenge.id, Challenge.name, UserChallenge.progress, Challenge.points).join(UserChallenge, UserChallenge.challenge_id == Challenge.id).filter(UserChallenge.user_id == user_id, UserChallenge.status == 'current').all()
            current = [{'id': r[0], 'name': r[1], 'progress': r[2], 'points': r[3]} for r in rows]
            return jsonify({'status': 200, 'message': 'successfully', 'current_challenges': current})
        except Exception as e:
            return jsonify({'status': 500, 'message': f'Error fetching data: {str(e)}'}), 500

    @app.route('/user/completed-challenges', methods=['GET'])
    @token_required
    def completed_challenges():
        user_id = request.user_id
        try:
            with get_session() as session:
                rows = session.query(Challenge.id, Challenge.name, UserChallenge.progress, Challenge.points).join(UserChallenge, UserChallenge.challenge_id == Challenge.id).filter(UserChallenge.user_id == user_id, UserChallenge.status == 'completed').all()
            completed = [{'id': r[0], 'name': r[1], 'progress': r[2], 'points': r[3]} for r in rows]
            return jsonify({'status': 200, 'message': 'successfully', 'completed_challenges': completed})
        except Exception as e:
            return jsonify({'status': 500, 'message': f'Error fetching data: {str(e)}'}), 500


