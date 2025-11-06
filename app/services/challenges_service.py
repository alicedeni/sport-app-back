from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import Feed, ChallengeNew, ChallengeParticipantNew, Activity, User
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
                now = datetime.utcnow()
                
                active_participations = session.query(
                    ChallengeNew, ChallengeParticipantNew
                ).join(
                    ChallengeParticipantNew,
                    ChallengeNew.id == ChallengeParticipantNew.challenge_id
                ).filter(
                    and_(
                        ChallengeParticipantNew.user_id == user_id,
                        ChallengeParticipantNew.completed == False,
                        ChallengeNew.status == 'active',
                        ChallengeNew.start_at <= now,
                        ChallengeNew.end_at >= now
                    )
                ).all()
                
                if not active_participations:
                    return
                
                logger.info(f"Checking {len(active_participations)} active challenges for user {user_id}")
                
                activity_tag = None
                if activity.activity_id is not None:
                    activity_obj = session.query(Activity.tag).filter(
                        Activity.id == activity.activity_id
                    ).first()
                    if activity_obj:
                        activity_tag = activity_obj[0]
                
                for challenge, participant in active_participations:
                    if challenge.activity_types and activity_tag:
                        if activity_tag not in challenge.activity_types:
                            logger.debug(f"Activity type {activity_tag} not in challenge {challenge.id} types")
                            continue
                    
                    metric_value = 0
                    if challenge.metric_type == 'distance':
                        metric_value = float(activity.distance) if activity.distance else 0
                    elif challenge.metric_type == 'calories':
                        metric_value = float(activity.calories) if activity.calories else 0
                    elif challenge.metric_type == 'points':
                        metric_value = float(activity.points) if activity.points else 0
                    elif challenge.metric_type == 'steps':
                        metric_value = float(activity.steps) if activity.steps else 0
                    
                    if metric_value <= 0:
                        continue
                    
                    old_value = participant.current_value
                    participant.current_value += metric_value
                    participant.last_activity_at = datetime.utcnow()
                    
                    if not participant.completed and participant.current_value >= challenge.target_value:
                        participant.completed = True
                        participant.completed_at = datetime.utcnow()
                        
                        if challenge.reward_points and challenge.reward_points > 0:
                            user = session.query(User).filter(User.id == user_id).first()
                            if user:
                                user.points = (user.points or 0) + challenge.reward_points
                                logger.info(
                                    f"User {user_id} earned {challenge.reward_points} points "
                                    f"for completing challenge '{challenge.name}'"
                                )
                        
                        logger.info(
                            f"✓ User {user_id} completed challenge '{challenge.name}' "
                            f"({old_value} -> {participant.current_value}/{challenge.target_value}) "
                            f"- Reward: {challenge.reward_points} points"
                        )
                    else:
                        logger.info(
                            f"User {user_id} progress in challenge '{challenge.name}': "
                            f"{old_value} -> {participant.current_value}/{challenge.target_value}"
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

