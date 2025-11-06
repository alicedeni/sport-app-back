from flask import jsonify, request, send_from_directory
from flasgger import Swagger, swag_from
from admin_scripts.recalc_points import recalculate_user_points
from admin_scripts.create_teams import calculate_team_points
import datetime
from datetime import datetime, time, timedelta
import os
import pytz
from app.api.public.auth_routes import token_required
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import Activity, Feed, User, Like, Comment
from sqlalchemy import func
from app.infra.services.points_service_client import get_points_client
import logging

logger = logging.getLogger(__name__)


def init_post_routes(app):
    @app.route('/user/list_of_activities', methods=['GET'])
    @token_required
    @swag_from({
        'responses': {
            200: {
                'description': 'List of activities available for the user',
                'examples': {
                    'application/json': {
                        'status': 200,
                        'activities': [
                            {'type': 'Running', 'scorecard': 'High', 'color': '#FF0000', 'tag': 'run'}
                        ]
                    }
                }
            }
        }
    })
    def list_of_activities():
        """Get a list of activities
        This endpoint returns a list of available activities.
        ---
        parameters:
          - name: user_id
            in: path
            type: integer
            required: true
            description: ID of the user
        responses:
          200:
            description: List of activities
        """

        with get_session() as session:
            rows = session.query(Activity.name, Activity.scorecard, Activity.color, Activity.tag).order_by(Activity.id.asc()).all()

        activities_data = []
        for r in rows:
            activities_data.append({
                'type': r[0],
                'scorecard': r[1],
                'color': r[2],
                'tag': r[3]
            })

        return jsonify({'status': 200, 'activities': activities_data})

    @app.route('/uploads/<filename>', methods=['GET'])
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route('/uploads', methods=['POST'])
    @swag_from({
        'responses': {
            200: {
                'description': 'Image successfully uploaded',
                'examples': {
                    'application/json': {
                        'imageUrl': '/path/to/uploaded/image'
                    }
                }
            },
            400: {
                'description': 'Bad request - image file not provided or empty'
            },
            500: {
                'description': 'Server error - upload failed'
            }
        }
    })

    def upload_image():
        """Upload an image file"""

        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        image = request.files['image']
        if image.filename == '':
            return jsonify({'error': 'No selected image'}), 400

        if image:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
            image.save(filename)

            logger.info(f"Image saved successfully: {filename}")

            return jsonify({'imageUrl': filename}), 200

        return jsonify({'error': 'Upload failed'}), 500

    @app.route('/user/activities', methods=['POST'])
    @token_required
    def create_post():
        user_id = request.user_id
        data = request.get_json()

        try:
            activity_data = validate_activity_data(data)
        except ValueError as e:
            return jsonify({'status': 400, 'message': str(e)})

        try:
            points_client = get_points_client()
            metrics = points_client.calculate_activity_metrics(
                activity_tag=activity_data['type'],
                activity_input_data=activity_data,
                user_id=user_id
            )
            
            save_activity(
                user_id=user_id,
                activity_data=activity_data,
                activity_id=metrics['activity_id'],
                distance=metrics['distance'],
                calories_burned=metrics['calories_burned'],
                activity_points=metrics['activity_points'],
                duration_hours=metrics['duration_hours']
            )
            
            return jsonify({'status': 200, 'message': 'Post created successfully'})
        except ValueError as e:
            logger.warning(f"Validation error creating post: {e}")
            return jsonify({'status': 400, 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error creating post: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    def validate_activity_data(data):
        """Валидация и нормализация данных активности"""
        required_fields = ['startTime', 'type', 'startDate']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            raise ValueError(f'Missing required fields: {", ".join(missing_fields)}')

        return {
            'startTime': data['startTime'],
            'duration': data.get('duration'),  
            'type': data['type'],
            'startDate': data['startDate'],
            'steps': data.get('step', 0) or data.get('steps', 0),  
            'description': data.get('description'),
            'verification': data.get('verification'),
            'image': data.get('image'),
            'other': data.get('other'),
            'distance': data.get('distance'),
            'time_of_publication': datetime.utcnow(),
        }

    def save_activity(user_id, activity_data, activity_id, distance, calories_burned, activity_points, duration_hours):
        """Сохранение активности в базу данных"""
        time_beginning_obj = datetime.strptime(activity_data['startTime'], '%H:%M').time()
        
        if duration_hours is not None:
            hours = int(duration_hours)
            minutes = int((duration_hours - hours) * 60)
            duration_formatted = f"{hours:02}:{minutes:02}"
            time_ending_obj = (datetime.combine(datetime.min, time_beginning_obj) + timedelta(hours=hours, minutes=minutes)).time()
        else:
            duration_formatted = '00:00'
            time_ending_obj = time_beginning_obj

        if activity_id == 2 and distance:
            distance = round(distance * 1000, 2)

        with get_session() as session:
            feed = Feed(
                author_id=user_id,
                status=False,
                distance=distance,
                activity_id=activity_id,
                time_of_publication=activity_data['time_of_publication'],
                commentactivity=activity_data['description'],
                duration=duration_formatted,
                time_beginning=activity_data['startTime'],
                proof=activity_data['verification'],
                image=activity_data['image'],
                steps=activity_data['steps'],
                activity_date=activity_data['startDate'],
                other_activity=activity_data['other'],
                time_ending=time_ending_obj,
                calories=int(round(calories_burned)) if calories_burned else 0,
                points=activity_points or 0
            )
            session.add(feed)
            if activity_points:
                session.query(User).filter(User.id == user_id).update({User.points: (User.points + activity_points)})
            session.commit()
            
            try:
                from app.services.challenges_service import get_challenges_service
                challenges_service = get_challenges_service()
                challenges_service.update_challenge_progress(user_id, feed)
            except Exception as e:
                logger.error(f"Failed to update challenges progress: {e}", exc_info=True)

    @app.route('/user/preview_post', methods=['POST'])
    @token_required
    def preview_post():
        """Предпросмотр поста без сохранения"""
        user_id = request.user_id
        data = request.get_json()

        try:
            activity_data = validate_activity_data(data)
        except ValueError as e:
            return jsonify({'status': 400, 'message': str(e)}), 400

        try:
            points_client = get_points_client()
            metrics = points_client.calculate_activity_metrics(
                activity_tag=activity_data['type'],
                activity_input_data=activity_data,
                user_id=user_id
            )
            
            distance = metrics['distance']
            if metrics['activity_id'] == 2 and distance:
                distance = round(distance * 1000, 2)
            
            preview_data = {
                'distance': distance,
                'duration_hours': metrics['duration_formatted'],
                'calories_burned': round(metrics['calories_burned']),
                'activity_points': metrics['activity_points'],
                'activity_data': activity_data
            }

            return jsonify({'status': 200, 'preview_data': preview_data})
        except ValueError as e:
            logger.warning(f"Validation error in preview: {e}")
            return jsonify({'status': 400, 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Error in preview_post: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'}), 500

    @app.route('/user/posts', methods=['GET'])
    @token_required
    @swag_from({ 'responses': { 200: {'description': 'List of posts'}, 500: {'description': 'Internal server error'} } })
    def posts():
        user_id = request.user_id
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 20))
        activity_filter = request.args.get('activity')
        username_filter = request.args.get('username')
        my_posts_only = request.args.get('my_posts')
        try:
            with get_session() as session:
                like_count_sq = session.query(func.count(Like.id)).filter(Like.feed_id == Feed.id).correlate(Feed).scalar_subquery()
                is_liked_sq = session.query(func.count(Like.id)).filter(Like.feed_id == Feed.id, Like.user_id == user_id).correlate(Feed).scalar_subquery()
                comment_count_sq = session.query(func.count(Comment.id)).filter(Comment.feed_id == Feed.id).correlate(Feed).scalar_subquery()
                q = session.query(
                    User.id, User.surname, User.name, User.points, User.avatar,
                    Feed.time_of_publication, Feed.image,
                    Activity.name.label('type_name'), Activity.scorecard, Activity.color, Activity.tag,
                    Feed.time_beginning, Feed.duration, Feed.distance, Feed.calories,
                    Feed.commentactivity, Feed.id.label('feed_id'),
                    like_count_sq, is_liked_sq, comment_count_sq,
                    Feed.steps, Feed.other_activity, Feed.points, Feed.activity_date
                ).join(Feed, Feed.author_id == User.id).join(Activity, Activity.id == Feed.activity_id)
                if my_posts_only and my_posts_only.lower() == 'true':
                    q = q.filter(Feed.author_id == user_id)
                if activity_filter:
                    q = q.filter(Activity.tag == activity_filter)
                if username_filter:
                    like_pattern = f"%{username_filter}%"
                    q = q.filter((User.surname.ilike(like_pattern)) | (User.name.ilike(like_pattern)))
                rows = q.order_by(Feed.time_of_publication.desc()).limit(limit).offset(offset).all()
            formatted_posts = []
            for post in rows:
                duration = post[12]
                hours, minutes = map(int, duration.split(':')) if duration else (0, 0)
                formatted_duration = f"{hours:02}:{minutes:02}"
                timestamp_str = post[5].isoformat() + 'Z' if post[5] else None
                activity_type = post[21] if post[10] == 'other' and post[21] is not None else post[7]
                formatted_post = {
                    'id': post[0], 'username': post[1], 'name': post[2], 'fireCount': post[3], 'miniAvatar': post[4],
                    'timestamp': timestamp_str, 'image': post[6], 'type': activity_type, 'scorecard': post[8],
                    'color': post[9], 'tag': post[10], 'time': formatted_duration, 'distance': post[13], 'calories': post[14],
                    'text': post[15], 'feed_id': post[16], 'likeCount': int(post[17] or 0), 'isLiked': (post[18] or 0) > 0,
                    'commentCount': int(post[19] or 0), 'postfireCount': post[22], 'activityDate': post[23].strftime('%Y-%m-%d') if post[23] else None,
                    'timeBeginning': post[11].strftime('%H:%M') if post[11] else None
                }
                if (post[20] or 0) > 0:
                    formatted_post['step'] = post[20]
                formatted_posts.append(formatted_post)
            formatted_posts = sorted(formatted_posts, key=lambda x: x['timestamp'], reverse=True)
            return jsonify({'status': 200, 'posts': formatted_posts})
        except Exception as e:
            logger.error(f"Error listing posts: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/user/edit_post/<int:post_id>', methods=['PUT'])
    @token_required
    def edit_post(post_id):
        user_id = request.user_id
        try:
            data = request.get_json()
            with get_session() as session:
                post = session.query(Feed).filter(Feed.id == post_id).first()
                if not post:
                    return jsonify({'status': 404, 'message': 'Post not found'})
                if post.author_id != user_id:
                    return jsonify({'status': 403, 'message': 'Forbidden: You can only edit your own posts'})

                post.status = True
                post.activity_id = data['type']
                post.commentactivity = data['description']
                post.proof = data['verification']
                post.calories = data['calories']
                post.time_beginning = data['startTime']
                post.time_ending = data['endTime']
                post.image = data['image']
                session.commit()

                recalculate_user_points(user_id)
                team_id = session.query(User.team_id).filter(User.id == user_id).scalar()
                calculate_team_points(team_id)

                return jsonify({'status': 200, 'message': 'Post updated successfully'})
        except Exception as e:
            logger.error(f"Error editing post: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/user/delete_post/<int:post_id>', methods=['DELETE'])
    @token_required
    def delete_post(post_id):
        user_id = request.user_id
        try:
            with get_session() as session:
                post = session.query(Feed).filter(Feed.id == post_id).first()
                if not post:
                    return jsonify({'status': 404, 'message': 'Post not found'})
                if post.author_id != user_id:
                    return jsonify({'status': 403, 'message': 'Forbidden: You can only delete your own posts'})
                points_to_subtract = int(post.points or 0)
                if points_to_subtract > 0:
                    session.query(User).filter(User.id == user_id).update({
                        User.points: func.greatest(User.points - points_to_subtract, 0)
                    })
                session.delete(post)
                session.commit()
                return jsonify({'status': 200, 'message': 'Post deleted successfully'})
        except Exception as e:
            logger.error(f"Error deleting post: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

