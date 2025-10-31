from flask import request, jsonify
from datetime import datetime, time
import logging
from app.api.public.auth_routes import token_required
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import Comment, Like, CommentLike, User
from sqlalchemy import func, case

logger = logging.getLogger(__name__)


def init_comment_routes(app):
    @app.route('/user/comment', methods=['POST'])
    @token_required
    def comment_post():
        user_id = request.user_id
        data = request.get_json()
        feed_id = data.get('post_id')
        comment_text = data.get("comment_text")
        time_of_publication = datetime.now()

        if not feed_id:
            return jsonify({'status': 400, 'message': 'post id is required'})
        if not comment_text:
            return jsonify({'status': 400, 'message': 'comment text is required'})

        try:
            with get_session() as session:
                session.add(Comment(author_id=user_id, feed_id=feed_id, comment_text=comment_text, created_at=time_of_publication))
                session.commit()
                comment_count = session.query(func.count(Comment.id)).filter(Comment.feed_id == feed_id).scalar() or 0
                return jsonify({'status': 200, 'message': 'Feed commented successfully', 'commentCount': comment_count})
        except Exception as e:
            logger.error(f"Error commenting feed: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/get_comments/<int:feed_id>', methods=['GET'])
    @token_required
    def get_comments(feed_id):
        current_user_id = request.user_id
        try:
            with get_session() as session:
                subquery_likes = session.query(
                    CommentLike.comment_id,
                    func.count(CommentLike.id).label('like_count'),
                    func.max(case((CommentLike.user_id == current_user_id, 1), else_=0)).label('user_liked')
                ).group_by(CommentLike.comment_id).subquery()

                rows = session.query(
                    User.surname, User.name,
                    Comment.id.label('comment_id'), Comment.author_id, Comment.comment_text, Comment.created_at,
                    func.coalesce(subquery_likes.c.user_liked, 0).label('is_liked'),
                    func.coalesce(subquery_likes.c.like_count, 0).label('like_count')
                ).join(User, User.id == Comment.author_id).outerjoin(subquery_likes, subquery_likes.c.comment_id == Comment.id).filter(Comment.feed_id == feed_id).order_by(Comment.created_at.asc(), Comment.id.asc()).all()

            comments_list = []
            for c in rows:
                comments_list.append({
                    'surname': c[0],
                    'name': c[1],
                    'comment_id': c[2],
                    'author_id': c[3],
                    'text': c[4],
                    'created_at': c[5],
                    'is_current_user': c[3] == current_user_id,
                    'is_liked': bool(c[6]),
                    'likeCountComment': int(c[7] or 0)
                })
            return jsonify({'status': 200, 'comments': comments_list})
        except Exception as e:
            logger.error(f"Error fetching comments: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/user/delete_comment/<int:comment_id>', methods=['DELETE'])
    @token_required
    def delete_comment(comment_id):
        user_id = request.user_id
        try:
            with get_session() as session:
                comment = session.query(Comment).filter(Comment.id == comment_id).first()
                if not comment:
                    return jsonify({'status': 404, 'message': 'Comment not found'})
                if comment.author_id != user_id:
                    return jsonify({'status': 403, 'message': 'You can only delete your own comments'})
                feed_id = comment.feed_id
                session.query(CommentLike).filter(CommentLike.comment_id == comment_id).delete()
                session.delete(comment)
                session.commit()
                comment_count = session.query(func.count(Comment.id)).filter(Comment.feed_id == feed_id).scalar() or 0
                return jsonify({'status': 200, 'message': 'Comment deleted successfully', 'commentCount': comment_count})
        except Exception as e:
            logger.error(f"Error deleting comment: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/post/comment_count/<int:post_id>', methods=['GET'])
    def get_comment_count(post_id):
        try:
            with get_session() as session:
                comment_count = session.query(func.count(Comment.id)).filter(Comment.feed_id == post_id).scalar() or 0
                return jsonify({'status': 200, 'commentCount': comment_count})
        except Exception as e:
            logger.error(f"Error fetching comment count: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})
