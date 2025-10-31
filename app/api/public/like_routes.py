from flask import jsonify, request
import logging
from app.api.public.auth_routes import token_required
from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import Like, Comment, CommentLike
from sqlalchemy import func

logger = logging.getLogger(__name__)


def init_like_routes(app):
    @app.route('/user/like', methods=['POST'])
    @token_required
    def like_post():
        user_id = request.user_id
        data = request.get_json()
        feed_id = data.get('post_id')
        if not feed_id:
            return jsonify({'status': 400, 'message': 'post id is required'})
        try:
            with get_session() as session:
                exists = session.query(Like.id).filter(Like.user_id == user_id, Like.feed_id == feed_id).first()
                if exists:
                    return jsonify({'status': 400, 'message': 'User has already liked this feed'})
                session.add(Like(user_id=user_id, feed_id=feed_id))
                session.commit()
                like_count = session.query(func.count(Like.id)).filter(Like.feed_id == feed_id).scalar() or 0
                return jsonify({'status': 200, 'message': 'Feed liked successfully', 'likeCount': like_count})
        except Exception as e:
            logger.error(f"Error liking feed: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/user/unlike', methods=['POST'])
    @token_required
    def unlike_post():
        user_id = request.user_id
        data = request.get_json()
        feed_id = data.get('post_id')
        if not feed_id:
            return jsonify({'status': 400, 'message': 'post id is required'})
        try:
            with get_session() as session:
                like_row = session.query(Like).filter(Like.user_id == user_id, Like.feed_id == feed_id).first()
                if not like_row:
                    return jsonify({'status': 400, 'message': 'Like not found'})
                session.delete(like_row)
                session.commit()
                like_count = session.query(func.count(Like.id)).filter(Like.feed_id == feed_id).scalar() or 0
                return jsonify({'status': 200, 'message': 'Feed unliked successfully', 'likeCount': like_count})
        except Exception as e:
            logger.error(f"Error unliking feed: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/post/like_count/<int:post_id>', methods=['GET'])
    def get_like_count(post_id):
        try:
            with get_session() as session:
                like_count = session.query(func.count(Like.id)).filter(Like.feed_id == post_id).scalar() or 0
                return jsonify({'status': 200, 'likeCount': like_count})
        except Exception as e:
            logger.error(f"Error fetching like count: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/user/comment/<int:comment_id>/like', methods=['POST'])
    @token_required
    def like_comment(comment_id):
        user_id = request.user_id
        try:
            with get_session() as session:
                comment_exists = session.query(Comment.id).filter(Comment.id == comment_id).first()
                if not comment_exists:
                    return jsonify({'status': 404, 'message': 'Comment not found'})
                exists = session.query(CommentLike.id).filter(CommentLike.user_id == user_id, CommentLike.comment_id == comment_id).first()
                if not exists:
                    session.add(CommentLike(user_id=user_id, comment_id=comment_id))
                    session.commit()
                return jsonify({'status': 200, 'message': 'Comment liked successfully'})
        except Exception as e:
            logger.error(f"Error liking comment: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})

    @app.route('/user/comment/<int:comment_id>/unlike', methods=['POST'])
    @token_required
    def unlike_comment(comment_id):
        user_id = request.user_id
        try:
            with get_session() as session:
                row = session.query(CommentLike).filter(CommentLike.user_id == user_id, CommentLike.comment_id == comment_id).first()
                if row:
                    session.delete(row)
                    session.commit()
                return jsonify({'status': 200, 'message': 'Comment unliked successfully'})
        except Exception as e:
            logger.error(f"Error unliking comment: {e}", exc_info=True)
            return jsonify({'status': 500, 'message': 'Internal server error'})
