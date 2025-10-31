from flask import jsonify, request
from app.infra.db.sqlalchemy_db import get_session
from sqlalchemy import or_, func
from app.domain.models import User, AuditLog
from app.api.public.auth_routes import token_required
from app.api.admin.admin_middleware import admin_required, log_audit
from app.domain.schemas import (
    AdminUserCreateSchema, AdminUserUpdateSchema, AdminUserStatusSchema, 
    AdminUserRoleSchema, validate_json_data, sanitize_string
)
from werkzeug.security import generate_password_hash
from app.infra.utils.admin_utils import paginate_query, build_filter_query, format_response, parse_date_param
from datetime import datetime
import json


def init_admin_users_routes(app):
    @app.route('/admin/users', methods=['GET'])
    @token_required
    @admin_required
    def get_users():
        """Получить список пользователей с фильтрацией и пагинацией"""
        try:
            query = request.args.get('query', '').strip()
            role = request.args.get('role', '')
            status = request.args.get('status', '')
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                base_query = session.query(User)
                
                if query:
                    base_query = base_query.filter(
                        or_(
                            User.name.ilike(f'%{query}%'),
                            User.surname.ilike(f'%{query}%'),
                            User.email.ilike(f'%{query}%')
                        )
                    )
                
                if role:
                    base_query = base_query.filter(User.role == role)
                
                if status == 'active':
                    base_query = base_query.filter(User.is_active == True)
                elif status == 'inactive':
                    base_query = base_query.filter(User.is_active == False)
                elif status == 'banned':
                    base_query = base_query.filter(User.banned_until.isnot(None), User.banned_until > datetime.utcnow())
                
                result = paginate_query(base_query.order_by(User.created_at.desc()), page, limit)
                
                users_data = []
                for user in result['items']:
                    users_data.append({
                        'id': user.id,
                        'email': user.email,
                        'firstName': user.name,
                        'lastName': user.surname,
                        'role': user.role,
                        'status': 'banned' if user.banned_until and user.banned_until > datetime.utcnow() else ('active' if user.is_active else 'inactive'),
                        'isActive': user.is_active,
                        'bannedUntil': user.banned_until.isoformat() if user.banned_until else None,
                        'avatar': user.avatar,
                        'createdAt': user.created_at.isoformat() if user.created_at else None,
                        'lastLoginAt': user.last_login_at.isoformat() if user.last_login_at else None,
                        'points': user.points
                    })
                
                return jsonify(format_response({
                    'users': users_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/users/<int:user_id>', methods=['GET'])
    @token_required
    @admin_required
    def get_user(user_id):
        """Получить пользователя по ID"""
        try:
            with get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return jsonify(format_response(None, 404, 'User not found')), 404
                
                user_data = {
                    'id': user.id,
                    'email': user.email,
                    'firstName': user.name,
                    'lastName': user.surname,
                    'midname': user.midname,
                    'role': user.role,
                    'status': 'banned' if user.banned_until and user.banned_until > datetime.utcnow() else ('active' if user.is_active else 'inactive'),
                    'isActive': user.is_active,
                    'bannedUntil': user.banned_until.isoformat() if user.banned_until else None,
                    'avatar': user.avatar,
                    'age': user.age,
                    'gender': user.gender,
                    'height': user.height,
                    'weight': user.weight,
                    'points': user.points,
                    'league': user.league,
                    'createdAt': user.created_at.isoformat() if user.created_at else None,
                    'lastLoginAt': user.last_login_at.isoformat() if user.last_login_at else None
                }
                return jsonify(format_response(user_data))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/users', methods=['POST'])
    @token_required
    @admin_required
    def create_user():
        """Создать нового пользователя"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminUserCreateSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                existing = session.query(User).filter_by(email=validated_data['email'].lower()).first()
                if existing:
                    return jsonify(format_response(None, 400, 'Email already exists')), 400
                
                new_user = User(
                    surname=sanitize_string(validated_data['surname']),
                    name=sanitize_string(validated_data['name']),
                    email=validated_data['email'].lower(),
                    password=generate_password_hash(validated_data['password']),
                    role=validated_data.get('role', 'user'),
                    is_active=validated_data.get('is_active', True)
                )
                session.add(new_user)
                session.commit()
                session.refresh(new_user)
                
                log_audit(
                    admin_id=request.user_id,
                    action='create',
                    entity_type='user',
                    entity_id=new_user.id,
                    new_value=json.dumps({'email': new_user.email, 'role': new_user.role})
                )
                
                return jsonify(format_response({'id': new_user.id, 'message': 'User created successfully'})), 201
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/users/<int:user_id>', methods=['PATCH'])
    @token_required
    @admin_required
    def update_user(user_id):
        """Обновить пользователя"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminUserUpdateSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return jsonify(format_response(None, 404, 'User not found')), 404
                
                old_values = {}
                new_values = {}
                
                if 'email' in validated_data:
                    email = validated_data['email'].lower()
                    existing = session.query(User).filter_by(email=email).filter(User.id != user_id).first()
                    if existing:
                        return jsonify(format_response(None, 400, 'Email already exists')), 400
                    old_values['email'] = user.email
                    user.email = email
                    new_values['email'] = email
                
                if 'name' in validated_data:
                    old_values['name'] = user.name
                    user.name = sanitize_string(validated_data['name'])
                    new_values['name'] = user.name
                
                if 'surname' in validated_data:
                    old_values['surname'] = user.surname
                    user.surname = sanitize_string(validated_data['surname'])
                    new_values['surname'] = user.surname
                
                if 'role' in validated_data:
                    old_values['role'] = user.role
                    user.role = validated_data['role']
                    new_values['role'] = user.role
                
                if 'is_active' in validated_data:
                    old_values['is_active'] = user.is_active
                    user.is_active = validated_data['is_active']
                    new_values['is_active'] = user.is_active
                
                if 'banned_until' in validated_data:
                    old_values['banned_until'] = str(user.banned_until) if user.banned_until else None
                    user.banned_until = validated_data['banned_until']
                    new_values['banned_until'] = str(user.banned_until) if user.banned_until else None
                
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='update',
                    entity_type='user',
                    entity_id=user_id,
                    old_value=json.dumps(old_values),
                    new_value=json.dumps(new_values)
                )
                
                return jsonify(format_response({'message': 'User updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/users/<int:user_id>/status', methods=['PATCH'])
    @token_required
    @admin_required
    def update_user_status(user_id):
        """Обновить статус пользователя"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminUserStatusSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return jsonify(format_response(None, 404, 'User not found')), 404
                
                old_values = {'is_active': user.is_active, 'banned_until': str(user.banned_until) if user.banned_until else None}
                user.is_active = validated_data['is_active']
                user.banned_until = validated_data.get('banned_until')
                new_values = {'is_active': user.is_active, 'banned_until': str(user.banned_until) if user.banned_until else None}
                
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='status_change',
                    entity_type='user',
                    entity_id=user_id,
                    old_value=json.dumps(old_values),
                    new_value=json.dumps(new_values)
                )
                
                return jsonify(format_response({'message': 'User status updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/users/<int:user_id>/role', methods=['PATCH'])
    @token_required
    @admin_required
    def update_user_role(user_id):
        """Обновить роль пользователя"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminUserRoleSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return jsonify(format_response(None, 404, 'User not found')), 404
                
                old_role = user.role
                user.role = validated_data['role']
                
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='role_change',
                    entity_type='user',
                    entity_id=user_id,
                    old_value=json.dumps({'role': old_role}),
                    new_value=json.dumps({'role': user.role})
                )
                
                return jsonify(format_response({'message': 'User role updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/users/<int:user_id>', methods=['DELETE'])
    @token_required
    @admin_required
    def delete_user(user_id):
        """Удалить пользователя"""
        try:
            with get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return jsonify(format_response(None, 404, 'User not found')), 404
                
                user_email = user.email
                session.delete(user)
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='delete',
                    entity_type='user',
                    entity_id=user_id,
                    old_value=json.dumps({'email': user_email})
                )
                
                return jsonify(format_response({'message': 'User deleted successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
    @token_required
    @admin_required
    def reset_user_password(user_id):
        """Сбросить пароль пользователя (админ)"""
        try:
            with get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return jsonify(format_response(None, 404, 'User not found')), 404
                
                import secrets
                new_password = secrets.token_urlsafe(12)
                user.password = generate_password_hash(new_password)
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='password_reset',
                    entity_type='user',
                    entity_id=user_id
                )
                
                return jsonify(format_response({
                    'message': 'Password reset successfully',
                    'dev_password': new_password 
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/audit/users', methods=['GET'])
    @token_required
    @admin_required
    def get_user_audit():
        """Получить журнал аудита пользователей"""
        try:
            user_id = request.args.get('userId', type=int)
            admin_id = request.args.get('adminId', type=int)
            action = request.args.get('action', '')
            from_date = parse_date_param(request.args.get('from'))
            to_date = parse_date_param(request.args.get('to'))
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                query = session.query(AuditLog).filter(AuditLog.entity_type == 'user')
                
                if user_id:
                    query = query.filter(AuditLog.user_id == user_id)
                if admin_id:
                    query = query.filter(AuditLog.admin_id == admin_id)
                if action:
                    query = query.filter(AuditLog.action == action)
                if from_date:
                    query = query.filter(AuditLog.created_at >= from_date)
                if to_date:
                    to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                    query = query.filter(AuditLog.created_at <= to_date_end)
                
                result = paginate_query(query.order_by(AuditLog.created_at.desc()), page, limit)
                
                audit_data = []
                for log in result['items']:
                    audit_data.append({
                        'id': log.id,
                        'adminId': log.admin_id,
                        'userId': log.user_id,
                        'action': log.action,
                        'entityType': log.entity_type,
                        'entityId': log.entity_id,
                        'oldValue': log.old_value,
                        'newValue': log.new_value,
                        'ipAddress': log.ip_address,
                        'createdAt': log.created_at.isoformat() if log.created_at else None
                    })
                
                return jsonify(format_response({
                    'logs': audit_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

