from flask import jsonify, request
from app.infra.db.sqlalchemy_db import get_session
from sqlalchemy import func
from app.domain.models import Challenge, UserChallenge, User, Task
from app.api.public.auth_routes import token_required
from app.api.admin.admin_middleware import admin_required, log_audit
from app.domain.schemas import (
    AdminChallengeSchema, AdminChallengeStatusSchema, validate_json_data
)
from app.infra.utils.admin_utils import paginate_query, format_response, parse_date_param
from datetime import datetime
import json


def init_admin_challenges_routes(app):
    @app.route('/admin/challenges', methods=['GET'])
    @token_required
    @admin_required
    def get_challenges():
        """Получить список челленджей с фильтрацией"""
        try:
            status = request.args.get('status', '')
            league = request.args.get('league', '')
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                query = session.query(Challenge)
                
                if status:
                    query = query.filter(Challenge.status == status)
                if league:
                    query = query.filter(Challenge.league == league)
                
                result = paginate_query(query.order_by(Challenge.id.desc()), page, limit)
                
                challenges_data = []
                for challenge in result['items']:
                    participants_count = session.query(func.count(UserChallenge.user_id)).filter(
                        UserChallenge.challenge_id == challenge.id
                    ).scalar() or 0
                    
                    challenges_data.append({
                        'id': challenge.id,
                        'name': challenge.name,
                        'points': challenge.points,
                        'description': challenge.description,
                        'startAt': challenge.start_at.isoformat() if challenge.start_at else None,
                        'endAt': challenge.end_at.isoformat() if challenge.end_at else None,
                        'status': challenge.status,
                        'league': challenge.league,
                        'coverImage': challenge.cover_image,
                        'participantsCount': participants_count
                    })
                
                return jsonify(format_response({
                    'challenges': challenges_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/challenges/<int:challenge_id>', methods=['GET'])
    @token_required
    @admin_required
    def get_challenge(challenge_id):
        """Получить челлендж по ID"""
        try:
            with get_session() as session:
                challenge = session.query(Challenge).filter_by(id=challenge_id).first()
                if not challenge:
                    return jsonify(format_response(None, 404, 'Challenge not found')), 404
                
                participants_count = session.query(func.count(UserChallenge.user_id)).filter(
                    UserChallenge.challenge_id == challenge_id
                ).scalar() or 0
                
                challenge_data = {
                    'id': challenge.id,
                    'name': challenge.name,
                    'points': challenge.points,
                    'description': challenge.description,
                    'startAt': challenge.start_at.isoformat() if challenge.start_at else None,
                    'endAt': challenge.end_at.isoformat() if challenge.end_at else None,
                    'status': challenge.status,
                    'league': challenge.league,
                    'coverImage': challenge.cover_image,
                    'participantsCount': participants_count
                }
                
                return jsonify(format_response(challenge_data))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/challenges', methods=['POST'])
    @token_required
    @admin_required
    def create_challenge():
        """Создать новый челлендж"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminChallengeSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                challenge = Challenge(
                    name=validated_data['name'],
                    points=validated_data.get('points', 0),
                    description=validated_data.get('description'),
                    start_at=validated_data.get('start_at'),
                    end_at=validated_data.get('end_at'),
                    status=validated_data.get('status', 'draft'),
                    league=validated_data.get('league'),
                    cover_image=validated_data.get('cover_image')
                )
                session.add(challenge)
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='create',
                    entity_type='challenge',
                    entity_id=challenge.id,
                    new_value=json.dumps({
                        'name': challenge.name,
                        'status': challenge.status
                    })
                )
                
                return jsonify(format_response({
                    'id': challenge.id,
                    'message': 'Challenge created successfully'
                })), 201
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/challenges/<int:challenge_id>', methods=['PATCH'])
    @token_required
    @admin_required
    def update_challenge(challenge_id):
        """Обновить челлендж"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminChallengeSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                challenge = session.query(Challenge).filter_by(id=challenge_id).first()
                if not challenge:
                    return jsonify(format_response(None, 404, 'Challenge not found')), 404
                
                old_values = {
                    'name': challenge.name,
                    'points': challenge.points,
                    'status': challenge.status,
                    'description': challenge.description
                }
                
                if 'name' in validated_data:
                    challenge.name = validated_data['name']
                if 'points' in validated_data:
                    challenge.points = validated_data['points']
                if 'description' in validated_data:
                    challenge.description = validated_data['description']
                if 'start_at' in validated_data:
                    challenge.start_at = validated_data['start_at']
                if 'end_at' in validated_data:
                    challenge.end_at = validated_data['end_at']
                if 'status' in validated_data:
                    challenge.status = validated_data['status']
                if 'league' in validated_data:
                    challenge.league = validated_data['league']
                if 'cover_image' in validated_data:
                    challenge.cover_image = validated_data['cover_image']
                
                new_values = {
                    'name': challenge.name,
                    'points': challenge.points,
                    'status': challenge.status,
                    'description': challenge.description
                }
                
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='update',
                    entity_type='challenge',
                    entity_id=challenge_id,
                    old_value=json.dumps(old_values),
                    new_value=json.dumps(new_values)
                )
                
                return jsonify(format_response({'message': 'Challenge updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/challenges/<int:challenge_id>/status', methods=['PATCH'])
    @token_required
    @admin_required
    def update_challenge_status(challenge_id):
        """Изменить статус челленджа"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminChallengeStatusSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                challenge = session.query(Challenge).filter_by(id=challenge_id).first()
                if not challenge:
                    return jsonify(format_response(None, 404, 'Challenge not found')), 404
                
                old_status = challenge.status
                challenge.status = validated_data['status']
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='status_change',
                    entity_type='challenge',
                    entity_id=challenge_id,
                    old_value=old_status,
                    new_value=challenge.status
                )
                
                return jsonify(format_response({'message': 'Challenge status updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/challenges/<int:challenge_id>', methods=['DELETE'])
    @token_required
    @admin_required
    def delete_challenge(challenge_id):
        """Удалить челлендж"""
        try:
            with get_session() as session:
                challenge = session.query(Challenge).filter_by(id=challenge_id).first()
                if not challenge:
                    return jsonify(format_response(None, 404, 'Challenge not found')), 404
                
                log_audit(
                    admin_id=request.user_id,
                    action='delete',
                    entity_type='challenge',
                    entity_id=challenge_id,
                    old_value=json.dumps({'name': challenge.name})
                )
                
                session.delete(challenge)
                session.commit()
                
                return jsonify(format_response({'message': 'Challenge deleted successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/challenges/<int:challenge_id>/participants', methods=['GET'])
    @token_required
    @admin_required
    def get_challenge_participants(challenge_id):
        """Получить список участников челленджа"""
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                challenge = session.query(Challenge).filter_by(id=challenge_id).first()
                if not challenge:
                    return jsonify(format_response(None, 404, 'Challenge not found')), 404
                
                query = session.query(UserChallenge, User).join(
                    User, UserChallenge.user_id == User.id
                ).filter(UserChallenge.challenge_id == challenge_id)
                
                result = paginate_query(query.order_by(UserChallenge.progress.desc()), page, limit)
                
                participants_data = []
                for uc, user in result['items']:
                    participants_data.append({
                        'userId': user.id,
                        'firstName': user.name,
                        'lastName': user.surname,
                        'email': user.email,
                        'progress': uc.progress,
                        'status': uc.status,
                        'league': user.league,
                        'points': user.points
                    })
                
                return jsonify(format_response({
                    'participants': participants_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/tasks', methods=['GET'])
    @token_required
    @admin_required
    def get_tasks():
        """Получить список задач"""
        try:
            challenge_id = request.args.get('challenge_id')
            status = request.args.get('status', '')
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                query = session.query(Task)
                
                if challenge_id:
                    query = query.filter(Task.challenge_id == challenge_id)
                if status:
                    query = query.filter(Task.status == status)
                
                result = paginate_query(query.order_by(Task.order.asc(), Task.id.asc()), page, limit)
                
                tasks_data = []
                for task in result['items']:
                    tasks_data.append({
                        'id': task.id,
                        'challengeId': task.challenge_id,
                        'title': task.title,
                        'description': task.description,
                        'status': task.status,
                        'points': task.points,
                        'order': task.order,
                        'createdAt': task.created_at.isoformat() if task.created_at else None,
                        'updatedAt': task.updated_at.isoformat() if task.updated_at else None
                    })
                
                return jsonify(format_response({
                    'tasks': tasks_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/tasks', methods=['POST'])
    @token_required
    @admin_required
    def create_task():
        """Создать задачу"""
        try:
            data = request.get_json()
            if not data.get('title'):
                return jsonify(format_response(None, 400, 'Title is required')), 400
            
            with get_session() as session:
                task = Task(
                    challenge_id=data.get('challenge_id'),
                    title=data['title'],
                    description=data.get('description'),
                    status=data.get('status', 'draft'),
                    points=data.get('points', 0),
                    order=data.get('order', 0)
                )
                session.add(task)
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='create',
                    entity_type='task',
                    entity_id=task.id,
                    new_value=json.dumps({'title': task.title})
                )
                
                return jsonify(format_response({
                    'id': task.id,
                    'message': 'Task created successfully'
                })), 201
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/tasks/<int:task_id>', methods=['PATCH'])
    @token_required
    @admin_required
    def update_task(task_id):
        """Обновить задачу"""
        try:
            data = request.get_json()
            
            with get_session() as session:
                task = session.query(Task).filter_by(id=task_id).first()
                if not task:
                    return jsonify(format_response(None, 404, 'Task not found')), 404
                
                old_values = {
                    'title': task.title,
                    'status': task.status
                }
                
                if 'title' in data:
                    task.title = data['title']
                if 'description' in data:
                    task.description = data['description']
                if 'status' in data:
                    task.status = data['status']
                if 'points' in data:
                    task.points = data['points']
                if 'order' in data:
                    task.order = data['order']
                if 'challenge_id' in data:
                    task.challenge_id = data['challenge_id']
                
                task.updated_at = datetime.utcnow()
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='update',
                    entity_type='task',
                    entity_id=task_id,
                    old_value=json.dumps(old_values),
                    new_value=json.dumps({
                        'title': task.title,
                        'status': task.status
                    })
                )
                
                return jsonify(format_response({'message': 'Task updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/tasks/<int:task_id>', methods=['DELETE'])
    @token_required
    @admin_required
    def delete_task(task_id):
        """Удалить задачу"""
        try:
            with get_session() as session:
                task = session.query(Task).filter_by(id=task_id).first()
                if not task:
                    return jsonify(format_response(None, 404, 'Task not found')), 404
                
                log_audit(
                    admin_id=request.user_id,
                    action='delete',
                    entity_type='task',
                    entity_id=task_id,
                    old_value=json.dumps({'title': task.title})
                )
                
                session.delete(task)
                session.commit()
                
                return jsonify(format_response({'message': 'Task deleted successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

