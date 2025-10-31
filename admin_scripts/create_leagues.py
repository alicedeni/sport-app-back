import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import User

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def create_leagues():
    """
    Распределяет пользователей по лигам на основе их баллов
    
    Лиги:
    - Gold (топ 33%)
    - Silver (средние 33%)
    - Bronze (нижние 33%)
    """
    try:
        with get_session() as session:
            users = session.query(User.id, User.points).order_by(
                User.points.desc()
            ).all()
            
            total_users = len(users)
            
            if total_users == 0:
                logger.warning("No users found in database")
                return
            
            num_gold = total_users // 3
            num_silver = total_users // 3
            
            logger.info(f"Distributing {total_users} users into leagues:")
            logger.info(f"  Gold: {num_gold} users")
            logger.info(f"  Silver: {num_silver} users")
            logger.info(f"  Bronze: {total_users - num_gold - num_silver} users")
            
            for idx, (user_id, points) in enumerate(users):
                if idx < num_gold:
                    league = 'gold'
                elif idx < num_gold + num_silver:
                    league = 'silver'
                else:
                    league = 'bronze'
                
                session.query(User).filter(User.id == user_id).update({
                    User.league: league
                })
            
            session.commit()
            
            gold_count = session.query(User).filter(User.league == 'gold').count()
            silver_count = session.query(User).filter(User.league == 'silver').count()
            bronze_count = session.query(User).filter(User.league == 'bronze').count()
            
            logger.info(f"Leagues created successfully:")
            logger.info(f"  Gold: {gold_count} users")
            logger.info(f"  Silver: {silver_count} users")
            logger.info(f"  Bronze: {bronze_count} users")
            
    except Exception as e:
        logger.error(f"Error creating leagues: {e}", exc_info=True)
        raise


def get_league_statistics():
    """
    Возвращает статистику по лигам
    
    Returns:
        dict: Статистика по каждой лиге
    """
    try:
        with get_session() as session:
            from sqlalchemy import func
            
            stats = session.query(
                User.league,
                func.count(User.id).label('count'),
                func.avg(User.points).label('avg_points'),
                func.sum(User.points).label('total_points')
            ).group_by(User.league).all()
            
            result = {}
            for league, count, avg_points, total_points in stats:
                result[league] = {
                    'count': count,
                    'avg_points': round(avg_points or 0, 2),
                    'total_points': total_points or 0
                }
            
            return result
            
    except Exception as e:
        logger.error(f"Error getting league statistics: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Create and manage user leagues')
    parser.add_argument('--create', action='store_true', help='Create/update leagues')
    parser.add_argument('--stats', action='store_true', help='Show league statistics')
    
    args = parser.parse_args()
    
    if args.create:
        create_leagues()
    elif args.stats:
        stats = get_league_statistics()
        print("\nLeague Statistics:")
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        print("Usage:")
        print("  python create_leagues.py --create")
        print("  python create_leagues.py --stats")
