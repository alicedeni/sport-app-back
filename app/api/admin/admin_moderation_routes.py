from flask import jsonify, request
from app.infra.db.sqlalchemy_db import get_session
from sqlalchemy import func, or_
from app.domain.models import Feed, Comment, User, Like, CommentLike, Activity
from app.api.public.auth_routes import token_required
from app.api.admin.admin_middleware import admin_required, moderator_required, log_audit
from app.domain.schemas import AdminPostStatusSchema, AdminPostEditSchema, AdminCommentStatusSchema, validate_json_data
from app.infra.utils.admin_utils import paginate_query, format_response, parse_date_param
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def init_admin_moderation_routes(app):
    @app.route('/admin/posts', methods=['GET'])
    @token_required
    @moderator_required
    def get_posts():
        """Получить список постов с фильтрацией"""
        try:
            status = request.args.get('status', '') 
            author_id = request.args.get('author_id', '')
            activity_id = request.args.get('activity_id', '')
            from_date = parse_date_param(request.args.get('from'))
            to_date = parse_date_param(request.args.get('to'))
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                query = session.query(Feed, User, Activity).join(
                    User, Feed.author_id == User.id
                ).join(
                    Activity, Feed.activity_id == Activity.id, isouter=True
                )
                
                if status == 'hidden':
                    query = query.filter(Feed.status == True)
                elif status == 'visible':
                    query = query.filter(Feed.status == False)
                
                if author_id:
                    query = query.filter(Feed.author_id == int(author_id))
                if activity_id:
                    query = query.filter(Feed.activity_id == int(activity_id))
                if from_date:
                    query = query.filter(Feed.time_of_publication >= from_date)
                if to_date:
                    to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                    query = query.filter(Feed.time_of_publication <= to_date_end)
                
                result = paginate_query(
                    query.order_by(Feed.time_of_publication.desc()),
                    page,
                    limit
                )
                
                posts_data = []
                for feed, user, activity in result['items']:
                    like_count = session.query(func.count(Like.id)).filter(
                        Like.feed_id == feed.id
                    ).scalar() or 0
                    
                    comment_count = session.query(func.count(Comment.id)).filter(
                        Comment.feed_id == feed.id
                    ).scalar() or 0
                    
                    posts_data.append({
                        'id': feed.id,
                        'authorId': feed.author_id,
                        'authorName': user.name,
                        'authorSurname': user.surname,
                        'authorEmail': user.email,
                        'status': 'hidden' if feed.status else 'visible',
                        'activityName': activity.name if activity else None,
                        'activityTag': activity.tag if activity else None,
                        'distance': feed.distance,
                        'calories': feed.calories,
                        'points': feed.points,
                        'duration': feed.duration,
                        'description': feed.commentactivity,
                        'image': feed.image,
                        'timeOfPublication': feed.time_of_publication.isoformat() if feed.time_of_publication else None,
                        'activityDate': feed.activity_date.isoformat() if feed.activity_date else None,
                        'likeCount': like_count,
                        'commentCount': comment_count
                    })
                
                return jsonify(format_response({
                    'posts': posts_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/posts/<int:post_id>', methods=['PUT'])
    @token_required
    @moderator_required
    def admin_edit_post(post_id):
        """Редактировать пост (характеристики и баллы)"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminPostEditSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                post = session.query(Feed).filter_by(id=post_id).first()
                if not post:
                    return jsonify(format_response(None, 404, 'Post not found')), 404
                
                old_values = {
                    'activity_id': post.activity_id,
                    'distance': post.distance,
                    'duration': post.duration,
                    'calories': post.calories,
                    'points': post.points,
                    'steps': post.steps,
                    'description': post.commentactivity,
                    'status': 'hidden' if post.status else 'visible'
                }
                old_points = int(post.points or 0)
                author_id = post.author_id
                
                if 'activity_id' in validated_data:
                    post.activity_id = validated_data['activity_id']
                
                if 'distance' in validated_data:
                    post.distance = str(validated_data['distance'])
                
                if 'duration' in validated_data:
                    post.duration = validated_data['duration']
                
                if 'steps' in validated_data:
                    post.steps = validated_data['steps']
                
                if 'calories' in validated_data:
                    post.calories = validated_data['calories']
                
                if 'points' in validated_data:
                    post.points = validated_data['points']
                
                if 'description' in validated_data:
                    post.commentactivity = validated_data['description']
                
                if 'status' in validated_data:
                    post.status = validated_data['status'] == 'hidden'
                
                session.commit()
                
                new_points = int(post.points or 0)
                if author_id:
                    from admin_scripts.recalc_points import recalculate_user_points
                    try:
                        recalculate_user_points(author_id)
                        
                        user = session.query(User).filter(User.id == author_id).first()
                        if user and user.team_id:
                            from admin_scripts.create_teams import calculate_team_points
                            calculate_team_points(user.team_id)
                    except Exception as e:
                        logger.error(f"Error recalculating points after post edit: {e}", exc_info=True)
                
                import json
                log_audit(
                    admin_id=request.user_id,
                    action='update',
                    entity_type='post',
                    entity_id=post_id,
                    old_value=json.dumps(old_values, ensure_ascii=False),
                    new_value=json.dumps(validated_data, ensure_ascii=False),
                    user_id=author_id
                )
                
                return jsonify(format_response({
                    'message': 'Post updated successfully',
                    'post_id': post_id,
                    'points_recalculated': old_points != new_points
                }))
        except Exception as e:
            logger.error(f"Error editing post {post_id}: {e}", exc_info=True)
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/posts/<int:post_id>/status', methods=['PATCH'])
    @token_required
    @moderator_required
    def update_post_status(post_id):
        """Изменить статус поста (visible/hidden/deleted)"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminPostStatusSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                post = session.query(Feed).filter_by(id=post_id).first()
                if not post:
                    return jsonify(format_response(None, 404, 'Post not found')), 404
                
                old_status = 'hidden' if post.status else 'visible'
                new_status = validated_data['status']
                
                if new_status == 'visible':
                    post.status = False
                elif new_status == 'hidden':
                    post.status = True
                
                session.commit()
                
                log_audit(
                    admin_id=request.user_id,
                    action='status_change',
                    entity_type='post',
                    entity_id=post_id,
                    old_value=old_status,
                    new_value=new_status
                )
                
                return jsonify(format_response({'message': 'Post status updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/posts/<int:post_id>', methods=['DELETE'])
    @token_required
    @admin_required 
    def admin_delete_post(post_id):
        """Удалить пост"""
        try:
            with get_session() as session:
                post = session.query(Feed).filter_by(id=post_id).first()
                if not post:
                    return jsonify(format_response(None, 404, 'Post not found')), 404
                
                log_audit(
                    admin_id=request.user_id,
                    action='delete',
                    entity_type='post',
                    entity_id=post_id,
                    old_value=json.dumps({
                        'author_id': post.author_id,
                        'description': post.commentactivity[:100] if post.commentactivity else None
                    })
                )
                
                points_to_subtract = int(post.points or 0)
                if points_to_subtract > 0 and post.author_id:
                    session.query(User).filter(User.id == post.author_id).update({
                        User.points: func.greatest(User.points - points_to_subtract, 0)
                    })

                session.delete(post)
                session.commit()
                
                return jsonify(format_response({'message': 'Post deleted successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    
    @app.route('/admin/comments', methods=['GET'])
    @token_required
    @moderator_required
    def admin_get_comments():
        """Получить список комментариев с фильтрацией"""
        try:
            post_id = request.args.get('post_id', '')
            author_id = request.args.get('author_id', '')
            from_date = parse_date_param(request.args.get('from'))
            to_date = parse_date_param(request.args.get('to'))
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            
            with get_session() as session:
                query = session.query(Comment, User, Feed).join(
                    User, Comment.author_id == User.id
                ).join(
                    Feed, Comment.feed_id == Feed.id
                )
                
                if post_id:
                    query = query.filter(Comment.feed_id == int(post_id))
                if author_id:
                    query = query.filter(Comment.author_id == int(author_id))
                if from_date:
                    query = query.filter(Comment.created_at >= from_date)
                if to_date:
                    to_date_end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                    query = query.filter(Comment.created_at <= to_date_end)
                
                result = paginate_query(
                    query.order_by(Comment.created_at.desc()),
                    page,
                    limit
                )
                
                comments_data = []
                for comment, user, feed in result['items']:
                    like_count = session.query(func.count(CommentLike.id)).filter(
                        CommentLike.comment_id == comment.id
                    ).scalar() or 0
                    
                    comments_data.append({
                        'id': comment.id,
                        'authorId': comment.author_id,
                        'authorName': user.name,
                        'authorSurname': user.surname,
                        'authorEmail': user.email,
                        'postId': comment.feed_id,
                        'text': comment.comment_text,
                        'likeCount': like_count,
                        'createdAt': comment.created_at.isoformat() if comment.created_at else None
                    })
                
                return jsonify(format_response({
                    'comments': comments_data,
                    'pagination': {
                        'total': result['total'],
                        'page': result['page'],
                        'limit': result['limit'],
                        'pages': result['pages']
                    }
                }))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/comments/<int:comment_id>/status', methods=['PATCH'])
    @token_required
    @moderator_required
    def update_comment_status(comment_id):
        """Изменить статус комментария"""
        try:
            data = request.get_json()
            validated_data, errors = validate_json_data(AdminCommentStatusSchema, data)
            if errors:
                return jsonify(format_response(None, 400, errors)), 400
            
            with get_session() as session:
                comment = session.query(Comment).filter_by(id=comment_id).first()
                if not comment:
                    return jsonify(format_response(None, 404, 'Comment not found')), 404
                
                new_status = validated_data['status']
                
                log_audit(
                    admin_id=request.user_id,
                    action='status_change',
                    entity_type='comment',
                    entity_id=comment_id,
                    old_value='visible',
                    new_value=new_status
                )
                
                return jsonify(format_response({'message': 'Comment status updated successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

    @app.route('/admin/comments/<int:comment_id>', methods=['DELETE'])
    @token_required
    @admin_required 
    def admin_delete_comment(comment_id):
        """Удалить комментарий"""
        try:
            with get_session() as session:
                comment = session.query(Comment).filter_by(id=comment_id).first()
                if not comment:
                    return jsonify(format_response(None, 404, 'Comment not found')), 404
                
                log_audit(
                    admin_id=request.user_id,
                    action='delete',
                    entity_type='comment',
                    entity_id=comment_id,
                    old_value=json.dumps({
                        'author_id': comment.author_id,
                        'text': comment.comment_text[:100] if comment.comment_text else None
                    })
                )
                
                session.delete(comment)
                session.commit()
                
                return jsonify(format_response({'message': 'Comment deleted successfully'}))
        except Exception as e:
            return jsonify(format_response(None, 500, str(e))), 500

