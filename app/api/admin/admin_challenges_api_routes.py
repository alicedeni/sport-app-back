from flask import jsonify, request
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import ChallengeNew, ChallengeParticipantNew, User
from app.api.public.auth_routes import token_required
from app.api.admin.admin_middleware import admin_required, log_audit
from app.domain.schemas import validate_json_data
from sqlalchemy import and_, func
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class FlexibleDateTime(fields.Field):
    def _deserialize(self, value, attr, data, **kwargs):
        if not value:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if not isinstance(value, str):
            raise ValidationError("Invalid datetime format")
        
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'
        
        formats = [
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.replace(tzinfo=None)
            except ValueError:
                continue
        
        raise ValidationError(f"Invalid datetime format: {value}")


class ChallengeCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    type = fields.Str(required=True, validate=validate.OneOf(['individual', 'team']), data_key='challenge_type')
    league = fields.Str(allow_none=True, validate=validate.OneOf(['bronze', 'silver', 'gold']))
    metric_type = fields.Str(required=True, validate=validate.OneOf(['distance', 'calories', 'points']))
    target_value = fields.Float(required=True, validate=validate.Range(min=0.1))
    verification_mode = fields.Str(missing='auto', validate=validate.OneOf(['auto']))
    activity_types = fields.List(fields.Str(), allow_none=True)
    reward_points = fields.Int(missing=0, validate=validate.Range(min=0))
    reward_badge = fields.Str(allow_none=True)
    start_at = FlexibleDateTime(required=True)
    end_at = FlexibleDateTime(required=True)
    status = fields.Str(missing='draft', validate=validate.OneOf(['draft', 'active', 'completed', 'archived']))
    cover_image = fields.Str(allow_none=True)


class ChallengeUpdateSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    type = fields.Str(validate=validate.OneOf(['individual', 'team']), data_key='challenge_type')
    league = fields.Str(allow_none=True, validate=validate.OneOf(['bronze', 'silver', 'gold']))
    metric_type = fields.Str(validate=validate.OneOf(['distance', 'calories', 'points']))
    target_value = fields.Float(validate=validate.Range(min=0.1))
    verification_mode = fields.Str(validate=validate.OneOf(['auto']))
    activity_types = fields.List(fields.Str(), allow_none=True)
    reward_points = fields.Int(validate=validate.Range(min=0))
    reward_badge = fields.Str(allow_none=True)
    start_at = FlexibleDateTime(allow_none=True)
    end_at = FlexibleDateTime(allow_none=True)
    status = fields.Str(validate=validate.OneOf(['draft', 'active', 'completed', 'archived']))
    cover_image = fields.Str(allow_none=True)


def init_admin_challenges_api_routes(app):
    @app.route('/admin/challenges', methods=['POST'])
    @token_required
    @admin_required
    def create_challenge():
        """Создать челлендж"""
        try:
            admin_id = request.user_id
            data = request.get_json()
            
            if not data:
                return jsonify({'status': 400, 'message': 'No data provided'}), 400
            
            validated_data, errors = validate_json_data(ChallengeCreateSchema, data)
            if errors:
                return jsonify({'status': 400, 'message': errors}), 400
            
            if 'type' in validated_data:
                validated_data['challenge_type'] = validated_data.pop('type')
            
            if 'activity_types' in validated_data and validated_data['activity_types'] == []:
                validated_data['activity_types'] = None
            
            with get_session() as session:
                challenge = ChallengeNew(
                    name=validated_data['name'],
                    description=validated_data.get('description'),
                    challenge_type=validated_data.get('challenge_type'),
                    league=validated_data.get('league'),
                    metric_type=validated_data['metric_type'],
                    target_value=validated_data['target_value'],
                    verification_mode=validated_data.get('verification_mode', 'auto'),
                    activity_types=validated_data.get('activity_types'),
                    reward_points=validated_data.get('reward_points', 0),
                    reward_badge=validated_data.get('reward_badge'),
                    start_at=validated_data['start_at'],
                    end_at=validated_data['end_at'],
                    status=validated_data.get('status', 'draft'),
                    cover_image=validated_data.get('cover_image'),
                    created_by=admin_id,
                    created_at=datetime.utcnow()
                )
                
                session.add(challenge)
                session.flush()
                
                challenge_id = challenge.id
                session.commit()
                
                log_audit(
                    admin_id=admin_id,
                    action='create',
                    entity_type='challenge',
                    entity_id=challenge_id,
                    new_value=json.dumps(validated_data, default=str)
                )
                
                logger.info(f"Challenge {challenge_id} created by admin {admin_id}")
                
                return jsonify({
                    'status': 200,
                    'message': 'Challenge created successfully',
                    'challenge_id': challenge_id
                }), 201
        
        except Exception as e:
            logger.error(f"Error creating challenge: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
    
    
    @app.route('/admin/challenges/<int:challenge_id>', methods=['PATCH'])
    @token_required
    @admin_required
    def update_challenge(challenge_id):
        """Обновить челлендж"""
        try:
            admin_id = request.user_id
            data = request.get_json()
            
            if not data:
                return jsonify({'status': 400, 'message': 'No data provided'}), 400
            
            validated_data, errors = validate_json_data(ChallengeUpdateSchema, data)
            if errors:
                return jsonify({'status': 400, 'message': 'Validation error', 'errors': errors}), 400
            
            if 'type' in validated_data:
                validated_data['challenge_type'] = validated_data.pop('type')
            
            if 'activity_types' in validated_data and validated_data['activity_types'] == []:
                validated_data['activity_types'] = None
            
            with get_session() as session:
                challenge = session.query(ChallengeNew).filter(
                    ChallengeNew.id == challenge_id
                ).first()
                
                if not challenge:
                    return jsonify({'status': 404, 'message': 'Challenge not found'}), 404
                
                for key, value in validated_data.items():
                    setattr(challenge, key, value)
                
                challenge.updated_at = datetime.utcnow()
                
                session.commit()
                
                log_audit(
                    admin_id=admin_id,
                    action='update',
                    entity_type='challenge',
                    entity_id=challenge_id,
                    new_value=json.dumps(validated_data, default=str)
                )
                
                logger.info(f"Challenge {challenge_id} updated by admin {admin_id}")
                
                return jsonify({
                    'status': 200,
                    'message': 'Challenge updated successfully'
                }), 200
        
        except Exception as e:
            logger.error(f"Error updating challenge {challenge_id}: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
    
    
    @app.route('/admin/challenges', methods=['GET'])
    @token_required
    @admin_required
    def get_all_challenges():
        """Получить все челленджи для админа"""
        try:
            status = request.args.get('status')
            challenge_type = request.args.get('type')
            page = int(request.args.get('page', 1))
            limit = min(int(request.args.get('limit', 20)), 100)
            
            with get_session() as session:
                query = session.query(ChallengeNew)
                
                if status:
                    query = query.filter(ChallengeNew.status == status)
                if challenge_type:
                    query = query.filter(ChallengeNew.challenge_type == challenge_type)
                
                total = query.count()
                offset = (page - 1) * limit
                challenges = query.order_by(
                    ChallengeNew.created_at.desc()
                ).limit(limit).offset(offset).all()
                
                challenges_data = []
                for challenge in challenges:
                    participants_count = session.query(
                        func.count(ChallengeParticipantNew.id)
                    ).filter(
                        ChallengeParticipantNew.challenge_id == challenge.id
                    ).scalar() or 0
                    
                    completed_count = session.query(
                        func.count(ChallengeParticipantNew.id)
                    ).filter(
                        and_(
                            ChallengeParticipantNew.challenge_id == challenge.id,
                            ChallengeParticipantNew.completed == True
                        )
                    ).scalar() or 0
                    
                    challenges_data.append({
                        'id': challenge.id,
                        'name': challenge.name,
                        'description': challenge.description,
                        'type': challenge.challenge_type,
                        'league': challenge.league,
                        'metric_type': challenge.metric_type,
                        'target_value': challenge.target_value,
                        'verification_mode': challenge.verification_mode,
                        'activity_types': challenge.activity_types,
                        'reward_points': challenge.reward_points,
                        'reward_badge': challenge.reward_badge,
                        'start_at': challenge.start_at.strftime('%Y-%m-%dT%H:%M') if challenge.start_at else None,
                        'end_at': challenge.end_at.strftime('%Y-%m-%dT%H:%M') if challenge.end_at else None,
                        'status': challenge.status,
                        'cover_image': challenge.cover_image,
                        'created_at': challenge.created_at.strftime('%Y-%m-%dT%H:%M:%S') if challenge.created_at else None,
                        'stats': {
                            'participants': participants_count,
                            'completed': completed_count
                        }
                    })
                
                pages = (total + limit - 1) // limit
                
                return jsonify({
                    'status': 200,
                    'challenges': challenges_data,
                    'pagination': {
                        'total': total,
                        'page': page,
                        'limit': limit,
                        'pages': pages
                    }
                }), 200
        
        except Exception as e:
            logger.error(f"Error getting all challenges: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
    
    
    @app.route('/admin/challenges/<int:challenge_id>/participants', methods=['GET'])
    @token_required
    @admin_required
    def get_challenge_participants(challenge_id):
        """Получить список участников челленджа"""
        try:
            page = int(request.args.get('page', 1))
            limit = min(int(request.args.get('limit', 50)), 200)
            
            with get_session() as session:
                challenge = session.query(ChallengeNew).filter(
                    ChallengeNew.id == challenge_id
                ).first()
                
                if not challenge:
                    return jsonify({'status': 404, 'message': 'Challenge not found'}), 404
                
                total = session.query(
                    func.count(ChallengeParticipantNew.id)
                ).filter(
                    ChallengeParticipantNew.challenge_id == challenge_id
                ).scalar() or 0
                
                rank_subquery = session.query(
                    ChallengeParticipantNew.id,
                    func.rank().over(
                        order_by=[
                            ChallengeParticipantNew.current_value.desc(),
                            ChallengeParticipantNew.completed_at.asc().nulls_last()
                        ]
                    ).label('rank')
                ).filter(
                    ChallengeParticipantNew.challenge_id == challenge_id
                ).subquery()
                
                offset = (page - 1) * limit
                participants = session.query(
                    ChallengeParticipantNew,
                    User,
                    rank_subquery.c.rank
                ).join(
                    User,
                    User.id == ChallengeParticipantNew.user_id
                ).join(
                    rank_subquery,
                    rank_subquery.c.id == ChallengeParticipantNew.id
                ).filter(
                    ChallengeParticipantNew.challenge_id == challenge_id
                ).order_by(
                    rank_subquery.c.rank
                ).limit(limit).offset(offset).all()
                
                participants_data = []
                target_value = challenge.target_value
                
                for participant, user, rank in participants:
                    percentage = (participant.current_value / target_value * 100) if target_value > 0 else 0
                    participants_data.append({
                        'id': participant.id,
                        'user_id': user.id,
                        'name': user.name,
                        'surname': user.surname,
                        'email': user.email,
                        'avatar': user.avatar,
                        'current_value': participant.current_value,
                        'percentage': round(percentage, 1),
                        'completed': participant.completed,
                        'completed_at': participant.completed_at.isoformat() + 'Z' if participant.completed_at else None,
                        'joined_at': participant.joined_at.isoformat() + 'Z' if participant.joined_at else None,
                        'last_activity': participant.last_activity_at.isoformat() + 'Z' if participant.last_activity_at else None,
                        'rank': rank
                    })
                
                pages = (total + limit - 1) // limit
                
                return jsonify({
                    'status': 200,
                    'challenge_name': challenge.name,
                    'target_value': target_value,
                    'participants': participants_data,
                    'pagination': {
                        'total': total,
                        'page': page,
                        'limit': limit,
                        'pages': pages
                    }
                }), 200
        
        except Exception as e:
            logger.error(f"Error getting participants for challenge {challenge_id}: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
