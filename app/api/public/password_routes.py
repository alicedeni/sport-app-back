from flask import jsonify, request
from datetime import datetime, timedelta
import secrets
import logging
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import User, PasswordReset
from werkzeug.security import generate_password_hash, check_password_hash
from app.api.public.auth_routes import token_required

logger = logging.getLogger(__name__)

RESET_TOKEN_TTL_HOURS = 2


def init_password_routes(app):
    @app.route('/password/request-reset', methods=['POST'])
    def request_password_reset():
        data = request.get_json() or {}
        login_or_email = data.get('email') 
        if not login_or_email:
            return jsonify({'status': 400, 'message': 'email is required'}), 400

        candidate = login_or_email.strip().lower()

        try:
            with get_session() as session:
                user = session.query(User).filter_by(email=candidate).first()
                if not user:
                    return jsonify({'status': 200, 'message': 'If account exists, reset instructions were sent'}), 200

                user_id = user.id
                token = secrets.token_urlsafe(32)
                expires_at = datetime.utcnow() + timedelta(hours=RESET_TOKEN_TTL_HOURS)

                session.query(PasswordReset).filter(
                    PasswordReset.user_id == user_id,
                    PasswordReset.used == False
                ).update({'used': True})

                new_reset = PasswordReset(
                    user_id=user_id,
                    token=token,
                    expires_at=expires_at
                )
                session.add(new_reset)
                session.commit()

                logger.info(f"Password reset token generated for user_id={user_id}")
                return jsonify({
                    'status': 200,
                    'message': 'If account exists, reset instructions were sent',
                    'dev_token': token  
                }), 200
        except Exception as e:
            logger.error(f"Error in password reset request: {e}")
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/password/reset', methods=['POST'])
    def reset_password():
        data = request.get_json() or {}
        token = data.get('token')
        new_password = data.get('password')

        if not token or not new_password:
            return jsonify({'status': 400, 'message': 'token and password are required'}), 400

        try:
            with get_session() as session:
                reset_row = session.query(PasswordReset).filter_by(token=token).first()
                if not reset_row:
                    return jsonify({'status': 400, 'message': 'Invalid or expired token'}), 400

                if reset_row.used or reset_row.expires_at < datetime.utcnow():
                    return jsonify({'status': 400, 'message': 'Invalid or expired token'}), 400

                user = session.query(User).filter_by(id=reset_row.user_id).first()
                if not user:
                    return jsonify({'status': 404, 'message': 'User not found'}), 404

                user.password = generate_password_hash(new_password)
                reset_row.used = True
                session.commit()

                return jsonify({'status': 200, 'message': 'Password has been reset successfully'}), 200
        except Exception as e:
            logger.error(f"Error in password reset: {e}")
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/password/change', methods=['POST'])
    @token_required
    def change_password():
        data = request.get_json() or {}
        old_password = data.get('oldPassword')
        new_password = data.get('newPassword')
        confirm_password = data.get('confirmPassword')

        if not old_password or not new_password or not confirm_password:
            return jsonify({'status': 400, 'message': 'oldPassword, newPassword and confirmPassword are required'}), 400
        if new_password != confirm_password:
            return jsonify({'status': 400, 'message': 'Passwords do not match'}), 400
        if len(new_password) < 4:
            return jsonify({'status': 400, 'message': 'Password must be at least 4 characters'}), 400
        if new_password == old_password:
            return jsonify({'status': 400, 'message': 'New password must differ from old password'}), 400

        try:
            user_id = request.user_id
            with get_session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return jsonify({'status': 404, 'message': 'User not found'}), 404
                if not check_password_hash(user.password, old_password):
                    return jsonify({'status': 400, 'message': 'Old password is incorrect'}), 400
                user.password = generate_password_hash(new_password)
                session.commit()
            return jsonify({'status': 200, 'message': 'Password changed successfully'}), 200
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500
