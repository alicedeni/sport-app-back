from flask import jsonify, request
import math
import logging
from app.api.public.auth_routes import token_required
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import User, Team, UserProgress
from werkzeug.security import generate_password_hash
from app.domain.models import TokenBlacklist
from app.domain.models import Feed
from sqlalchemy import func

logger = logging.getLogger(__name__)


def init_user_routes(app):
    @app.route('/participants/progress', methods=['GET'])
    def get_total_participants_progress():
        # 1 000 км
        goal_calories = 10000

        with get_session() as session:
            total_calories = session.query(func.sum(Feed.calories)).scalar() or 0

        total_calories = 10000
        all_progress = min((total_calories / goal_calories) * 100, 100)

        return jsonify({'status': 200, 'all_progress': round(all_progress, 2)})

    @app.route('/hide_welcome', methods=['POST'])
    @token_required
    def hide_welcome():
        user_id = request.user_id

        try:
            with get_session() as session:
                session.query(User).filter(User.id == user_id, User.show_welcome == True).update({User.show_welcome: False})
                session.commit()
                current_value = session.query(User.show_welcome).filter(User.id == user_id).scalar()
                return jsonify({'status': 200, 'message': 'Welcome banner state updated', 'show_welcome': bool(current_value)})
        except Exception as e:
            return jsonify({'status': 500, 'message': f'Error updating banner status: {str(e)}'}), 500

    @app.route('/main', methods=['GET'])
    @token_required
    def main():
        user_id = request.user_id

        try:
            with get_session() as session:
                u = session.query(User.name, User.avatar, User.points, User.show_welcome).filter(User.id == user_id).first()
                if not u:
                    return jsonify({'status': 404, 'message': 'User not found'})

                team_count = session.query(Team.id).count()
                participant_count = session.query(User.id).count()
                total_points_rows = session.query(User.points).all()
                total_points = sum([(row[0] or 0) for row in total_points_rows])

                progress = min((total_points / (10562 * 10)) * 100, 100)
                distance = max(0, math.floor(total_points / 10))

                return jsonify({
                    'status': 200,
                    'name': u[0],
                    'avatar': u[1],
                    'points': u[2],
                    'teams': team_count,
                    'participants': participant_count,
                    'count': distance,
                    'goal': progress,
                    'show_welcome': u[3]
            })
        except Exception as e:
            return jsonify({'status': 500, 'message': f'Error fetching data: {str(e)}'}), 500


    @app.route('/profile', methods=['GET'])
    @token_required
    def profile():
        user_id = request.user_id

        try:
            with get_session() as session:
                q = session.query(
                    User.id,
                    User.surname,
                    User.name,
                    User.email,
                    User.height,
                    User.weight,
                    User.points,
                    User.avatar,
                    User.league,
                    Team.name,
                    User.f_hello,
                    User.show_welcome
                ).join(Team, Team.id == User.team_id, isouter=True).filter(User.id == user_id)
                user_profile = q.first()

                if not user_profile:
                    return jsonify({'status': 404, 'message': 'User not found'})

                place_league = 100
                league_value = user_profile[8]
                if league_value:
                    higher = session.query(User.id).filter(User.league == league_value, User.points > (user_profile[6] or 0)).count()
                    place_league = higher + 1

                goal_row = session.query(UserProgress.target_weight).filter(UserProgress.user_id == user_id).first()
                target_weight = goal_row[0] if goal_row else None

                profile_data = {
                    'id': user_profile[0],
                    'lastName': user_profile[1],
                    'firstName': user_profile[2],
                    'email': user_profile[3],
                    'height': user_profile[4],
                    'weight': user_profile[5],
                    'points': user_profile[6],
                    'avatar': user_profile[7],
                    'team': user_profile[9],
                    'league': user_profile[8],
                    'place_league': place_league,
                    'target_weight': target_weight,
                    'f_hello': bool(user_profile[10]) if user_profile[10] is not None else False,
                    'show_welcome': bool(user_profile[11]) if user_profile[11] is not None else True
                }

                return jsonify({'status': 200, 'profile': profile_data})
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})


    @app.route('/user/team_members', methods=['GET'])
    @token_required
    def get_team_members():
        user_id = request.user_id

        try:
            with get_session() as session:
                team_id = session.query(User.team_id).filter(User.id == user_id).scalar()
                if not team_id:
                    return jsonify({'status': 400, 'message': 'team_id is required'}), 400

                members = session.query(User.id, User.name, User.surname).filter(User.team_id == team_id).all()
                if not members:
                    return jsonify({'status': 404, 'message': 'No members found for the team'}), 404

                team_members = [{'id': m[0], 'name': m[1], 'surname': m[2]} for m in members]
                return jsonify({'status': 200, 'teamMembers': team_members}), 200
        except Exception as e:
            logger.error(f"Error fetching team members: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/user/progress', methods=['GET'])
    @token_required
    def get_weight_progress():
        user_id = request.user_id

        try:
            with get_session() as session:
                prog = session.query(UserProgress.target_weight, UserProgress.start_weight).filter(UserProgress.user_id == user_id).first()
                if not prog:
                    return jsonify({'status': 200, 'progress': 0})

                target_weight, start_weight = prog
                current_weight = session.query(User.weight).filter(User.id == user_id).scalar()

                if target_weight is None or start_weight is None or current_weight is None:
                    return jsonify({'status': 500, 'message': 'Invalid weight data'}), 500

                if target_weight > start_weight:
                    if current_weight >= start_weight:
                        progress = min(100, (current_weight - start_weight) / (target_weight - start_weight) * 100)
                    else:
                        progress = 0
                else:
                    if current_weight <= start_weight:
                        progress = min(100, (start_weight - current_weight) / (start_weight - target_weight) * 100)
                    else:
                        progress = 0

                return jsonify({'status': 200, 'progress': progress})
        except Exception as e:
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500


    @app.route('/user/set_goal', methods=['POST'])
    @token_required
    def set_weight_goal():
        user_id = request.user_id

        data = request.get_json()
        target_weight = data.get('target_weight')
        current_weight = data.get('weight')

        if target_weight is None or current_weight is None:
            return jsonify({'status': 400, 'message': 'Target weight or current weight not provided'}), 400

        try:
            with get_session() as session:
                existing = session.query(UserProgress).filter(UserProgress.user_id == user_id).first()
                if existing:
                    existing.target_weight = target_weight
                    existing.start_weight = current_weight
                else:
                    session.add(UserProgress(user_id=user_id, target_weight=target_weight, start_weight=current_weight))
                session.commit()
                return jsonify({'status': 200, 'message': 'Goal saved successfully'})
        except Exception as e:
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500



    @app.route('/edit_person_data', methods=['POST'])
    @token_required
    def edit_person_data():
        user_id = request.user_id

        data = request.json
        age = data.get('age')
        height = data.get('height')
        weight = data.get('weight')

        try:
            with get_session() as session:
                updates = {}
                if age is not None:
                    updates[User.age] = age
                if height is not None:
                    updates[User.height] = height
                if weight is not None:
                    updates[User.weight] = weight

                if not updates:
                    return jsonify({'status': 400, 'message': 'No data provided for update'})

                session.query(User).filter(User.id == user_id).update(updates)
                session.commit()
                return jsonify({'status': 200, 'message': 'User data updated successfully'})
        except Exception as e:
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/edit_fio_data', methods=['POST'])
    @token_required
    def edit_fio_data():
        user_id = request.user_id

        data = request.json
        name = data.get('firstName')
        surname = data.get('lastName')
        email = data.get('email')
        password = data.get('password')
        avatar = data.get('avatar')

        try:
            with get_session() as session:
                updates = {}
                if name is not None:
                    updates[User.name] = name
                if surname is not None:
                    updates[User.surname] = surname
                if email is not None:
                    updates[User.email] = email
                if password is not None:
                    updates[User.password] = generate_password_hash(password)
                if avatar is not None:
                    updates[User.avatar] = avatar

                if not updates:
                    return jsonify({'status': 400, 'message': 'No data provided for update'})

                session.query(User).filter(User.id == user_id).update(updates)
                session.commit()
                return jsonify({'status': 200, 'message': 'User info updated successfully'})
        except Exception as e:
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/logout', methods=['POST'])
    def logout():
        try:
            token = request.headers.get('Authorization')
            if not token or not token.startswith("Bearer "):
                return jsonify({"error": "Invalid token", "status": 400})

            token = token.split("Bearer ")[1]

            with get_session() as session:
                exists = session.query(TokenBlacklist.id).filter(TokenBlacklist.token == token).first()
                if exists:
                    return jsonify({'status': 400, 'error': 'Token is already blacklisted'}), 400
                session.add(TokenBlacklist(token=token))
                session.commit()
                return jsonify({'status': 200, 'message': 'Logged out successfully'})

        except Exception as e:
            return jsonify({'status': 500, 'error': str(e)})

    # @app.route('/delete_account', methods=['DELETE'])
    # @token_required
    # def delete_account():
    #     user_id = request.user_id
    #     token = request.headers.get('Authorization').split("Bearer ")[1]
    #     try:
    #         execute_query('DELETE FROM users WHERE id = %s', (user_id,), delete=True)
    #         execute_query('INSERT INTO token_blacklist (token) VALUES (%s)', (token,))
    #         return jsonify({'status': 200, 'message': 'Account deleted successfully'})
    #     except Exception as e:
    #         return jsonify({'status': 500, 'error': str(e)})


