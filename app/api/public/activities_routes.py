from flask import jsonify, request
import logging
from app.api.public.auth_routes import token_required
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import Activity, Feed
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def init_activities_routes(app):
    def parse_duration_to_minutes(duration_str):
        """Преобразует duration в формате 'HH:MM' в минуты"""
        if not duration_str or duration_str == '' or duration_str == '00:00':
            return 0
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:
                hours = int(parts[0])
                minutes = int(parts[1])
                return hours * 60 + minutes
        except (ValueError, AttributeError):
            pass
        return 0

    @app.route('/user/activities/week', methods=['GET'])
    @token_required
    def activities_week():
        user_id = request.user_id
        try:
            week_ago = datetime.utcnow() - timedelta(weeks=1)
            with get_session() as session:
                rows = session.query(
                    Activity.tag, Activity.name, Activity.color, Feed.duration
                ).join(Feed, Activity.id == Feed.activity_id).filter(
                    Feed.author_id == user_id,
                    Feed.time_of_publication >= week_ago
                ).all()
            
            activities_dict = {}
            for row in rows:
                tag, name, color, duration = row
                if tag not in activities_dict:
                    activities_dict[tag] = {
                        'tag': tag,
                        'type': name,
                        'color': color,
                        'total_minutes': 0
                    }
                activities_dict[tag]['total_minutes'] += parse_duration_to_minutes(duration)
            
            activities = []
            for activity_data in activities_dict.values():
                total_minutes = activity_data['total_minutes']
                hours = int(total_minutes // 60)
                minutes = int(total_minutes % 60)
                time_str = f"{hours:02}:{minutes:02}"
                average_time = round(total_minutes / 7) if total_minutes else 0
                activities.append({
                    'tag': activity_data['tag'],
                    'type': activity_data['type'],
                    'color': activity_data['color'],
                    'time': time_str,
                    'average': average_time
                })
            return jsonify({'status': 200, 'activities': activities})
        except Exception as e:
            logger.error(f"Error in activities_week: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': f'Error fetching data: {str(e)}'}), 500

    @app.route('/user/activities/month', methods=['GET'])
    @token_required
    def activities_month():
        user_id = request.user_id
        try:
            month_ago = datetime.utcnow() - timedelta(days=30)
            with get_session() as session:
                rows = session.query(
                    Activity.tag, Activity.name, Activity.color, Feed.duration
                ).join(Feed, Activity.id == Feed.activity_id).filter(
                    Feed.author_id == user_id,
                    Feed.time_of_publication >= month_ago
                ).all()
            
            activities_dict = {}
            for row in rows:
                tag, name, color, duration = row
                if tag not in activities_dict:
                    activities_dict[tag] = {
                        'tag': tag,
                        'type': name,
                        'color': color,
                        'total_minutes': 0
                    }
                activities_dict[tag]['total_minutes'] += parse_duration_to_minutes(duration)
            
            activities = []
            for activity_data in activities_dict.values():
                total_minutes = activity_data['total_minutes']
                hours = int(total_minutes // 60)
                minutes = int(total_minutes % 60)
                time_str = f"{hours:02}:{minutes:02}"
                average_time = round(total_minutes / 30) if total_minutes else 0
                activities.append({
                    'tag': activity_data['tag'],
                    'type': activity_data['type'],
                    'color': activity_data['color'],
                    'time': time_str,
                    'average': average_time
                })
            return jsonify({'status': 200, 'activities': activities})
        except Exception as e:
            logger.error(f"Error in activities_month: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': f'Error fetching data: {str(e)}'}), 500

    @app.route('/user/activities/all', methods=['GET'])
    @token_required
    def activities_all():
        user_id = request.user_id
        try:
            with get_session() as session:
                rows = session.query(
                    Activity.tag, Activity.name, Activity.color, Feed.duration
                ).join(Feed, Activity.id == Feed.activity_id).filter(
                    Feed.author_id == user_id
                ).all()
            
            activities_dict = {}
            for row in rows:
                tag, name, color, duration = row
                if tag not in activities_dict:
                    activities_dict[tag] = {
                        'tag': tag,
                        'type': name,
                        'color': color,
                        'total_minutes': 0
                    }
                activities_dict[tag]['total_minutes'] += parse_duration_to_minutes(duration)
            
            activities = []
            for activity_data in activities_dict.values():
                total_minutes = activity_data['total_minutes']
                hours = int(total_minutes // 60)
                minutes = int(total_minutes % 60)
                time_str = f"{hours:02}:{minutes:02}"
                activities.append({
                    'tag': activity_data['tag'],
                    'type': activity_data['type'],
                    'color': activity_data['color'],
                    'time': time_str
                })
            return jsonify({'status': 200, 'activities': activities})
        except Exception as e:
            logger.error(f"Error in activities_all: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': f'Error fetching data: {str(e)}'}), 500

