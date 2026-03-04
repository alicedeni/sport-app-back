from flask import jsonify, request
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import Challenge, ChallengeParticipant, User, Team
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
                    Challenge,
                    ChallengeParticipant,
                    func.count(ChallengeParticipant.id).over(
                        partition_by=Challenge.id
                    ).label('participants_count')
                ).outerjoin(
                    ChallengeParticipant,
                    and_(
                        Challenge.id == ChallengeParticipant.challenge_id,
                        ChallengeParticipant.user_id == user_id
                    )
                )
                
                now = datetime.utcnow()
                if status == 'active':
                    query = query.filter(
                        and_(
                            Challenge.status == 'active',
                            Challenge.start_at <= now,
                            Challenge.end_at >= now
                        )
                    )
                elif status == 'upcoming':
                    query = query.filter(
                        and_(
                            Challenge.status == 'active',
                            Challenge.start_at > now
                        )
                    )
                elif status == 'completed':
                    query = query.filter(Challenge.status == 'completed')
                elif status != 'all':
                    query = query.filter(Challenge.status == status)
                
                if challenge_type:
                    query = query.filter(Challenge.challenge_type == challenge_type)
                
                if league:
                    query = query.filter(
                        or_(
                            Challenge.league == league,
                            Challenge.league.is_(None)
                        )
                    )
                
                total = query.count()
                
                offset = (page - 1) * limit
                rows = query.order_by(Challenge.start_at.desc()).limit(limit).offset(offset).all()
                
                challenges_data = []
                for challenge, participant, participants_count in rows:
                    real_participants_count = session.query(func.count(ChallengeParticipant.id)).filter(
                        ChallengeParticipant.challenge_id == challenge.id
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
                            'last_activity': participant.last_activity_at.isoformat() if participant.last_activity_at else None,
                            'reward_granted': participant.reward_granted,
                            'reward_granted_at': participant.reward_granted_at.isoformat() if participant.reward_granted_at else None,
                            'reward_points_awarded': participant.reward_points_awarded
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
                    Challenge,
                    ChallengeParticipant
                ).outerjoin(
                    ChallengeParticipant,
                    and_(
                        Challenge.id == ChallengeParticipant.challenge_id,
                        ChallengeParticipant.user_id == user_id
                    )
                ).filter(Challenge.id == challenge_id)
                
                result = query.first()
                
                if not result:
                    return jsonify({'status': 404, 'message': 'Challenge not found'}), 404
                
                challenge, participant = result
                
                participants_count = session.query(func.count(ChallengeParticipant.id)).filter(
                    ChallengeParticipant.challenge_id == challenge.id
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
                        func.count(ChallengeParticipant.id)
                    ).filter(
                        and_(
                            ChallengeParticipant.challenge_id == challenge_id,
                            ChallengeParticipant.current_value > participant.current_value
                        )
                    ).scalar() + 1
                    
                    percentage = (participant.current_value / challenge.target_value * 100) if challenge.target_value > 0 else 0
                    challenge_dict['my_progress'] = {
                        'joined': True,
                        'current_value': participant.current_value,
                        'percentage': round(percentage, 1),
                        'completed': participant.completed,
                        'reward_granted': participant.reward_granted,
                        'reward_granted_at': participant.reward_granted_at.isoformat() if participant.reward_granted_at else None,
                        'reward_points_awarded': participant.reward_points_awarded,
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
                challenge = session.query(Challenge).filter(
                    Challenge.id == challenge_id
                ).first()
                
                if not challenge:
                    return jsonify({'status': 404, 'message': 'Challenge not found'}), 404
                
                now = datetime.utcnow()
                if challenge.status != 'active' or challenge.start_at > now or challenge.end_at < now:
                    return jsonify({'status': 400, 'message': 'Challenge is not available for joining'}), 400
                
                existing = session.query(ChallengeParticipant).filter(
                    and_(
                        ChallengeParticipant.challenge_id == challenge_id,
                        ChallengeParticipant.user_id == user_id
                    )
                ).first()
                
                if existing:
                    return jsonify({'status': 400, 'message': 'Already joined this challenge'}), 400
                
                user = session.query(User.id, User.team_id).filter(User.id == user_id).first()
                if challenge.challenge_type == 'team':
                    if not user or not user.team_id:
                        return jsonify({'status': 400, 'message': 'User must be in a team to join this challenge'}), 400
                    
                    team_participant = session.query(ChallengeParticipant).filter(
                        and_(
                            ChallengeParticipant.challenge_id == challenge_id,
                            ChallengeParticipant.team_id == user.team_id
                        )
                    ).first()
                    
                    if not team_participant:
                        team_participant = ChallengeParticipant(
                            challenge_id=challenge_id,
                            team_id=user.team_id,
                            current_value=0,
                            completed=False,
                            joined_at=datetime.utcnow()
                        )
                        session.add(team_participant)
                        session.flush()
                
                participant = ChallengeParticipant(
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
                participant = session.query(ChallengeParticipant).filter(
                    and_(
                        ChallengeParticipant.challenge_id == challenge_id,
                        ChallengeParticipant.user_id == user_id,
                        ChallengeParticipant.completed == False
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
                challenge = session.query(Challenge).filter(
                    Challenge.id == challenge_id
                ).first()
                
                if not challenge:
                    return jsonify({'status': 404, 'message': 'Challenge not found'}), 404
                
                target_value = challenge.target_value
                rank_subquery = session.query(
                    ChallengeParticipant.id,
                    func.rank().over(
                        order_by=[
                            ChallengeParticipant.completed.desc(),
                            ChallengeParticipant.current_value.desc(),
                            ChallengeParticipant.completed_at.asc().nulls_last()
                        ]
                    ).label('rank')
                ).filter(
                    ChallengeParticipant.challenge_id == challenge_id
                ).subquery()
                
                leaderboard = session.query(
                    ChallengeParticipant,
                    User,
                    rank_subquery.c.rank
                ).join(
                    User,
                    User.id == ChallengeParticipant.user_id
                ).join(
                    rank_subquery,
                    rank_subquery.c.id == ChallengeParticipant.id
                ).filter(
                    ChallengeParticipant.challenge_id == challenge_id
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
                    ChallengeParticipant,
                    rank_subquery.c.rank
                ).join(
                    rank_subquery,
                    rank_subquery.c.id == ChallengeParticipant.id
                ).filter(
                    and_(
                        ChallengeParticipant.challenge_id == challenge_id,
                        ChallengeParticipant.user_id == user_id
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
    
    
    @app.route('/challenges/<int:challenge_id>/team-leaderboard', methods=['GET'])
    @token_required
    def get_team_leaderboard(challenge_id):
        """Получить командный лидерборд челленджа"""
        try:
            limit = min(int(request.args.get('limit', 100)), 1000)
            
            with get_session() as session:
                challenge = session.query(Challenge).filter(
                    Challenge.id == challenge_id
                ).first()
                
                if not challenge:
                    return jsonify({'status': 404, 'message': 'Challenge not found'}), 404
                
                if challenge.challenge_type != 'team':
                    return jsonify({'status': 400, 'message': 'Challenge is not a team challenge'}), 400
                
                participants_stats = session.query(
                    User.team_id.label('team_id'),
                    func.count(ChallengeParticipant.id).label('members_count'),
                    func.avg(ChallengeParticipant.current_value).label('avg_value'),
                    func.max(ChallengeParticipant.current_value).label('best_value'),
                    func.sum(ChallengeParticipant.current_value).label('sum_value')
                ).join(
                    User,
                    User.id == ChallengeParticipant.user_id
                ).filter(
                    ChallengeParticipant.challenge_id == challenge_id,
                    ChallengeParticipant.user_id.isnot(None),
                    User.team_id.isnot(None)
                ).group_by(User.team_id).subquery()
                
                team_rows = session.query(
                    ChallengeParticipant,
                    Team,
                    participants_stats.c.members_count,
                    participants_stats.c.avg_value,
                    participants_stats.c.best_value
                ).join(
                    Team,
                    Team.id == ChallengeParticipant.team_id
                ).outerjoin(
                    participants_stats,
                    participants_stats.c.team_id == ChallengeParticipant.team_id
                ).filter(
                    ChallengeParticipant.challenge_id == challenge_id,
                    ChallengeParticipant.team_id.isnot(None)
                ).order_by(
                    ChallengeParticipant.current_value.desc()
                ).limit(limit).all()
                
                leaderboard = []
                for index, (participant, team, members_count, avg_value, best_value) in enumerate(team_rows, start=1):
                    total_value = participant.current_value or 0
                    members_count = members_count or 0
                    avg_value = avg_value or 0
                    best_value = best_value or 0
                    percentage = (total_value / challenge.target_value * 100) if challenge.target_value > 0 else 0
                    
                    leaderboard.append({
                        'rank': index,
                        'team_id': team.id,
                        'team_name': team.name,
                        'members_count': int(members_count),
                        'total_value': total_value,
                        'average_value': round(avg_value, 2),
                        'best_member_value': best_value,
                        'percentage': round(percentage, 1),
                        'completed': participant.completed,
                        'reward_granted': participant.reward_granted,
                        'reward_granted_at': participant.reward_granted_at.isoformat() + 'Z' if participant.reward_granted_at else None,
                        'reward_points_awarded': participant.reward_points_awarded,
                        'last_activity': participant.last_activity_at.isoformat() + 'Z' if participant.last_activity_at else None
                    })
                
                return jsonify({
                    'status': 200,
                    'leaderboard': leaderboard
                }), 200
        
        except Exception as e:
            logger.error(f"Error getting team leaderboard for challenge {challenge_id}: {e}", exc_info=True)
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
                    Challenge,
                    ChallengeParticipant
                ).join(
                    ChallengeParticipant,
                    Challenge.id == ChallengeParticipant.challenge_id
                ).filter(
                    ChallengeParticipant.user_id == user_id
                )
                
                if status_filter == 'active':
                    query = query.filter(ChallengeParticipant.completed == False)
                elif status_filter == 'completed':
                    query = query.filter(ChallengeParticipant.completed == True)
                
                results = query.order_by(Challenge.end_at.desc()).all()
                
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
                            'reward_granted': participant.reward_granted,
                            'reward_granted_at': participant.reward_granted_at.isoformat() if participant.reward_granted_at else None,
                            'reward_points_awarded': participant.reward_points_awarded,
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
