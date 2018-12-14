from datetime import datetime, timedelta

from sqlalchemy import Column, BigInteger, Text, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Model = declarative_base()


class PermissionsLevels:
    USER = 1
    ADMIN = 10


class User(Model):
    __tablename__ = "users"

    id = Column("id", BigInteger, primary_key=True)
    permissions = Column("permissions", BigInteger)
    keys_get = Column('keys_get', Integer, default=0)
    count = Column('count', Integer,  default=0)
    channel_key = Column('channel_key', Boolean, default=True)
    last_bonus = Column("last_bonus", DateTime, default=datetime.utcnow() - timedelta(days=365))
    blocked = Column("blocked", Boolean, default=False)
    last_activity = Column("last_activity", DateTime)
    sub_keys = Column("sub_keys", Integer, default=0)
    keys_away = Column("keys_away", Integer, default=0)

    chat_state = relationship("ChatState", uselist=False, back_populates="user")


class Keys(Model):
    __tablename__ = 'keys'

    id = Column('id', BigInteger, primary_key=True, autoincrement=True)
    key = Column('key', Text)


class AdLink(Model):
    __tablename__ = "ad_links"

    id = Column("id", BigInteger, primary_key=True, autoincrement=True)
    uuid = Column("uuid", Text, unique=True)
    keyword = Column("keyword", Text)
    clicks = Column("clicks", BigInteger, nullable=False, default=0)
    users_count = Column("users_count", BigInteger, nullable=False, default=0)


class ReferralLink(Model):
    __tablename__ = "referral_links"

    user_id = Column("user_id", BigInteger, primary_key=True)
    invited_by_id = Column(BigInteger, ForeignKey("users.id"))

    invited_by = relationship("User")


class Post(Model):
    __tablename__ = "posts"

    id = Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    draft = Column("draft", Boolean)
    time_to_publish = Column("time_to_publish", DateTime)
    data = Column("data", Text)
    reply_markup_data = Column("reply_markup_data", Text)


class ChannelToSubscribe(Model):
    __tablename__ = "channels_to_subscribe"

    id = Column("id", BigInteger, primary_key=True)
    enabled = Column("enabled", Boolean, default=True, server_default="1", nullable=False)

    user_assoc = relationship("Subscription")


class ChatState(Model):
    __tablename__ = "chats_states"

    id = Column("id", BigInteger, primary_key=True)
    node = Column("node", BigInteger)
    data = Column("data", Text)

    user_id = Column(BigInteger, ForeignKey("users.id"))
    user = relationship("User", back_populates="chat_state")


class Subscription(Model):
    __tablename__ = "subscriptions"

    user_id = Column(BigInteger, ForeignKey("users.id"), primary_key=True)
    channel_id = Column(BigInteger, ForeignKey("channels_to_subscribe.id"), primary_key=True)

    user = relationship("User")
    channel = relationship("ChannelToSubscribe")


class Payment(Model):
    __tablename__ = "payments"

    id = Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column("user_id", BigInteger)
    amount = Column("amount", BigInteger)
    accepted = Column("accepted", Boolean, default=False)


class PromoutionReferrallink(Model):
    __tablename__ = 'promoution_links'

    id = Column("id", BigInteger, primary_key=True)
    title = Column("title", Text)
