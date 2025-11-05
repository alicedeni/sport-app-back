import jwt
from flask import Flask, jsonify, request, make_response
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import User
from config import config
import os
import random
import logging
from app.domain.schemas import UserRegistrationSchema, UserLoginSchema, UserUpdateSchema, validate_json_data, sanitize_string

logger = logging.getLogger(__name__)

env = os.environ.get('FLASK_ENV', 'development')
app_config = config.get(env, config['default'])

def generate_token(user_id):
    """Генерация JWT токена (legacy, для совместимости)"""
    try:
        expiration = datetime.utcnow() + timedelta(hours=app_config.JWT_EXPIRATION_HOURS)
        payload = {'user_id': user_id, 'exp': expiration}
        return jwt.encode(payload, app_config.SECRET_KEY, algorithm=app_config.JWT_ALGORITHM)
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        raise

def generate_access_token(user_id):
    """Генерация короткого access токена для cookie"""
    try:
        expiration = datetime.utcnow() + timedelta(minutes=app_config.JWT_ACCESS_TOKEN_EXPIRES)
        payload = {
            'user_id': user_id,
            'exp': expiration,
            'type': 'access'
        }
        return jwt.encode(payload, app_config.SECRET_KEY, algorithm=app_config.JWT_ALGORITHM)
    except Exception as e:
        logger.error(f"Error generating access token: {e}")
        raise

def generate_refresh_token(user_id):
    """Генерация длинного refresh токена для cookie"""
    try:
        expiration = datetime.utcnow() + timedelta(days=app_config.JWT_REFRESH_TOKEN_EXPIRES)
        payload = {
            'user_id': user_id,
            'exp': expiration,
            'type': 'refresh'
        }
        return jwt.encode(payload, app_config.SECRET_KEY, algorithm=app_config.JWT_ALGORITHM)
    except Exception as e:
        logger.error(f"Error generating refresh token: {e}")
        raise

def set_auth_cookies(response, access_token, refresh_token):
    """Установка httpOnly cookies для токенов"""
    response.set_cookie(
        app_config.JWT_ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=app_config.JWT_ACCESS_TOKEN_EXPIRES * 60,
        secure=app_config.JWT_COOKIE_SECURE,
        httponly=app_config.JWT_COOKIE_HTTPONLY,
        samesite=app_config.JWT_COOKIE_SAMESITE
    )

    response.set_cookie(
        app_config.JWT_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=app_config.JWT_REFRESH_TOKEN_EXPIRES * 24 * 60 * 60,
        secure=app_config.JWT_COOKIE_SECURE,
        httponly=app_config.JWT_COOKIE_HTTPONLY,
        samesite=app_config.JWT_COOKIE_SAMESITE
    )
    
    return response

def clear_auth_cookies(response):
    """Очистка auth cookies при logout"""
    response.set_cookie(
        app_config.JWT_ACCESS_COOKIE_NAME,
        value='',
        max_age=0,
        secure=app_config.JWT_COOKIE_SECURE,
        httponly=app_config.JWT_COOKIE_HTTPONLY,
        samesite=app_config.JWT_COOKIE_SAMESITE
    )
    
    response.set_cookie(
        app_config.JWT_REFRESH_COOKIE_NAME,
        value='',
        max_age=0,
        secure=app_config.JWT_COOKIE_SECURE,
        httponly=app_config.JWT_COOKIE_HTTPONLY,
        samesite=app_config.JWT_COOKIE_SAMESITE
    )
    
    return response

def decode_token(token):
    """Декодирование JWT токена"""
    if not app_config.SECRET_KEY:
        raise ValueError("SECRET_KEY is missing!")

    try:
        decoded = jwt.decode(token, app_config.SECRET_KEY, algorithms=[app_config.JWT_ALGORITHM])
        return decoded['user_id']
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return "expired"
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return None

def token_required(f):
    """
    Dual-mode декоратор авторизации:
    1. Приоритет: httpOnly cookie (access_token)
    2. Fallback: Authorization header (Bearer token)
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        token = request.cookies.get(app_config.JWT_ACCESS_COOKIE_NAME)
        if token:
            logger.debug("Auth via cookie")
        else:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split("Bearer ")[1]
                logger.debug("Auth via Bearer token")

        if not token:
            return jsonify({'status': 401, 'message': 'Token is required'}), 401

        user_id = decode_token(token)
        if user_id == "expired":
            return jsonify({'status': 401, 'message': 'Token expired'}), 401
        if user_id is None:
            return jsonify({'status': 401, 'message': 'Invalid token'}), 401

        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated

def init_auth_routes(app):
    @app.route('/login', methods=['POST'])
    def login():
        """
        Вход пользователя в систему (dual-mode)
        - Устанавливает httpOnly cookies (access + refresh)
        - Возвращает токен в JSON (для fallback/совместимости)
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 400, 'message': 'No data provided'}), 400

            if isinstance(data, dict) and 'email' in data and isinstance(data['email'], str):
                data['email'] = data['email'].strip().lower()

            validated_data, errors = validate_json_data(UserLoginSchema, data)
            if errors:
                return jsonify({'status': 400, 'message': 'Validation error', 'errors': errors}), 400
            
            email = sanitize_string(validated_data['email']).lower()
            password = validated_data['password']

            with get_session() as session:
                db_user = session.query(User.id, User.password).filter(User.email == email).first()

            if not db_user:
                logger.warning(f"Login attempt with non-existent email: {email}")
                return jsonify({'status': 400, 'message': 'Введен неверный логин или пароль.'}), 200

            if not check_password_hash(db_user[1], password):
                logger.warning(f"Invalid password attempt for user: {db_user[0]}")
                return jsonify({'status': 400, 'message': 'Введен неверный логин или пароль.'}), 200

            user_id = db_user[0]
            
            access_token = generate_access_token(user_id)
            refresh_token = generate_refresh_token(user_id)
            legacy_token = generate_token(user_id)
            
            logger.info(f"User {user_id} logged in successfully")
            
            response_data = {
                'status': 200,
                'message': 'Login successful',
                'token': legacy_token
            }
            response = make_response(jsonify(response_data), 200)
            
            response = set_auth_cookies(response, access_token, refresh_token)
            
            return response

        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/auth/refresh', methods=['POST'])
    def refresh():
        """
        Обновление access токена через refresh токен из cookie
        - Читает refresh_token из httpOnly cookie
        - Генерирует новую пару токенов
        - Устанавливает новые cookies (ротация refresh токена)
        """
        try:
            refresh_token = request.cookies.get(app_config.JWT_REFRESH_COOKIE_NAME)
            
            if not refresh_token:
                return jsonify({'status': 401, 'message': 'Refresh token is missing'}), 401
            
            user_id = decode_token(refresh_token)
            
            if user_id == "expired":
                response = make_response(jsonify({'status': 401, 'message': 'Refresh token expired'}), 401)
                response = clear_auth_cookies(response)
                return response
            
            if user_id is None:
                response = make_response(jsonify({'status': 401, 'message': 'Invalid refresh token'}), 401)
                response = clear_auth_cookies(response)
                return response
            
            with get_session() as session:
                user_exists = session.query(User.id).filter(User.id == user_id).first()
            
            if not user_exists:
                response = make_response(jsonify({'status': 404, 'message': 'User not found'}), 404)
                response = clear_auth_cookies(response)
                return response
            
            new_access_token = generate_access_token(user_id)
            new_refresh_token = generate_refresh_token(user_id)
            new_legacy_token = generate_token(user_id)
            
            logger.info(f"Tokens refreshed for user {user_id}")
            
            response_data = {
                'status': 200,
                'message': 'Tokens refreshed successfully',
                'token': new_legacy_token
            }
            response = make_response(jsonify(response_data), 200)
            
            response = set_auth_cookies(response, new_access_token, new_refresh_token)
            
            return response
            
        except Exception as e:
            logger.error(f"Refresh error: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/auth/logout', methods=['POST'])
    def auth_logout():
        """
        Выход из системы (cookie-based)
        - Очищает httpOnly cookies
        - Опционально: добавить refresh token в blacklist (будущая feature)
        """
        try:
            access_token = request.cookies.get(app_config.JWT_ACCESS_COOKIE_NAME)
            if access_token:
                user_id = decode_token(access_token)
                if user_id and user_id != "expired":
                    logger.info(f"User {user_id} logged out")
            
            response_data = {
                'status': 200,
                'message': 'Logged out successfully'
            }
            response = make_response(jsonify(response_data), 200)
            response = clear_auth_cookies(response)
            
            return response
            
        except Exception as e:
            logger.error(f"Logout error: {e}", exc_info=True)
            response = make_response(jsonify({'status': 500, 'message': 'Internal server error'}), 500)
            response = clear_auth_cookies(response)
            return response

    @app.route('/user', methods=['GET'])
    @token_required
    def get_user_data():
        user_id = request.user_id
        try:
            with get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()

                if user:
                    user_data = {
                        'id': user.id,
                        'surname': user.surname,
                        'name': user.name,
                        'midname': user.midname,
                        'email': user.email,
                        'age': user.age,
                        'gender': user.gender,
                        'height': user.height,
                        'weight': user.weight,
                        'points': user.points,
                        'team_id': user.team_id,
                        'f_hello': bool(user.f_hello) if user.f_hello is not None else False,
                        'show_welcome': bool(user.show_welcome) if user.show_welcome is not None else True
                    }
                    return jsonify({'status': 200, 'user_data': user_data})
                return jsonify({'status': 404, 'message': 'User not found'}), 404
        except Exception as e:
            logger.error(f"Error fetching user data: {e}")
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/register', methods=['POST'])
    def register():
        """Регистрация нового пользователя"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 400, 'message': 'No data provided'}), 400

            if isinstance(data, dict) and 'email' in data and isinstance(data['email'], str):
                data['email'] = data['email'].strip().lower()

            validated_data, errors = validate_json_data(UserRegistrationSchema, data)
            if errors:
                logger.warning(f"Validation errors: {errors}")
                return jsonify({'status': 400, 'message': 'Validation error', 'errors': errors}), 400

            surname = sanitize_string(validated_data['surname'])
            name = sanitize_string(validated_data['name'])
            midname = sanitize_string(validated_data.get('patronymic', ''))
            email = sanitize_string(validated_data['email']).lower()
            password = validated_data['password']

            with get_session() as session:
                exists = session.query(User.id).filter(User.email == email).first()
            if exists:
                logger.warning(f"Registration attempt with existing email: {email}")
                return jsonify({'status': 400, 'message': 'Email already exists'}), 400

            password_hash = generate_password_hash(password)
            
            with get_session() as session:
                new_user = User(
                    surname=surname,
                    name=name,
                    midname=midname,
                    email=email,
                    password=password_hash,
                    team_id=random.randint(1, 3)
                )
                session.add(new_user)
                session.commit()

            logger.info(f"User registered successfully: {email}")
            return jsonify({'status': 200, 'message': 'User registered successfully'}), 200

        except Exception as e:
            logger.error(f"Registration error: {e}")
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/user/get_hello_status', methods=['GET'])
    @token_required
    def get_hello_status():
        user_id = request.user_id
        try:
            with get_session() as session:
                result = session.query(User.f_hello).filter(User.id == user_id).first()
                
                if result is not None:
                    f_hello_value = result[0]
                    final_value = bool(f_hello_value) if f_hello_value is not None else False
                    return jsonify({'status': 200, 'f_hello': final_value})
                
                user_exists = session.query(User.id).filter(User.id == user_id).first()
                if user_exists:
                    return jsonify({'status': 200, 'f_hello': False})
                
                return jsonify({'status': 404, 'message': 'User not found'}), 404
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"Error fetching hello status: {e}\n{error_detail}")
            try:
                with get_session() as session:
                    user_exists = session.query(User.id).filter(User.id == user_id).first()
                    if user_exists:
                        return jsonify({'status': 200, 'f_hello': False})
            except:
                pass
            return jsonify({'status': 500, 'message': f'Internal server error: {str(e)}'}), 500

    @app.route('/user/update_f_hello', methods=['POST'])
    @token_required
    def update_f_hello():
        user_id = request.user_id
        try:
            with get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return jsonify({'status': 404, 'message': 'User not found'}), 404
                user.f_hello = True
                session.commit()
                return jsonify({'status': 200, 'message': 'f_hello updated successfully'})
        except Exception as e:
            logger.error(f"Error updating f_hello: {e}")
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

