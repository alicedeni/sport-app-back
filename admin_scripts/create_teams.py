import sys
import os
import random
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import User, Team
from sqlalchemy import func

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def create_teams():
    """
    Создает команды и распределяет пользователей случайным образом
    Группы по 2-3 человека
    """
    try:
        with get_session() as session:
            users = session.query(User.id).all()
            user_ids = [user[0] for user in users]
            
            if not user_ids:
                logger.warning("No users found in database")
                return
            
            random.shuffle(user_ids)
            
            session.query(User).update({User.team_id: None})
            session.query(Team).delete()
            session.commit()
            
            logger.info(f"Creating teams for {len(user_ids)} users")
            
            team_id = 1
            i = 0
            
            while i < len(user_ids):
                group_size = random.randint(2, 3)
                if i + group_size > len(user_ids):
                    group_size = len(user_ids) - i
                
                group = user_ids[i:i + group_size]
                
                new_team = Team(
                    id=team_id,
                    name=f'Команда {team_id}',
                    points=0
                )
                session.add(new_team)
                
                for user_id in group:
                    session.query(User).filter(User.id == user_id).update({
                        User.team_id: team_id
                    })
                
                logger.info(f"Team {team_id} created with {len(group)} members")
                team_id += 1
                i += group_size
            
            session.commit()
            
            calculate_teams_points()
            
            logger.info(f"Successfully created {team_id - 1} teams")
            
    except Exception as e:
        logger.error(f"Error creating teams: {e}", exc_info=True)
        raise


def calculate_team_points(team_id):
    """
    Рассчитывает и обновляет баллы конкретной команды
    
    Args:
        team_id: ID команды
    """
    try:
        with get_session() as session:
            total_points = session.query(func.sum(User.points)).filter(
                User.team_id == team_id
            ).scalar() or 0
            
            session.query(Team).filter(Team.id == team_id).update({
                Team.points: total_points
            })
            session.commit()
            
            logger.info(f"Team {team_id} points updated: {total_points}")
            
    except Exception as e:
        logger.error(f"Error calculating team {team_id} points: {e}", exc_info=True)
        raise


def calculate_teams_points():
    """
    Пересчитывает баллы для всех команд
    """
    try:
        with get_session() as session:
            team_ids = session.query(User.team_id).filter(
                User.team_id.isnot(None)
            ).distinct().all()
            
            for (team_id,) in team_ids:
                if team_id:
                    calculate_team_points(team_id)
            
            logger.info("All teams points calculated successfully")
            
    except Exception as e:
        logger.error(f"Error calculating teams points: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Create and manage teams')
    parser.add_argument('--create', action='store_true', help='Create new teams')
    parser.add_argument('--recalc', action='store_true', help='Recalculate teams points')
    parser.add_argument('--team', type=int, help='Recalculate points for specific team ID')
    
    args = parser.parse_args()
    
    if args.create:
        create_teams()
    elif args.recalc:
        calculate_teams_points()
    elif args.team:
        calculate_team_points(args.team)
    else:
        print("Usage:")
        print("  python create_teams.py --create")
        print("  python create_teams.py --recalc")
        print("  python create_teams.py --team TEAM_ID")
