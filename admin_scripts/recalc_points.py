import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import User, Feed, Activity, Team
from sqlalchemy import func

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def recalculate_user_points(user_id):
    """
    Пересчитывает баллы пользователя на основе его постов
    
    Args:
        user_id: ID пользователя
        
    Returns:
        int: Общее количество баллов
    """
    try:
        with get_session() as session:
            total_points = session.query(func.sum(Feed.points)).filter(
                Feed.author_id == user_id
            ).scalar() or 0
            
            total_points = int(total_points)
            
            session.query(User).filter(User.id == user_id).update({
                User.points: total_points
            })
            session.commit()
            
            calculate_teams_points()
            
            logger.info(f"User {user_id} points recalculated: {total_points}")
            return total_points
            
    except Exception as e:
        logger.error(f"Error recalculating user {user_id} points: {e}", exc_info=True)
        raise


def recalculate_all_users_points():
    """
    Пересчитывает баллы для всех пользователей
    """
    try:
        with get_session() as session:
            users = session.query(User.id).all()
            
            for user in users:
                user_id = user[0]
                recalculate_user_points(user_id)
        
        logger.info(f"All users points recalculated successfully")
        
    except Exception as e:
        logger.error(f"Error recalculating all users points: {e}", exc_info=True)
        raise


def calculate_teams_points():
    """
    Пересчитывает баллы всех команд на основе баллов участников
    """
    try:
        with get_session() as session:
            team_ids = session.query(User.team_id).filter(
                User.team_id.isnot(None)
            ).distinct().all()
            
            for (team_id,) in team_ids:
                total_points = session.query(func.sum(User.points)).filter(
                    User.team_id == team_id
                ).scalar() or 0
                
                session.query(Team).filter(Team.id == team_id).update({
                    Team.points: total_points
                })
            
            session.commit()
            logger.info("All teams points recalculated successfully")
            
    except Exception as e:
        logger.error(f"Error recalculating teams points: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Recalculate points for users and teams')
    parser.add_argument('--user', type=int, help='Recalculate points for specific user ID')
    parser.add_argument('--all', action='store_true', help='Recalculate points for all users')
    parser.add_argument('--teams', action='store_true', help='Recalculate points for all teams')
    
    args = parser.parse_args()
    
    if args.user:
        recalculate_user_points(args.user)
    elif args.all:
        recalculate_all_users_points()
    elif args.teams:
        calculate_teams_points()
    else:
        print("Usage:")
        print("  python recalc_points.py --user USER_ID")
        print("  python recalc_points.py --all")
        print("  python recalc_points.py --teams")
