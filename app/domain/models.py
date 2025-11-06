from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, Time, ForeignKey, UniqueConstraint, Float, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from app.infra.db.sqlalchemy_db import Base
from datetime import datetime


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    surname = Column(String(25))
    name = Column(String(25))
    midname = Column(String(25))
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    age = Column(Integer)
    gender = Column(String(25))
    height = Column(Integer)
    weight = Column(Integer)
    points = Column(Integer, default=0)
    team_id = Column(Integer, ForeignKey('teams.id'))
    avatar = Column(String(255))
    f_hello = Column(Boolean, default=False)
    league = Column(Text, default='silver')
    show_welcome = Column(Boolean, default=True)
    
    role = Column(String(20), default='user')  # 'user', 'moderator', 'admin'
    is_active = Column(Boolean, default=True)
    banned_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    team = relationship('Team', back_populates='users')


class Team(Base):
    __tablename__ = 'teams'

    id = Column(Integer, primary_key=True)
    name = Column(String(30))
    points = Column(Integer)

    users = relationship('User', back_populates='team')


class Activity(Base):
    __tablename__ = 'activities'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    scorecard = Column(String)
    proportion_points = Column(Integer)
    color = Column(String(30))
    tag = Column(String(30))
    met = Column(Float)
    avg_speed = Column(Float)
    low_speed = Column(Float)
    high_speed = Column(Float)


class Feed(Base):
    __tablename__ = 'feeds'

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    time_of_publication = Column(DateTime, default=datetime.utcnow)
    status = Column(Boolean, default=False)
    distance = Column(String(30))
    activity_id = Column(Integer, ForeignKey('activities.id'))
    commentactivity = Column(String(500))
    proof = Column(Text)
    calories = Column(Integer)
    time_beginning = Column(Time)
    duration = Column(Text, default='00:00')
    image = Column(Text)
    steps = Column(Integer)
    activity_date = Column(Date)
    other_activity = Column(String)
    time_ending = Column(Time)
    points = Column(Integer)


class Like(Base):
    __tablename__ = 'likes'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    feed_id = Column(Integer, ForeignKey('feeds.id'))
    UniqueConstraint('user_id', 'feed_id', name='likes_user_feed_unique')


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey('users.id'))
    feed_id = Column(Integer, ForeignKey('feeds.id'))
    comment_text = Column(String(250))
    created_at = Column(DateTime, default=datetime.utcnow)


class CommentLike(Base):
    __tablename__ = 'comment_likes'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    comment_id = Column(Integer, ForeignKey('comments.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    UniqueConstraint('user_id', 'comment_id', name='comment_likes_user_comment_unique')


class TokenBlacklist(Base):
    __tablename__ = 'token_blacklist'

    id = Column(Integer, primary_key=True)
    token = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserProgress(Base):
    __tablename__ = 'user_progress'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    target_weight = Column(Integer)
    start_weight = Column(Integer)


class PasswordReset(Base):
    __tablename__ = 'password_resets'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = Column(Text, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    action = Column(String(50), nullable=False) 
    entity_type = Column(String(50), nullable=False)  
    entity_id = Column(Integer, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AppSettings(Base):
    __tablename__ = 'app_settings'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)


class FeatureFlag(Base):
    __tablename__ = 'feature_flags'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    enabled = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)


class ErrorLog(Base):
    __tablename__ = 'error_logs'
    
    id = Column(Integer, primary_key=True)
    level = Column(String(20), nullable=False) 
    service = Column(String(50), nullable=True)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    context = Column(Text, nullable=True) 
    status = Column(String(20), default='open')
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SystemLog(Base):
    __tablename__ = 'system_logs'
    
    id = Column(Integer, primary_key=True)
    level = Column(String(20), nullable=False) 
    context = Column(String(100), nullable=True) 
    message = Column(Text, nullable=False)
    meta_data = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey('challenges.id'), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default='draft') 
    points = Column(Integer, default=0)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChallengeNew(Base):
    """Модель челленджа (схема challenges)"""
    __tablename__ = 'challenges'
    __table_args__ = (
        CheckConstraint("challenge_type IN ('team', 'individual')", name='check_challenge_type'),
        CheckConstraint("league IN ('bronze', 'silver', 'gold') OR league IS NULL", name='check_league'),
        CheckConstraint("metric_type IN ('distance', 'calories', 'points', 'steps', 'duration')", name='check_metric_type'),
        CheckConstraint("target_value > 0", name='check_target_value'),
        CheckConstraint("verification_mode IN ('auto', 'manual', 'hybrid')", name='check_verification_mode'),
        CheckConstraint("reward_points >= 0", name='check_reward_points'),
        CheckConstraint("status IN ('draft', 'active', 'completed', 'archived')", name='check_status'),
        CheckConstraint("end_at > start_at", name='check_dates'),
        Index('idx_challenges_status', 'status'),
        Index('idx_challenges_dates', 'start_at', 'end_at'),
        Index('idx_challenges_type', 'challenge_type'),
        Index('idx_challenges_league', 'league'),
        {'schema': 'challenges'}
    )
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    challenge_type = Column(String(20), nullable=False)
    league = Column(String(20))
    metric_type = Column(String(50), nullable=False)
    target_value = Column(Float, nullable=False)
    verification_mode = Column(String(20), nullable=False, default='auto')
    activity_types = Column(ARRAY(String))
    reward_points = Column(Integer, default=0)
    reward_badge = Column(String(100))
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    status = Column(String(20), default='draft')
    cover_image = Column(String(255))
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChallengeParticipantNew(Base):
    """Модель участника челленджа (схема challenges)"""
    __tablename__ = 'challenge_participants'
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND team_id IS NULL) OR (user_id IS NULL AND team_id IS NOT NULL)",
            name='check_participant'
        ),
        CheckConstraint("current_value >= 0", name='check_current_value'),
        Index('idx_participants_challenge', 'challenge_id'),
        Index('idx_participants_user', 'user_id'),
        Index('idx_participants_team', 'team_id'),
        Index('idx_participants_completed', 'completed'),
        UniqueConstraint('challenge_id', 'user_id', name='uq_challenge_user'),
        UniqueConstraint('challenge_id', 'team_id', name='uq_challenge_team'),
        {'schema': 'challenges'}
    )
    
    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey('challenges.challenges.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer)
    team_id = Column(Integer)
    current_value = Column(Float, default=0)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_activity_at = Column(DateTime)
