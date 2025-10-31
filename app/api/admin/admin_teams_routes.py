from flask import jsonify, request
from app.infra.db.sqlalchemy_db import get_session
from sqlalchemy import func
from app.domain.models import Team, User
from app.api.public.auth_routes import token_required
from app.api.admin.admin_middleware import admin_required, log_audit
from app.infra.utils.admin_utils import format_response, paginate_query


def init_admin_teams_routes(app):
    @app.route('/admin/teams', methods=['GET'])
    @token_required
    @admin_required
    def get_teams():
        try:
            query_str = (request.args.get('query') or '').strip()
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))

            with get_session() as session:
                base = session.query(
                    Team.id,
                    Team.name,
                    func.coalesce(func.sum(User.points), 0).label('total_points'),
                    func.count(User.id).label('members_count')
                ).join(User, Team.id == User.team_id, isouter=True)

                if query_str:
                    base = base.filter(Team.name.ilike(f'%{query_str}%'))

                base = base.group_by(Team.id, Team.name).order_by(func.coalesce(func.sum(User.points), 0).desc())

                total = base.count()
                items = base.offset((page - 1) * limit).limit(limit).all()

                teams = []
                for team_id, name, total_points, members_count in items:
                    teams.append({
                        'id': team_id,
                        'name': name,
                        'totalPoints': int(total_points or 0),
                        'members': int(members_count or 0)
                    })

                return jsonify(format_response({
                    'teams': teams,
                    'pagination': {
                        'total': total,
                        'page': page,
                        'limit': limit,
                        'pages': (total + limit - 1) // limit
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500
    @app.route('/admin/teams', methods=['POST'])
    @token_required
    @admin_required
    def create_team():
        try:
            data = request.get_json() or {}
            name = (data.get('name') or '').strip()
            if not name:
                return jsonify(format_response(None, 400, 'Team name is required')), 400

            with get_session() as session:
                exists = session.query(Team.id).filter(Team.name == name).first()
                if exists:
                    return jsonify(format_response(None, 400, 'Team with this name already exists')), 400

                team = Team(name=name, points=0)
                session.add(team)
                session.commit()

                log_audit(
                    admin_id=request.user_id,
                    action='create',
                    entity_type='team',
                    entity_id=team.id,
                    new_value=name
                )

                return jsonify(format_response({'id': team.id, 'message': 'Team created successfully'})), 201
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/teams/<int:team_id>', methods=['PATCH'])
    @token_required
    @admin_required
    def update_team(team_id: int):
        try:
            data = request.get_json() or {}
            name = (data.get('name') or '').strip()
            if not name:
                return jsonify(format_response(None, 400, 'Team name is required')), 400

            with get_session() as session:
                team = session.query(Team).filter(Team.id == team_id).first()
                if not team:
                    return jsonify(format_response(None, 404, 'Team not found')), 404

                old_name = team.name
                team.name = name
                session.commit()

                log_audit(
                    admin_id=request.user_id,
                    action='update',
                    entity_type='team',
                    entity_id=team_id,
                    old_value=old_name,
                    new_value=name
                )

                return jsonify(format_response({'message': 'Team updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/teams/<int:team_id>', methods=['DELETE'])
    @token_required
    @admin_required
    def delete_team(team_id: int):
        try:
            with get_session() as session:
                team = session.query(Team).filter(Team.id == team_id).first()
                if not team:
                    return jsonify(format_response(None, 404, 'Team not found')), 404

                session.query(User).filter(User.team_id == team_id).update({User.team_id: None})

                log_audit(
                    admin_id=request.user_id,
                    action='delete',
                    entity_type='team',
                    entity_id=team_id,
                    old_value=team.name
                )

                session.delete(team)
                session.commit()

                return jsonify(format_response({'message': 'Team deleted successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/teams/<int:team_id>/users', methods=['POST'])
    @token_required
    @admin_required
    def add_user_to_team(team_id: int):
        try:
            data = request.get_json() or {}
            user_id = data.get('user_id')
            if not user_id:
                return jsonify(format_response(None, 400, 'user_id is required')), 400

            with get_session() as session:
                team = session.query(Team).filter(Team.id == team_id).first()
                if not team:
                    return jsonify(format_response(None, 404, 'Team not found')), 404

                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return jsonify(format_response(None, 404, 'User not found')), 404

                if user.team_id and user.team_id != team_id:
                    return jsonify(format_response(None, 400, f'User already in team {user.team_id}. Remove first.')), 400

                if user.team_id == team_id:
                    return jsonify(format_response({'message': 'User is already in this team'}))

                old_team_id = user.team_id
                user.team_id = team_id
                session.commit()

                log_audit(
                    admin_id=request.user_id,
                    action='update',
                    entity_type='user',
                    entity_id=user.id,
                    old_value=f'team_id={old_team_id}',
                    new_value=f'team_id={team_id}'
                )

                return jsonify(format_response({'message': 'User added to team'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/teams/<int:team_id>/users/<int:user_id>', methods=['DELETE'])
    @token_required
    @admin_required
    def remove_user_from_team(team_id: int, user_id: int):
        try:
            with get_session() as session:
                team = session.query(Team).filter(Team.id == team_id).first()
                if not team:
                    return jsonify(format_response(None, 404, 'Team not found')), 404

                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return jsonify(format_response(None, 404, 'User not found')), 404

                if user.team_id != team_id:
                    return jsonify(format_response(None, 400, 'User is not in this team')), 400

                user.team_id = None
                session.commit()

                log_audit(
                    admin_id=request.user_id,
                    action='update',
                    entity_type='user',
                    entity_id=user.id,
                    old_value=f'team_id={team_id}',
                    new_value='team_id=None'
                )

                return jsonify(format_response({'message': 'User removed from team'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/teams/<int:team_id>/users', methods=['GET'])
    @token_required
    @admin_required
    def list_team_users(team_id: int):
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            query_str = (request.args.get('query') or '').strip()

            with get_session() as session:
                team = session.query(Team).filter(Team.id == team_id).first()
                if not team:
                    return jsonify(format_response(None, 404, 'Team not found')), 404

                q = session.query(User).filter(User.team_id == team_id)
                if query_str:
                    q = q.filter((User.name.ilike(f'%{query_str}%')) | (User.surname.ilike(f'%{query_str}%')) | (User.email.ilike(f'%{query_str}%')))

                total = q.count()
                items = q.order_by(User.points.desc()).offset((page - 1) * limit).limit(limit).all()

                users = []
                for u in items:
                    users.append({
                        'id': u.id,
                        'email': u.email,
                        'firstName': u.name,
                        'lastName': u.surname,
                        'league': u.league,
                        'points': int(u.points or 0)
                    })

                return jsonify(format_response({
                    'team': { 'id': team.id, 'name': team.name },
                    'users': users,
                    'pagination': {
                        'total': total,
                        'page': page,
                        'limit': limit,
                        'pages': (total + limit - 1) // limit
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500


