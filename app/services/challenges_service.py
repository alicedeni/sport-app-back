from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import Feed, Challenge, ChallengeParticipant, Activity, User
from sqlalchemy import and_
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ChallengesService:
    """Сервис обновления прогресса челленджей"""
    
    @staticmethod
    def update_challenge_progress(user_id: int, activity: Feed):
        """
        Обновить прогресс пользователя во всех активных челленджах
        Вызывается автоматически после создания активности
        """
        try:
            with get_session() as session:
                user_record = session.query(User.id, User.team_id).filter(User.id == user_id).first()
                user_team_id = user_record.team_id if user_record else None
                now = datetime.utcnow()
                
                activity_tag = None
                if activity.activity_id is not None:
                    activity_obj = session.query(Activity.tag).filter(
                        Activity.id == activity.activity_id
                    ).first()
                    if activity_obj:
                        activity_tag = activity_obj[0]
                
                def calculate_metric_value(challenge_obj: Challenge) -> float:
                    if challenge_obj.metric_type == 'distance':
                        return float(activity.distance) if activity.distance else 0
                    if challenge_obj.metric_type == 'calories':
                        return float(activity.calories) if activity.calories else 0
                    if challenge_obj.metric_type == 'points':
                        return float(activity.points) if activity.points else 0
                    if challenge_obj.metric_type == 'steps':
                        return float(activity.steps) if activity.steps else 0
                    if challenge_obj.metric_type == 'duration':
                        duration_val = activity.duration or activity.duration_hours if hasattr(activity, 'duration_hours') else activity.duration
                        duration_str = duration_val if isinstance(duration_val, str) else getattr(activity, 'duration', None)
                        if not duration_str:
                            return 0
                        try:
                            hours, minutes = duration_str.split(':')
                            hours = int(hours)
                            minutes = int(minutes)
                            return hours + minutes / 60.0
                        except Exception:
                            return 0
                    return 0
                
                user_participations = session.query(
                    Challenge, ChallengeParticipant
                ).join(
                    ChallengeParticipant,
                    Challenge.id == ChallengeParticipant.challenge_id
                ).filter(
                    and_(
                        ChallengeParticipant.user_id == user_id,
                        ChallengeParticipant.completed == False,
                        Challenge.status == 'active',
                        Challenge.start_at <= now,
                        Challenge.end_at >= now
                    )
                ).all()
                
                if user_participations:
                    logger.info(f"Checking {len(user_participations)} active challenges for user {user_id}")
                
                for challenge, participant in user_participations:
                    if challenge.activity_types and activity_tag:
                        if activity_tag not in challenge.activity_types:
                            logger.debug(f"Activity type {activity_tag} not in challenge {challenge.id} types")
                            continue
                    
                    metric_value = calculate_metric_value(challenge)
                    
                    if metric_value <= 0:
                        continue
                    
                    old_value = participant.current_value
                    participant.current_value += metric_value
                    participant.last_activity_at = datetime.utcnow()
                    
                    if not participant.completed and participant.current_value >= challenge.target_value:
                        participant.completed = True
                        participant.completed_at = datetime.utcnow()
                        participant.reward_granted = participant.reward_granted or False
                        logger.info(
                            f"✓ User {user_id} completed challenge '{challenge.name}' "
                            f"({old_value} -> {participant.current_value}/{challenge.target_value}). "
                            f"Reward pending manual approval."
                        )
                    else:
                        logger.info(
                            f"User {user_id} progress in challenge '{challenge.name}': "
                            f"{old_value} -> {participant.current_value}/{challenge.target_value}"
                        )
                
                if user_team_id:
                    team_participations = session.query(
                        Challenge, ChallengeParticipant
                    ).join(
                        ChallengeParticipant,
                        Challenge.id == ChallengeParticipant.challenge_id
                    ).filter(
                        and_(
                            ChallengeParticipant.team_id == user_team_id,
                            ChallengeParticipant.completed == False,
                            Challenge.challenge_type == 'team',
                            Challenge.status == 'active',
                            Challenge.start_at <= now,
                            Challenge.end_at >= now
                        )
                    ).all()
                    
                    if team_participations:
                        logger.info(f"Checking {len(team_participations)} active team challenges for team {user_team_id}")
                    
                    for challenge, team_participant in team_participations:
                        if challenge.activity_types and activity_tag:
                            if activity_tag not in challenge.activity_types:
                                continue
                        
                        metric_value = calculate_metric_value(challenge)
                        if metric_value <= 0:
                            continue
                        
                        old_value = team_participant.current_value
                        team_participant.current_value += metric_value
                        team_participant.last_activity_at = datetime.utcnow()
                        
                        if not team_participant.completed and team_participant.current_value >= challenge.target_value:
                            team_participant.completed = True
                            team_participant.completed_at = datetime.utcnow()
                            logger.info(
                                f"✓ Team {user_team_id} completed challenge '{challenge.name}' "
                                f"({old_value} -> {team_participant.current_value}/{challenge.target_value}). "
                                f"Reward pending manual approval."
                            )
                        else:
                            logger.info(
                                f"Team {user_team_id} progress in challenge '{challenge.name}': "
                                f"{old_value} -> {team_participant.current_value}/{challenge.target_value}"
                            )
                
                session.commit()
        
        except Exception as e:
            logger.error(f"Error updating challenge progress for user {user_id}: {e}", exc_info=True)

_challenges_service = None

def get_challenges_service() -> ChallengesService:
    """Получить экземпляр сервиса челленджей"""
    global _challenges_service
    if _challenges_service is None:
        _challenges_service = ChallengesService()
    return _challenges_service

