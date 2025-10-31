import jwt
from flask import Flask, jsonify, request
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
    """Генерация JWT токена"""
    try:
        expiration = datetime.utcnow() + timedelta(hours=app_config.JWT_EXPIRATION_HOURS)
        payload = {'user_id': user_id, 'exp': expiration}
        return jwt.encode(payload, app_config.SECRET_KEY, algorithm=app_config.JWT_ALGORITHM)
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        raise

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
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if token and token.startswith("Bearer "):
            token = token.split("Bearer ")[1]

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
        """Вход пользователя в систему"""
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

            token = generate_token(db_user[0])
            logger.info(f"User {db_user[0]} logged in successfully")
            
            return jsonify({'status': 200, 'message': 'Login successful', 'token': token}), 200

        except Exception as e:
            logger.error(f"Login error: {e}")
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

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
                        'team_id': user.team_id
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
                    f_hello_value = result[0] if isinstance(result, tuple) else result
                    return jsonify({'status': 200, 'f_hello': bool(f_hello_value) if f_hello_value is not None else False})
                
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

