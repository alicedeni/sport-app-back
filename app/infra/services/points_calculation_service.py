from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import Activity, User
import logging

logger = logging.getLogger(__name__)


class ActivityCalculationService:
    ACTIVITY_WALK = 0
    ACTIVITY_RUN = 1
    ACTIVITY_BIKE = 2
    ACTIVITY_SWIM = 5
    
    STRIDE_COEFFICIENT = 0.414  # коэффициент для расчета шага
    METERS_TO_KM = 0.001
    POINTS_PER_CALORIE_RATIO = 10  # 10 калорий = 1 балл
    
    def __init__(self):
        """Инициализация сервиса"""
        pass
    
    def get_user_data(self, user_id: int) -> Optional[Dict]:
        """Получить данные пользователя для расчетов"""
        try:
            with get_session() as session:
                user = session.query(
                    User.weight, User.height, User.gender, User.league
                ).filter(User.id == user_id).first()
                
                if not user:
                    return None
                
                return {
                    'weight': user.weight or 70,
                    'height': user.height or 170,
                    'gender': user.gender or 'М',
                    'league': user.league or 'silver'
                }
        except Exception as e:
            logger.error(f"Error fetching user data for user_id {user_id}: {e}")
            return None
    
    def get_activity_data(self, activity_tag: str) -> Optional[Dict]:
        """Получить данные активности по тегу"""
        try:
            with get_session() as session:
                activity = session.query(
                    Activity.id,
                    Activity.met,
                    Activity.proportion_points,
                    Activity.avg_speed,
                    Activity.low_speed,
                    Activity.high_speed
                ).filter(Activity.tag == activity_tag).first()
                
                if not activity:
                    return None
                
                return {
                    'id': activity.id,
                    'met': activity.met,
                    'proportion_points': activity.proportion_points,
                    'avg_speed': activity.avg_speed,
                    'low_speed': activity.low_speed,
                    'high_speed': activity.high_speed
                }
        except Exception as e:
            logger.error(f"Error fetching activity data for tag {activity_tag}: {e}")
            return None
    
    def get_user_speed(self, user_id: int, activity_id: int) -> Optional[float]:
        """Получить скорость пользователя в зависимости от лиги"""
        user_data = self.get_user_data(user_id)
        if not user_data:
            return None
        
        activity_data = None
        try:
            with get_session() as session:
                activity = session.query(
                    Activity.avg_speed,
                    Activity.low_speed,
                    Activity.high_speed
                ).filter(Activity.id == activity_id).first()
                
                if not activity:
                    return None
                
                league = user_data['league']
                if league == 'silver':
                    return activity.avg_speed
                elif league == 'gold':
                    return activity.high_speed
                else:
                    return activity.low_speed
        except Exception as e:
            logger.error(f"Error getting user speed: {e}")
            return None
    
    def calculate_stride(self, height: Optional[int], gender: Optional[str]) -> float:
        """Рассчитать длину шага"""
        if height and height > 0:
            return height * 0.00414
        elif gender == 'М':
            return 0.73
        elif gender == 'Ж':
            return 0.68
        else:
            return 0.705
    
    def parse_duration(self, duration_str: Optional[str]) -> Optional[float]:
        """Парсинг продолжительности из строки 'HH:MM' в часы (float)"""
        if not duration_str:
            return None
        
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:
                hours = int(parts[0])
                minutes = int(parts[1])
                return hours + minutes / 60.0
        except (ValueError, AttributeError):
            pass
        
        return None
    
    def format_duration(self, duration_hours: float) -> str:
        """Форматирование продолжительности из часов в 'HH:MM'"""
        hours = int(duration_hours)
        minutes = int((duration_hours - hours) * 60)
        return f"{hours:02}:{minutes:02}"
    
    def calculate_activity_distance_and_duration(
        self,
        activity_id: int,
        activity_data: Dict,
        user_data: Dict,
        user_id: int
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Рассчитать дистанцию и продолжительность активности
        
        Returns:
            Tuple[distance, duration_hours] - дистанция в км, продолжительность в часах
        """
        duration_hours = self.parse_duration(activity_data.get('duration'))
        distance = activity_data.get('distance')
        
        # Безопасное приведение distance к числу
        if distance:
            try:
                distance = float(distance)
            except (ValueError, TypeError):
                distance = None
        
        # Ходьба (activity_id == 0)
        if activity_id == self.ACTIVITY_WALK:
            steps = activity_data.get('steps', 0)
            # Приводим steps к числу (может прийти как строка)
            try:
                steps = int(steps) if steps else 0
            except (ValueError, TypeError):
                steps = 0
            
            if steps and steps > 0:
                stride = self.calculate_stride(user_data.get('height'), user_data.get('gender'))
                distance = stride * steps * self.METERS_TO_KM
                
                if not duration_hours:
                    with get_session() as session:
                        avg_speed = session.query(Activity.avg_speed).filter(
                            Activity.id == activity_id
                        ).scalar()
                    if avg_speed:
                        duration_hours = distance / avg_speed
            
            return round(distance, 2) if distance else None, duration_hours
        
        # Бег, плавание (activity_id in [1, 5])
        elif activity_id in [self.ACTIVITY_RUN, self.ACTIVITY_SWIM]:
            if distance:
                if not duration_hours:
                    user_speed = self.get_user_speed(user_id, activity_id)
                    if user_speed:
                        duration_hours = distance / user_speed
                
                return round(distance, 2), duration_hours
            elif duration_hours:
                return None, duration_hours
        
        # Велосипед (activity_id == 2)
        elif activity_id == self.ACTIVITY_BIKE:
            if distance:
                # Для велосипеда distance приходит в метрах, конвертируем в км
                distance = distance * self.METERS_TO_KM
                if not duration_hours:
                    user_speed = self.get_user_speed(user_id, activity_id)
                    if user_speed:
                        duration_hours = distance / user_speed
                
                return round(distance, 2), duration_hours
        
        # Другие активности
        else:
            if duration_hours is None:
                duration_str = activity_data.get('duration')
                if duration_str:
                    duration_hours = self.parse_duration(duration_str)
            
            return None, duration_hours
    
    def calculate_calories_per_km(
        self,
        weight: float,
        walking_met: float,
        walking_speed: float
    ) -> float:
        """
        Рассчитать калории на километр ходьбы (базовый расчет)
        
        Args:
            weight: вес пользователя в кг
            walking_met: MET для ходьбы
            walking_speed: скорость ходьбы в км/ч
        
        Returns:
            Калории на километр
        """
        duration_per_km = 60 / walking_speed
        calories_per_km = walking_met * weight * (duration_per_km / 60)
        return calories_per_km
    
    def calculate_calories_and_points(
        self,
        activity_id: int,
        met: float,
        activity_data: Dict,
        user_data: Dict,
        duration_hours: Optional[float],
        calories_per_km: float,
        user_id: int
    ) -> Tuple[float, int]:
        """
        Рассчитать сожженные калории и баллы за активность
        
        Args:
            activity_id: ID активности
            met: MET коэффициент активности
            activity_data: данные активности (distance, steps, etc.)
            user_data: данные пользователя (weight, height, gender, league)
            duration_hours: продолжительность в часах
            calories_per_km: базовое количество калорий на км (для ходьбы)
            user_id: ID пользователя
        
        Returns:
            Tuple[calories_burned, points] - калории и баллы
        """
        weight = user_data.get('weight', 70)
        
        # Ходьба (activity_id == 0)
        if activity_id == self.ACTIVITY_WALK:
            steps = activity_data.get('steps', 0)
            # Приводим steps к числу (может прийти как строка)
            try:
                steps = int(steps) if steps else 0
            except (ValueError, TypeError):
                steps = 0
            
            if steps and steps > 0:
                with get_session() as session:
                    avg_speed = session.query(Activity.avg_speed).filter(
                        Activity.id == activity_id
                    ).scalar()
                
                if avg_speed:
                    stride = self.calculate_stride(
                        user_data.get('height'),
                        user_data.get('gender')
                    )
                    calories_burned_per_kg = met * steps * stride * self.METERS_TO_KM / avg_speed
                    calories_burned = calories_burned_per_kg * weight
                else:
                    distance = activity_data.get('distance', 0)
                    try:
                        distance = float(distance) if distance else 0
                    except (ValueError, TypeError):
                        distance = 0
                    calories_burned = calories_per_km * distance if distance else 0
            else:
                calories_burned = 0
        
        # Бег, плавание (activity_id in [1, 5])
        elif activity_id in [self.ACTIVITY_RUN, self.ACTIVITY_SWIM]:
            distance = activity_data.get('distance', 0)
            # Безопасное приведение к числу
            try:
                distance = float(distance) if distance else 0
            except (ValueError, TypeError):
                distance = 0
            
            if distance:
                user_speed = self.get_user_speed(user_id, activity_id)
                if user_speed:
                    calories_burned_per_kg = met * distance / user_speed
                    calories_burned = calories_burned_per_kg * weight
                else:
                    calories_burned = met * weight * distance / 10 
            else:
                calories_burned = 0
        
        # Велосипед (activity_id == 2)
        elif activity_id == self.ACTIVITY_BIKE:
            distance = activity_data.get('distance', 0)
            # Безопасное приведение к числу
            try:
                distance = float(distance) if distance else 0
            except (ValueError, TypeError):
                distance = 0
            
            if distance:
                distance_km = distance * self.METERS_TO_KM
                user_speed = self.get_user_speed(user_id, activity_id)
                if user_speed:
                    calories_burned_per_kg = met * distance_km / user_speed
                    calories_burned = calories_burned_per_kg * weight
                else:
                    calories_burned = met * weight * distance_km / 10
            else:
                calories_burned = 0
        
        # Другие активности
        else:
            if duration_hours:
                calories_burned_per_kg = met * duration_hours
                calories_burned = calories_burned_per_kg * weight
            else:
                calories_burned = 0
        
        # Расчет баллов: калории / базовые_калории_на_км * 10
        if calories_per_km > 0:
            activity_points = int((calories_burned / calories_per_km) * self.POINTS_PER_CALORIE_RATIO)
        else:
            activity_points = 0
        
        return round(calories_burned, 2), activity_points
    
    def calculate_activity_metrics(
        self,
        activity_tag: str,
        activity_input_data: Dict,
        user_id: int
    ) -> Dict:
        """
        Главный метод для расчета всех метрик активности
        
        Args:
            activity_tag: тег активности (run, walk, bike, etc.)
            activity_input_data: входные данные активности от пользователя
            user_id: ID пользователя
        
        Returns:
            Dict с ключами:
                - distance: дистанция в км
                - duration_hours: продолжительность в часах
                - duration_formatted: продолжительность в формате 'HH:MM'
                - calories_burned: калории
                - activity_points: баллы
                - activity_id: ID активности
        
        Raises:
            ValueError: если данные некорректны
        """
        activity_info = self.get_activity_data(activity_tag)
        if not activity_info:
            raise ValueError(f"Activity with tag '{activity_tag}' not found")
        
        user_data = self.get_user_data(user_id)
        if not user_data:
            raise ValueError(f"User with id {user_id} not found")
        
        with get_session() as session:
            walking = session.query(
                Activity.met,
                Activity.avg_speed
            ).filter(Activity.tag == 'walk').first()
        
        if not walking:
            raise ValueError("Walking activity not configured in database")
        
        walking_met, walking_speed = walking.met, walking.avg_speed
        
        calories_per_km = self.calculate_calories_per_km(
            user_data['weight'],
            walking_met,
            walking_speed
        )
        
        distance, duration_hours = self.calculate_activity_distance_and_duration(
            activity_info['id'],
            activity_input_data,
            user_data,
            user_id
        )
        
        calories_burned, activity_points = self.calculate_calories_and_points(
            activity_info['id'],
            activity_info['met'],
            activity_input_data,
            user_data,
            duration_hours,
            calories_per_km,
            user_id
        )
        
        duration_formatted = self.format_duration(duration_hours) if duration_hours else '00:00'
        
        return {
            'distance': distance,
            'duration_hours': duration_hours,
            'duration_formatted': duration_formatted,
            'calories_burned': calories_burned,
            'activity_points': activity_points,
            'activity_id': activity_info['id'],
            'calories_per_km': calories_per_km
        }


_points_service = None

def get_points_service() -> ActivityCalculationService:
    """Получить экземпляр сервиса расчета баллов (singleton)"""
    global _points_service
    if _points_service is None:
        _points_service = ActivityCalculationService()
    return _points_service


def calculate_activity_metrics_wrapper(activity_tag: str, activity_data: Dict, user_id: int) -> Dict:
    """Обертка для совместимости со старым кодом"""
    service = get_points_service()
    return service.calculate_activity_metrics(activity_tag, activity_data, user_id)

