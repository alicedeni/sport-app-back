from flask import jsonify, request, make_response
from app.infra.db.sqlalchemy_db import get_session
from sqlalchemy import func, and_, case
from app.domain.models import AppSettings, FeatureFlag, ErrorLog, SystemLog, User, Feed, Team, Activity, ChallengeNew
from app.api.public.auth_routes import token_required
from app.api.admin.admin_middleware import admin_required, log_audit
from app.domain.schemas import AdminSettingsSchema, AdminFeatureFlagsSchema, AdminErrorStatusSchema, validate_json_data
from app.infra.utils.admin_utils import paginate_query, format_response, parse_date_param
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


def get_timeline_stats(session, from_date, to_date, interval):
    """
    Получает статистику с группировкой по интервалам
    
    Args:
        session: SQLAlchemy session
        from_date: начальная дата
        to_date: конечная дата
        interval: day/week/month
        
    Returns:
        list: Данные по периодам
    """
    from sqlalchemy import func, cast, Date
    
    if interval == 'day':
        date_trunc = func.date_trunc('day', Feed.time_of_publication)
    elif interval == 'week':
        date_trunc = func.date_trunc('week', Feed.time_of_publication)
    elif interval == 'month':
        date_trunc = func.date_trunc('month', Feed.time_of_publication)
    else:
        return []
    
    query = session.query(
        cast(date_trunc, Date).label('period'),
        func.count(Feed.id).label('posts'),
        func.sum(Feed.calories).label('calories'),
        func.sum(Feed.points).label('points'),
        func.count(func.distinct(Feed.author_id)).label('active_users')
    )
    
    if from_date:
        query = query.filter(Feed.time_of_publication >= from_date)
    if to_date:
        to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        query = query.filter(Feed.time_of_publication <= to_date_end)
    
    results = query.group_by('period').order_by('period').all()
    
    timeline = []
    for period, posts, calories, points, users in results:
        timeline.append({
            'date': period.strftime('%Y-%m-%d'),
            'posts': posts,
            'calories': int(calories or 0),
            'points': int(points or 0),
            'activeUsers': users
        })
    
    return timeline


def init_admin_common_routes(app):
    @app.route('/admin/settings', methods=['GET'])
    @token_required
    @admin_required
    def get_settings():
        """Получить настройки приложения"""
        try:
            with get_session() as session:
                settings = session.query(AppSettings).all()
                settings_dict = {s.key: s.value for s in settings}
                return jsonify(format_response(settings_dict))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/settings', methods=['PATCH'])
    @token_required
    @admin_required
    def update_settings():
        """Обновить настройки"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminSettingsSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                old_values = {}
                new_values = {}
                
                for key, value in validated_data.items():
                    if value is not None:
                        setting = session.query(AppSettings).filter_by(key=key).first()
                        if setting:
                            old_values[key] = setting.value
                            setting.value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                            setting.updated_by = request.user_id
                            setting.updated_at = datetime.utcnow()
                        else:
                            setting = AppSettings(
                                key=key,
                                value=json.dumps(value) if isinstance(value, (dict, list)) else str(value),
                                updated_by=request.user_id
                            )
                            session.add(setting)
                        new_values[key] = value
                
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='update',
                    entity_type='settings',
                    old_value=json.dumps(old_values),
                    new_value=json.dumps(new_values)
                )
                
                return jsonify(format_response({'message': 'Settings updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/feature-flags', methods=['GET'])
    @token_required
    @admin_required
    def get_feature_flags():
        """Получить feature flags"""
        try:
            with get_session() as session:
                flags = session.query(FeatureFlag).all()
                flags_dict = {f.key: f.enabled for f in flags}
                return jsonify(format_response(flags_dict))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/feature-flags', methods=['PATCH'])
    @token_required
    @admin_required
    def update_feature_flags():
        """Обновить feature flags"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminFeatureFlagsSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                for key, enabled in validated_data['flags'].items():
                    flag = session.query(FeatureFlag).filter_by(key=key).first()
                    if flag:
                        flag.enabled = enabled
                        flag.updated_by = request.user_id
                    else:
                        flag = FeatureFlag(key=key, enabled=enabled, updated_by=request.user_id)
                        session.add(flag)
                
                session.commit()
                
                return jsonify(format_response({'message': 'Feature flags updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/stats/overview', methods=['GET'])
    @token_required
    @admin_required
    def get_stats_overview():
        """Общая статистика с группировкой по интервалам"""
        try:
            from_date = parse_date_param(request.args.get('from'))
            to_date = parse_date_param(request.args.get('to'))
            interval = request.args.get('interval', 'all')  # day, week, month, all
            
            if interval != 'all' and not from_date:
                if interval == 'day':
                    from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                elif interval == 'week':
                    from_date = datetime.now() - timedelta(days=7)
                elif interval == 'month':
                    from_date = datetime.now() - timedelta(days=30)
            
            with get_session() as session:
                query = session.query(Feed)
                if from_date:
                    query = query.filter(Feed.time_of_publication >= from_date)
                if to_date:
                    to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                    query = query.filter(Feed.time_of_publication <= to_date_end)
                
                total_posts = query.count()
                
                calories_query = session.query(func.sum(Feed.calories))
                points_query = session.query(func.sum(Feed.points))
                users_query = session.query(func.count(func.distinct(Feed.author_id)))
                
                if from_date:
                    calories_query = calories_query.filter(Feed.time_of_publication >= from_date)
                    points_query = points_query.filter(Feed.time_of_publication >= from_date)
                    users_query = users_query.filter(Feed.time_of_publication >= from_date)
                
                if to_date:
                    to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                    calories_query = calories_query.filter(Feed.time_of_publication <= to_date_end)
                    points_query = points_query.filter(Feed.time_of_publication <= to_date_end)
                    users_query = users_query.filter(Feed.time_of_publication <= to_date_end)
                
                total_calories = calories_query.scalar() or 0
                total_points = points_query.scalar() or 0
                active_users = users_query.scalar() or 0
                
                now = datetime.utcnow()
                active_challenges = session.query(func.count(ChallengeNew.id)).filter(
                    and_(
                        ChallengeNew.status == 'active',
                        ChallengeNew.start_at <= now,
                        ChallengeNew.end_at >= now
                    )
                ).scalar() or 0
                
                response_data = {
                    'totalPosts': total_posts,
                    'totalCalories': int(total_calories),
                    'totalPoints': int(total_points),
                    'activeUsers': active_users,
                    'activeChallenges': active_challenges
                }
                
                if interval != 'all':
                    timeline_data = get_timeline_stats(session, from_date, to_date, interval)
                    response_data['timeline'] = timeline_data
                
                return jsonify(format_response(response_data))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/stats/participants-rating', methods=['GET'])
    @token_required
    @admin_required
    def get_participants_rating():
        """Рейтинг участников"""
        try:
            league = request.args.get('league', '')
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                
                league_order = case(
                    (User.league == 'gold', 1),
                    (User.league == 'silver', 2),
                    else_=3
                )
                query = session.query(User).filter(
                    User.role.notin_(['admin', 'moderator'])
                ).order_by(User.points.desc(), league_order.asc())
                if league:
                    query = query.filter(User.league == league)
                
                result = paginate_query(query, page, limit)
                
                users_data = []
                for user in result['items']:
                    users_data.append({
                        'id': user.id,
                        'firstName': user.name,
                        'lastName': user.surname,
                        'progress': user.points,
                        'league': user.league
                    })
                
                return jsonify(format_response({
                    'leaderboard': users_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/errors', methods=['GET'])
    @token_required
    @admin_required
    def get_errors():
        """Список ошибок"""
        try:
            level = request.args.get('level', '')
            service = request.args.get('service', '')
            from_date = parse_date_param(request.args.get('from'))
            to_date = parse_date_param(request.args.get('to'))
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                query = session.query(ErrorLog)
                if level:
                    query = query.filter(ErrorLog.level == level)
                if service:
                    query = query.filter(ErrorLog.service == service)
                if from_date:
                    query = query.filter(ErrorLog.created_at >= from_date)
                if to_date:
                    to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                    query = query.filter(ErrorLog.created_at <= to_date_end)
                
                result = paginate_query(query.order_by(ErrorLog.created_at.desc()), page, limit)
                
                errors_data = []
                for error in result['items']:
                    errors_data.append({
                        'id': error.id,
                        'level': error.level,
                        'service': error.service,
                        'message': error.message,
                        'status': error.status,
                        'createdAt': error.created_at.isoformat() if error.created_at else None
                    })
                
                return jsonify(format_response({
                    'errors': errors_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/logs', methods=['GET'])
    @token_required
    @admin_required
    def get_logs():
        """Системные логи"""
        try:
            level = request.args.get('level', '')
            context = request.args.get('context', '')
            from_date = parse_date_param(request.args.get('from'))
            to_date = parse_date_param(request.args.get('to'))
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                query = session.query(SystemLog)
                if level:
                    query = query.filter(SystemLog.level == level)
                if context:
                    query = query.filter(SystemLog.context == context)
                if from_date:
                    query = query.filter(SystemLog.created_at >= from_date)
                if to_date:
                    to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                    query = query.filter(SystemLog.created_at <= to_date_end)
                
                result = paginate_query(query.order_by(SystemLog.created_at.desc()), page, limit)
                
                logs_data = []
                for log in result['items']:
                    logs_data.append({
                        'id': log.id,
                        'level': log.level,
                        'context': log.context,
                        'message': log.message,
                        'createdAt': log.created_at.isoformat() if log.created_at else None
                    })
                
                return jsonify(format_response({
                    'logs': logs_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/stats/teams-rating', methods=['GET'])
    @token_required
    @admin_required
    def get_teams_rating():
        """Рейтинг команд"""
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                query = session.query(
                    Team.id,
                    Team.name,
                    func.sum(User.points).label('total_points'),
                    func.count(User.id).label('members_count')
                ).join(
                    User, Team.id == User.team_id, isouter=True
                ).filter(
                    User.role.notin_(['admin', 'moderator'])
                ).group_by(Team.id, Team.name).having(
                    func.count(User.id) > 0
                ).order_by(func.sum(User.points).desc())
                
                result = paginate_query(query, page, limit)
                
                teams_data = []
                for team_id, team_name, total_points, members_count in result['items']:
                    teams_data.append({
                        'id': team_id,
                        'name': team_name,
                        'totalProgress': int(total_points) if total_points else 0,
                        'members': int(members_count) if members_count else 0
                    })
                
                return jsonify(format_response({
                    'leaderboard': teams_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/stats/metrics', methods=['GET'])
    @token_required
    @admin_required
    def get_stats_metrics():
        """Детальные метрики приложения"""
        try:
            from_date = parse_date_param(request.args.get('from'))
            to_date = parse_date_param(request.args.get('to'))
            interval = request.args.get('interval', 'all')  # day, week, month, all
            
            if interval != 'all' and not from_date:
                if interval == 'day':
                    from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                elif interval == 'week':
                    from_date = datetime.now() - timedelta(days=7)
                elif interval == 'month':
                    from_date = datetime.now() - timedelta(days=30)
            
            to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999) if to_date else None
            
            with get_session() as session:
                query = session.query(Feed)
                if from_date:
                    query = query.filter(Feed.time_of_publication >= from_date)
                if to_date_end:
                    query = query.filter(Feed.time_of_publication <= to_date_end)
                
                total_posts = query.count()
                total_calories = session.query(func.sum(Feed.calories)).filter(
                    Feed.time_of_publication >= from_date if from_date else True,
                    Feed.time_of_publication <= to_date_end if to_date_end else True
                ).scalar() or 0
                
                total_points = session.query(func.sum(Feed.points)).filter(
                    Feed.time_of_publication >= from_date if from_date else True,
                    Feed.time_of_publication <= to_date_end if to_date_end else True
                ).scalar() or 0
                
                active_users = session.query(func.count(func.distinct(Feed.author_id))).filter(
                    Feed.time_of_publication >= from_date if from_date else True,
                    Feed.time_of_publication <= to_date_end if to_date_end else True
                ).scalar() or 0
                
                total_users = session.query(func.count(User.id)).scalar() or 0
                total_teams = session.query(func.count(Team.id)).scalar() or 0
                
                now = datetime.utcnow()
                active_challenges = session.query(func.count(ChallengeNew.id)).filter(
                    and_(
                        ChallengeNew.status == 'active',
                        ChallengeNew.start_at <= now,
                        ChallengeNew.end_at >= now
                    )
                ).scalar() or 0
                
                activity_stats = session.query(
                    Activity.name,
                    Activity.tag,
                    func.count(Feed.id).label('count'),
                    func.sum(Feed.calories).label('total_calories'),
                    func.sum(Feed.points).label('total_points')
                ).join(
                    Feed, Activity.id == Feed.activity_id
                ).filter(
                    Feed.time_of_publication >= from_date if from_date else True,
                    Feed.time_of_publication <= to_date_end if to_date_end else True
                ).group_by(Activity.id, Activity.name, Activity.tag).all()
                
                activities_data = []
                for name, tag, count, calories, points in activity_stats:
                    activities_data.append({
                        'name': name,
                        'tag': tag,
                        'count': count,
                        'totalCalories': int(calories) if calories else 0,
                        'totalPoints': int(points) if points else 0
                    })
                
                response_data = {
                    'totalPosts': total_posts,
                    'totalCalories': int(total_calories),
                    'totalPoints': int(total_points),
                    'activeUsers': active_users,
                    'totalUsers': total_users,
                    'totalTeams': total_teams,
                    'activeChallenges': active_challenges,
                    'activities': activities_data
                }
                
                if interval != 'all':
                    timeline_data = get_timeline_stats(session, from_date, to_date, interval)
                    response_data['timeline'] = timeline_data
                
                return jsonify(format_response(response_data))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/stats/recalculate', methods=['POST'])
    @token_required
    @admin_required
    def recalculate_stats():
        """Пересчет статистики"""
        try:
            from admin_scripts.recalc_points import recalculate_user_points
            from admin_scripts.create_teams import calculate_team_points
            
            data = request.get_json() or {}
            scope = data.get('scope', 'all')  # 'participants', 'teams', 'all'
            from_date = parse_date_param(data.get('from'))
            to_date = parse_date_param(data.get('to'))
            
            with get_session() as session:
                if scope in ['participants', 'all']:
                    all_users = session.query(User.id).all()
                    for (user_id,) in all_users:
                        try:
                            recalculate_user_points(user_id)
                        except Exception as e:
                            logger.error(f"Error recalculating points for user {user_id}: {e}", exc_info=True)
                
                if scope in ['teams', 'all']:
                    all_teams = session.query(Team.id).all()
                    for (team_id,) in all_teams:
                        try:
                            calculate_team_points(team_id)
                        except Exception as e:
                            logger.error(f"Error recalculating points for team {team_id}: {e}", exc_info=True)
                
                log_audit(
                    admin_id=request.user_id,
                    action='recalculate',
                    entity_type='statistics',
                    new_value=json.dumps({
                        'scope': scope,
                        'from_date': from_date.isoformat() if from_date else None,
                        'to_date': to_date.isoformat() if to_date else None
                    })
                )
                
                return jsonify(format_response({
                    'message': f'Statistics recalculated successfully for scope: {scope}'
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/errors/<int:error_id>', methods=['GET'])
    @token_required
    @admin_required
    def get_error(error_id):
        """Получить ошибку по ID"""
        try:
            with get_session() as session:
                error = session.query(ErrorLog).filter_by(id=error_id).first()
                if not error:
                    return jsonify(format_response(None, 404, 'Error not found')), 404
                
                error_data = {
                    'id': error.id,
                    'level': error.level,
                    'service': error.service,
                    'message': error.message,
                    'stackTrace': error.stack_trace,
                    'context': json.loads(error.context) if error.context else None,
                    'status': error.status,
                    'userId': error.user_id,
                    'ipAddress': error.ip_address,
                    'createdAt': error.created_at.isoformat() if error.created_at else None
                }
                
                return jsonify(format_response(error_data))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/errors/<int:error_id>/status', methods=['PATCH'])
    @token_required
    @admin_required
    def update_error_status(error_id):
        """Изменить статус ошибки"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminErrorStatusSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                error = session.query(ErrorLog).filter_by(id=error_id).first()
                if not error:
                    return jsonify(format_response(None, 404, 'Error not found')), 404
                
                old_status = error.status
                error.status = validated_data['status']
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='status_change',
                    entity_type='error',
                    entity_id=error_id,
                    old_value=old_status,
                    new_value=error.status
                )
                
                return jsonify(format_response({'message': 'Error status updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/errors/ingest', methods=['POST'])
    @token_required
    def ingest_error():
        """Прием ошибок от клиента (доступен для всех авторизованных)"""
        try:
            data = request.get_json()
            if not data or not data.get('message'):
                return jsonify(format_response(None, 400, 'Message is required')), 400
            
            with get_session() as session:
                error = ErrorLog(
                    level=data.get('level', 'error'),
                    service=data.get('service', 'client'),
                    message=data['message'],
                    stack_trace=data.get('stackTrace'),
                    context=json.dumps(data.get('context')) if data.get('context') else None,
                    status='open',
                    user_id=request.user_id,
                    ip_address=request.remote_addr
                )
                session.add(error)
                session.commit()
                
                return jsonify(format_response({
                    'id': error.id,
                    'message': 'Error logged successfully'
                })), 201
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/leagues/recalculate', methods=['POST'])
    @token_required
    @admin_required
    def recalculate_leagues():
        """Перерасчет лиг как в admin/create_leagues.py: деление на трети по очкам.

        Алгоритм:
        - Сортируем всех пользователей по points DESC
        - Первую треть назначаем 'gold', вторую треть 'silver', остальные 'bronze'
        - Совместим по поведению с скриптом create_leagues (без исключений по ролям)
        """
        try:
            updated_counts = { 'bronze': 0, 'silver': 0, 'gold': 0 }

            with get_session() as session:
                users = session.query(User).order_by(User.points.desc().nullslast()).all()
                total = len(users)
                if total == 0:
                    return jsonify(format_response({'message': 'No users to recalculate', 'updated': updated_counts}))

                num_gold = total // 3
                num_silver = total // 3

                for idx, u in enumerate(users):
                    if idx < num_gold:
                        new_league = 'gold'
                    elif idx < num_gold + num_silver:
                        new_league = 'silver'
                    else:
                        new_league = 'bronze'

                    if u.league != new_league:
                        u.league = new_league
                        updated_counts[new_league] += 1

                session.commit()

            log_audit(
                admin_id=request.user_id,
                action='recalculate',
                entity_type='leagues',
                old_value=None,
                new_value=json.dumps({ 'strategy': 'thirds_by_points', 'updated': updated_counts })
            )

            return jsonify(format_response({
                'message': 'Leagues recalculated successfully by thirds strategy',
                'updated': updated_counts
            }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/dashboard/recent-activity', methods=['GET'])
    @token_required
    @admin_required
    def get_recent_activity():
        """Последняя активность пользователей (посты и комментарии)"""
        try:
            limit = min(int(request.args.get('limit', 3)), 3)
            with get_session() as session:
                recent_feeds = session.query(Feed, User).join(
                    User, Feed.author_id == User.id
                ).order_by(Feed.time_of_publication.desc()).limit(limit).all()

                from app.domain.models import Comment
                recent_comments = session.query(Comment, User, Feed).join(
                    User, Comment.author_id == User.id
                ).join(
                    Feed, Comment.feed_id == Feed.id
                ).order_by(Comment.created_at.desc()).limit(limit).all()

                items = []
                for feed, user in recent_feeds:
                    items.append({
                        'type': 'post',
                        'id': feed.id,
                        'userId': user.id,
                        'firstName': user.name,
                        'lastName': user.surname,
                        'activityId': feed.activity_id,
                        'points': feed.points or 0,
                        'calories': feed.calories or 0,
                        'createdAt': feed.time_of_publication.isoformat() if feed.time_of_publication else None,
                        'preview': (feed.commentactivity or '')[:120]
                    })

                for comment, user, feed in recent_comments:
                    items.append({
                        'type': 'comment',
                        'id': comment.id,
                        'userId': user.id,
                        'firstName': user.name,
                        'lastName': user.surname,
                        'postId': feed.id,
                        'createdAt': comment.created_at.isoformat() if comment.created_at else None,
                        'preview': (comment.comment_text or '')[:120]
                    })

                items.sort(key=lambda x: x.get('createdAt') or '', reverse=True)
                return jsonify(format_response({'items': items[:limit]}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/dashboard/quick-actions', methods=['GET'])
    @token_required
    @admin_required
    def get_quick_actions():
        """Быстрые действия и ключевые метрики для быстрого доступа"""
        try:
            with get_session() as session:
                total_users = session.query(func.count(User.id)).scalar() or 0
                total_posts = session.query(func.count(Feed.id)).scalar() or 0
                open_errors = session.query(func.count(ErrorLog.id)).filter(ErrorLog.status == 'open').scalar() or 0

                return jsonify(format_response({
                    'metrics': {
                        'totalUsers': total_users,
                        'totalPosts': total_posts,
                        'openErrors': int(open_errors)
                    },
                    'actions': [
                        { 'label': 'Создать пользователя', 'method': 'POST', 'path': '/admin/users' },
                        { 'label': 'Создать челлендж', 'method': 'POST', 'path': '/admin/challenges' },
                        { 'label': 'Просмотреть ошибки', 'method': 'GET', 'path': '/admin/errors' },
                        { 'label': 'Пересчитать статистику', 'method': 'POST', 'path': '/admin/stats/recalculate' }
                    ]
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/stats/export', methods=['GET'])
    @token_required
    @admin_required
    def export_stats():
        """Экспорт статистики в CSV. Поддерживаемые scope: overview, participants, teams, activities"""
        try:
            scope = request.args.get('scope', 'overview')
            export_format = request.args.get('format', 'csv')
            interval = request.args.get('interval', 'all')
            from_date = parse_date_param(request.args.get('from'))
            to_date = parse_date_param(request.args.get('to'))
            
            if interval != 'all' and not from_date:
                if interval == 'day':
                    from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                elif interval == 'week':
                    from_date = datetime.now() - timedelta(days=7)
                elif interval == 'month':
                    from_date = datetime.now() - timedelta(days=30)
            
            to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999) if to_date else None

            if export_format != 'csv':
                return jsonify(format_response(None, 400, 'Only CSV export is supported for now')), 400

            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            with get_session() as session:
                if scope == 'participants':
                    rows = session.query(
                        User.id, User.name, User.surname, User.league, User.points, Team.name
                    ).join(Team, Team.id == User.team_id, isouter=True).filter(
                        User.role.notin_(['admin', 'moderator'])
                    ).order_by(User.points.desc()).all()
                    writer.writerow(['ID', 'First name', 'Last name', 'Team', 'League', 'Points'])
                    for row in rows:
                        team_name = row[5] if row[5] else ''
                        writer.writerow([row[0], row[1], row[2], team_name, row[3], int(row[4] or 0)])
                    filename = 'participants.csv'
                elif scope == 'teams':
                    rows = session.query(
                        Team.id, Team.name, func.sum(User.points).label('points'), func.count(User.id).label('members')
                    ).join(User, Team.id == User.team_id).filter(
                        User.role.notin_(['admin', 'moderator'])
                    ).group_by(Team.id, Team.name).order_by(func.sum(User.points).desc()).all()
                    writer.writerow(['Team ID', 'Team name', 'Total points', 'Members'])
                    for row in rows:
                        writer.writerow([row[0], row[1], int(row[2] or 0), int(row[3] or 0)])
                    filename = 'teams.csv'
                elif scope == 'activities':
                    q = session.query(
                        Activity.name, Activity.tag, func.count(Feed.id).label('count'), func.sum(Feed.calories).label('calories'), func.sum(Feed.points).label('points')
                    ).join(Feed, Activity.id == Feed.activity_id)
                    if from_date:
                        q = q.filter(Feed.time_of_publication >= from_date)
                    if to_date_end:
                        q = q.filter(Feed.time_of_publication <= to_date_end)
                    rows = q.group_by(Activity.id, Activity.name, Activity.tag).all()
                    writer.writerow(['Activity', 'Tag', 'Posts count', 'Total calories', 'Total points'])
                    for row in rows:
                        writer.writerow([row[0], row[1], int(row[2] or 0), int(row[3] or 0), int(row[4] or 0)])
                    filename = 'activities.csv'
                else:
                    q = session.query(Feed)
                    if from_date:
                        q = q.filter(Feed.time_of_publication >= from_date)
                    if to_date_end:
                        q = q.filter(Feed.time_of_publication <= to_date_end)
                    total_posts = q.count()
                    
                    calories_q = session.query(func.sum(Feed.calories))
                    points_q = session.query(func.sum(Feed.points))
                    users_q = session.query(func.count(func.distinct(Feed.author_id)))
                    
                    if from_date:
                        calories_q = calories_q.filter(Feed.time_of_publication >= from_date)
                        points_q = points_q.filter(Feed.time_of_publication >= from_date)
                        users_q = users_q.filter(Feed.time_of_publication >= from_date)
                    if to_date_end:
                        calories_q = calories_q.filter(Feed.time_of_publication <= to_date_end)
                        points_q = points_q.filter(Feed.time_of_publication <= to_date_end)
                        users_q = users_q.filter(Feed.time_of_publication <= to_date_end)
                    
                    total_calories = calories_q.scalar() or 0
                    total_points = points_q.scalar() or 0
                    active_users = users_q.scalar() or 0
                    
                    now = datetime.utcnow()
                    active_challenges = session.query(func.count(ChallengeNew.id)).filter(
                        and_(
                            ChallengeNew.status == 'active',
                            ChallengeNew.start_at <= now,
                            ChallengeNew.end_at >= now
                        )
                    ).scalar() or 0

                    writer.writerow(['Metric', 'Value'])
                    writer.writerow(['Total posts', total_posts])
                    writer.writerow(['Total calories', int(total_calories)])
                    writer.writerow(['Total points', int(total_points)])
                    writer.writerow(['Active users', int(active_users)])
                    writer.writerow(['Active challenges', int(active_challenges)])
                    filename = 'overview.csv'

            csv_text = output.getvalue()
            csv_bytes = csv_text.encode('utf-8-sig')
            response = make_response(csv_bytes)
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return response
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

