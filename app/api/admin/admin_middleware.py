from functools import wraps
from flask import jsonify, request
import logging
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import User

logger = logging.getLogger(__name__)


def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({'status': 401, 'message': 'Authentication required'}), 401
        
        user = None
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'status': 404, 'message': 'User not found'}), 404
            
            if not user.is_active:
                return jsonify({'status': 403, 'message': 'User is inactive'}), 403
            
            if user.role not in ['admin', 'moderator']:
                return jsonify({'status': 403, 'message': 'Admin access required'}), 403
        
        request.admin_user = user
        return f(*args, **kwargs)
    return decorated


def moderator_required(f):
    """Декоратор для проверки прав модератора"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return jsonify({'status': 401, 'message': 'Authentication required'}), 401
        
        user = None
        with get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'status': 404, 'message': 'User not found'}), 404
            
            if not user.is_active:
                return jsonify({'status': 403, 'message': 'User is inactive'}), 403
            
            if user.role not in ['admin', 'moderator']:
                return jsonify({'status': 403, 'message': 'Moderator access required'}), 403
        
        request.admin_user = user
        return f(*args, **kwargs)
    return decorated


def log_audit(admin_id, action, entity_type, entity_id=None, old_value=None, new_value=None, user_id=None):
    """Создает запись в журнале аудита"""
    try:
        from app.domain.models import AuditLog
        
        with get_session() as session:
            audit = AuditLog(
                admin_id=admin_id,
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                old_value=str(old_value) if old_value else None,
                new_value=str(new_value) if new_value else None,
                ip_address=request.remote_addr if request else None,
                user_agent=request.headers.get('User-Agent') if request else None
            )
            session.add(audit)
            session.commit()
    except Exception as e:
        logger.error(f"Failed to log audit: {e}", exc_info=True)

