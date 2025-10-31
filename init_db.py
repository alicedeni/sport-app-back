import sys
import os
from dotenv import load_dotenv

load_dotenv(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.infra.db.sqlalchemy_db import engine, Base
from app.domain.models import (
    User, Team, Activity, Feed, Like, Comment, CommentLike,
    Challenge, UserChallenge, UserChallengeStatus, TokenBlacklist,
    UserProgress, PasswordReset, AuditLog, AppSettings, FeatureFlag,
    ErrorLog, SystemLog, Task
)
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    try:
        logger.info("Инициализация базы данных...")
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"Подключение успешно: {version}")
        
        logger.info("Создание таблиц...")
        Base.metadata.create_all(bind=engine)
        logger.info("✓ Все таблицы созданы!")
        
        logger.info(f"Создано таблиц: {len(Base.metadata.tables)}")
        add_initial_data()
        
        logger.info("✓ Инициализация завершена успешно!")
        return True
        
    except Exception as e:
        logger.error(f"✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def add_initial_data():
    from sqlalchemy.orm import Session
    
    try:
        with Session(engine) as session:
            existing_settings = session.query(AppSettings).first()
            if existing_settings:
                logger.info("Начальные данные уже существуют")
                return
            
            logger.info("Добавление начальных данных...")
            settings = [
                AppSettings(key='app_name', value='Sport App', description='Название приложения'),
                AppSettings(key='maintenance_mode', value='false', description='Режим обслуживания'),
                AppSettings(key='registration_enabled', value='true', description='Регистрация разрешена'),
            ]
            session.add_all(settings)
            
            features = [
                FeatureFlag(key='challenges_enabled', enabled=True, description='Челленджи'),
                FeatureFlag(key='teams_enabled', enabled=True, description='Команды'),
                FeatureFlag(key='comments_enabled', enabled=True, description='Комментарии'),
            ]
            session.add_all(features)
            
            activities = [
                Activity(id=0, name='Ходьба', scorecard=None, proportion_points=None, color='#FF7745', 
                        tag='walk', met=5, avg_speed=6, low_speed=None, high_speed=None),
                Activity(id=1, name='Бег', scorecard=None, proportion_points=None, color='#00AF56', 
                        tag='run', met=10, avg_speed=12, low_speed=11, high_speed=13.5),
                Activity(id=2, name='Плавание', scorecard=None, proportion_points=None, color='#51B8FF', 
                        tag='pool', met=8, avg_speed=3, low_speed=2.5, high_speed=6),
                Activity(id=3, name='Кардио', scorecard=None, proportion_points=None, color='#FFB700', 
                        tag='cardio', met=6, avg_speed=7, low_speed=None, high_speed=None),
                Activity(id=4, name='Силовая тренировка', scorecard=None, proportion_points=None, color='#FF3D75', 
                        tag='power', met=5, avg_speed=5.6, low_speed=None, high_speed=None),
                Activity(id=5, name='Велотренировка', scorecard=None, proportion_points=None, color='#9393FF', 
                        tag='bike', met=7, avg_speed=22, low_speed=16, high_speed=28),
                Activity(id=6, name='Танцы', scorecard=None, proportion_points=None, color='#F957F9', 
                        tag='dance', met=5, avg_speed=5.8, low_speed=None, high_speed=None),
                Activity(id=7, name='Спортивные игры', scorecard=None, proportion_points=None, color='#0078D4', 
                        tag='game', met=8.5, avg_speed=8.5, low_speed=None, high_speed=None),
                Activity(id=8, name='Йога', scorecard=None, proportion_points=None, color='#00B5A6', 
                        tag='yoga', met=3, avg_speed=4.8, low_speed=None, high_speed=None),
                Activity(id=9, name='Другое', scorecard=None, proportion_points=None, color='#808080', 
                        tag='other', met=5, avg_speed=6, low_speed=None, high_speed=None),
            ]
            session.add_all(activities)
            
            session.commit()
            logger.info("✓ Начальные данные добавлены")
            
    except Exception as e:
        logger.error(f"✗ Ошибка при добавлении данных: {e}")


def drop_all_tables():
    logger.warning("⚠ ВНИМАНИЕ! Удаление всех таблиц из базы данных!")
    confirm = input("Введите 'YES' для подтверждения: ")
    
    if confirm == 'YES':
        try:
            logger.info("Удаление таблиц...")
            Base.metadata.drop_all(bind=engine)
            logger.info("✓ Все таблицы удалены")
            return True
        except Exception as e:
            logger.error(f"✗ Ошибка: {e}")
            return False
    else:
        logger.info("Операция отменена")
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Управление базой данных Sport App')
    parser.add_argument('--drop', action='store_true', help='Удалить все таблицы')
    parser.add_argument('--recreate', action='store_true', help='Пересоздать базу данных')
    
    args = parser.parse_args()
    
    if args.recreate:
        logger.info("Режим пересоздания базы данных")
        if drop_all_tables():
            init_database()
    elif args.drop:
        drop_all_tables()
    else:
        init_database()
