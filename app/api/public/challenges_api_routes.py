from flask import jsonify, request
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import ChallengeNew, ChallengeParticipantNew, User
from app.api.public.auth_routes import token_required
from sqlalchemy import and_, or_, func, case
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def init_challenges_api_routes(app):
    @app.route('/challenges', methods=['GET'])
    @token_required
    def get_challenges():
        """Получить список доступных челленджей"""
        try:
            user_id = request.user_id
            
            status = request.args.get('status', 'active')
            challenge_type = request.args.get('type')
            league = request.args.get('league')
            page = int(request.args.get('page', 1))
            limit = min(int(request.args.get('limit', 20)), 100)
            
            with get_session() as session:
                query = session.query(
                    ChallengeNew,
                    ChallengeParticipantNew,
                    func.count(ChallengeParticipantNew.id).over(
                        partition_by=ChallengeNew.id
                    ).label('participants_count')
                ).outerjoin(
                    ChallengeParticipantNew,
                    and_(
                        ChallengeNew.id == ChallengeParticipantNew.challenge_id,
                        ChallengeParticipantNew.user_id == user_id
                    )
                )
                
                now = datetime.utcnow()
                if status == 'active':
                    query = query.filter(
                        and_(
                            ChallengeNew.status == 'active',
                            ChallengeNew.start_at <= now,
                            ChallengeNew.end_at >= now
                        )
                    )
                elif status == 'upcoming':
                    query = query.filter(
                        and_(
                            ChallengeNew.status == 'active',
                            ChallengeNew.start_at > now
                        )
                    )
                elif status == 'completed':
                    query = query.filter(ChallengeNew.status == 'completed')
                elif status != 'all':
                    query = query.filter(ChallengeNew.status == status)
                
                if challenge_type:
                    query = query.filter(ChallengeNew.challenge_type == challenge_type)
                
                if league:
                    query = query.filter(
                        or_(
                            ChallengeNew.league == league,
                            ChallengeNew.league.is_(None)
                        )
                    )
                
                total = query.count()
                
                offset = (page - 1) * limit
                rows = query.order_by(ChallengeNew.start_at.desc()).limit(limit).offset(offset).all()
                
                challenges_data = []
                for challenge, participant, participants_count in rows:
                    real_participants_count = session.query(func.count(ChallengeParticipantNew.id)).filter(
                        ChallengeParticipantNew.challenge_id == challenge.id
                    ).scalar() or 0
                    
                    challenge_dict = {
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
                        'start_at': challenge.start_at.isoformat() if challenge.start_at else None,
                        'end_at': challenge.end_at.isoformat() if challenge.end_at else None,
                        'status': challenge.status,
                        'cover_image': challenge.cover_image,
                        'participants_count': real_participants_count
                    }
                    
                    if participant and participant.id:
                        percentage = (participant.current_value / challenge.target_value * 100) if challenge.target_value > 0 else 0
                        challenge_dict['my_progress'] = {
                            'joined': True,
                            'current_value': participant.current_value,
                            'percentage': round(percentage, 1),
                            'completed': participant.completed,
                            'last_activity': participant.last_activity_at.isoformat() if participant.last_activity_at else None
                        }
                    else:
                        challenge_dict['my_progress'] = {'joined': False}
                    
                    challenges_data.append(challenge_dict)
                
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
            logger.error(f"Error getting challenges: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
    
    
    @app.route('/challenges/<int:challenge_id>', methods=['GET'])
    @token_required
    def get_challenge(challenge_id):
        """Получить детали челленджа"""
        try:
            user_id = request.user_id
            
            with get_session() as session:
                query = session.query(
                    ChallengeNew,
                    ChallengeParticipantNew
                ).outerjoin(
                    ChallengeParticipantNew,
                    and_(
                        ChallengeNew.id == ChallengeParticipantNew.challenge_id,
                        ChallengeParticipantNew.user_id == user_id
                    )
                ).filter(ChallengeNew.id == challenge_id)
                
                result = query.first()
                
                if not result:
                    return jsonify({'status': 404, 'message': 'Challenge not found'}), 404
                
                challenge, participant = result
                
                participants_count = session.query(func.count(ChallengeParticipantNew.id)).filter(
                    ChallengeParticipantNew.challenge_id == challenge.id
                ).scalar() or 0
                
                challenge_dict = {
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
                    'start_at': challenge.start_at.isoformat() if challenge.start_at else None,
                    'end_at': challenge.end_at.isoformat() if challenge.end_at else None,
                    'status': challenge.status,
                    'cover_image': challenge.cover_image,
                    'participants_count': participants_count
                }
                
                if participant and participant.id:
                    rank = session.query(
                        func.count(ChallengeParticipantNew.id)
                    ).filter(
                        and_(
                            ChallengeParticipantNew.challenge_id == challenge_id,
                            ChallengeParticipantNew.current_value > participant.current_value
                        )
                    ).scalar() + 1
                    
                    percentage = (participant.current_value / challenge.target_value * 100) if challenge.target_value > 0 else 0
                    challenge_dict['my_progress'] = {
                        'joined': True,
                        'current_value': participant.current_value,
                        'percentage': round(percentage, 1),
                        'completed': participant.completed,
                        'rank': rank,
                        'joined_at': participant.joined_at.isoformat() if participant.joined_at else None,
                        'last_activity': participant.last_activity_at.isoformat() if participant.last_activity_at else None
                    }
                else:
                    challenge_dict['my_progress'] = {'joined': False}
                
                return jsonify({'status': 200, 'challenge': challenge_dict}), 200
        
        except Exception as e:
            logger.error(f"Error getting challenge {challenge_id}: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
    
    
    @app.route('/challenges/<int:challenge_id>/join', methods=['POST'])
    @token_required
    def join_challenge(challenge_id):
        """Присоединиться к челленджу"""
        try:
            user_id = request.user_id
            
            with get_session() as session:
                challenge = session.query(ChallengeNew).filter(
                    ChallengeNew.id == challenge_id
                ).first()
                
                if not challenge:
                    return jsonify({'status': 404, 'message': 'Challenge not found'}), 404
                
                now = datetime.utcnow()
                if challenge.status != 'active' or challenge.start_at > now or challenge.end_at < now:
                    return jsonify({'status': 400, 'message': 'Challenge is not available for joining'}), 400
                
                existing = session.query(ChallengeParticipantNew).filter(
                    and_(
                        ChallengeParticipantNew.challenge_id == challenge_id,
                        ChallengeParticipantNew.user_id == user_id
                    )
                ).first()
                
                if existing:
                    return jsonify({'status': 400, 'message': 'Already joined this challenge'}), 400
                
                participant = ChallengeParticipantNew(
                    challenge_id=challenge_id,
                    user_id=user_id,
                    current_value=0,
                    completed=False,
                    joined_at=datetime.utcnow()
                )
                session.add(participant)
                session.commit()
                
                logger.info(f"User {user_id} joined challenge {challenge_id}")
                
                return jsonify({
                    'status': 200,
                    'message': 'Successfully joined challenge',
                    'participant_id': participant.id
                }), 200
        
        except Exception as e:
            logger.error(f"Error joining challenge {challenge_id}: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
    
    
    @app.route('/challenges/<int:challenge_id>/leave', methods=['POST'])
    @token_required
    def leave_challenge(challenge_id):
        """Выйти из челленджа"""
        try:
            user_id = request.user_id
            
            with get_session() as session:
                participant = session.query(ChallengeParticipantNew).filter(
                    and_(
                        ChallengeParticipantNew.challenge_id == challenge_id,
                        ChallengeParticipantNew.user_id == user_id,
                        ChallengeParticipantNew.completed == False
                    )
                ).first()
                
                if not participant:
                    return jsonify({'status': 404, 'message': 'Not participating or challenge already completed'}), 404
                
                session.delete(participant)
                session.commit()
                
                logger.info(f"User {user_id} left challenge {challenge_id}")
                
                return jsonify({'status': 200, 'message': 'Successfully left challenge'}), 200
        
        except Exception as e:
            logger.error(f"Error leaving challenge {challenge_id}: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
    
    
    @app.route('/challenges/<int:challenge_id>/leaderboard', methods=['GET'])
    @token_required
    def get_leaderboard(challenge_id):
        """Получить лидерборд челленджа"""
        try:
            user_id = request.user_id
            limit = min(int(request.args.get('limit', 100)), 1000)
            
            with get_session() as session:
                challenge = session.query(ChallengeNew).filter(
                    ChallengeNew.id == challenge_id
                ).first()
                
                if not challenge:
                    return jsonify({'status': 404, 'message': 'Challenge not found'}), 404
                
                target_value = challenge.target_value
                rank_subquery = session.query(
                    ChallengeParticipantNew.id,
                    func.rank().over(
                        order_by=[
                            ChallengeParticipantNew.completed.desc(),
                            ChallengeParticipantNew.current_value.desc(),
                            ChallengeParticipantNew.completed_at.asc().nulls_last()
                        ]
                    ).label('rank')
                ).filter(
                    ChallengeParticipantNew.challenge_id == challenge_id
                ).subquery()
                
                leaderboard = session.query(
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
                ).limit(limit).all()
                
                leaderboard_data = []
                for participant, user, rank in leaderboard:
                    percentage = (participant.current_value / target_value * 100) if target_value > 0 else 0
                    leaderboard_data.append({
                        'rank': rank,
                        'user_id': user.id,
                        'username': f"{user.name} {user.surname}",
                        'avatar': user.avatar,
                        'current_value': participant.current_value,
                        'percentage': round(percentage, 1),
                        'completed': participant.completed,
                        'completed_at': participant.completed_at.isoformat() if participant.completed_at else None
                    })
                
                my_position = None
                my_participant = session.query(
                    ChallengeParticipantNew,
                    rank_subquery.c.rank
                ).join(
                    rank_subquery,
                    rank_subquery.c.id == ChallengeParticipantNew.id
                ).filter(
                    and_(
                        ChallengeParticipantNew.challenge_id == challenge_id,
                        ChallengeParticipantNew.user_id == user_id
                    )
                ).first()
                
                if my_participant:
                    participant, rank = my_participant
                    percentage = (participant.current_value / target_value * 100) if target_value > 0 else 0
                    my_position = {
                        'rank': rank,
                        'current_value': participant.current_value,
                        'percentage': round(percentage, 1)
                    }
                
                return jsonify({
                    'status': 200,
                    'leaderboard': leaderboard_data,
                    'my_position': my_position
                }), 200
        
        except Exception as e:
            logger.error(f"Error getting leaderboard for challenge {challenge_id}: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
    
    
    @app.route('/my-challenges', methods=['GET'])
    @token_required
    def get_my_challenges():
        """Получить челленджи пользователя"""
        try:
            user_id = request.user_id
            status_filter = request.args.get('status', 'active')
            
            with get_session() as session:
                query = session.query(
                    ChallengeNew,
                    ChallengeParticipantNew
                ).join(
                    ChallengeParticipantNew,
                    ChallengeNew.id == ChallengeParticipantNew.challenge_id
                ).filter(
                    ChallengeParticipantNew.user_id == user_id
                )
                
                if status_filter == 'active':
                    query = query.filter(ChallengeParticipantNew.completed == False)
                elif status_filter == 'completed':
                    query = query.filter(ChallengeParticipantNew.completed == True)
                
                results = query.order_by(ChallengeNew.end_at.desc()).all()
                
                challenges_data = []
                for challenge, participant in results:
                    percentage = (participant.current_value / challenge.target_value * 100) if challenge.target_value > 0 else 0
                    challenges_data.append({
                        'id': challenge.id,
                        'name': challenge.name,
                        'description': challenge.description,
                        'type': challenge.challenge_type,
                        'metric_type': challenge.metric_type,
                        'target_value': challenge.target_value,
                        'activity_types': challenge.activity_types,
                        'reward_points': challenge.reward_points,
                        'start_at': challenge.start_at.isoformat() if challenge.start_at else None,
                        'end_at': challenge.end_at.isoformat() if challenge.end_at else None,
                        'status': challenge.status,
                        'my_progress': {
                            'current_value': participant.current_value,
                            'percentage': round(percentage, 1),
                            'completed': participant.completed,
                            'completed_at': participant.completed_at.isoformat() if participant.completed_at else None,
                            'joined_at': participant.joined_at.isoformat() if participant.joined_at else None
                        }
                    })
                
                return jsonify({
                    'status': 200,
                    'challenges': challenges_data
                }), 200
        
        except Exception as e:
            logger.error(f"Error getting my challenges: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': str(e)}), 500
