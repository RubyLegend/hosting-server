from .. import Base
from sqlalchemy import Column, Integer, String, VARCHAR, DateTime, TIMESTAMP, Boolean
from sqlalchemy.orm import relationship


class Users(Base):
    __tablename__ = 'Users'

    IdUser = Column(Integer, primary_key=True, autoincrement=True)
    Email = Column(String(255), nullable=False, unique=True)
    LoginUser = Column(String(255), nullable=False, unique=True)
    NameUser = Column(String(255))
    Surname = Column(String(255))
    Patronymic = Column(String(255))
    Birthday = Column(DateTime)
    RegisterTime = Column(TIMESTAMP)
    Password = Column(String(255), nullable=False)
    IsActive = Column(Boolean, nullable=False, default=True)

    ratings = relationship("Ratings", back_populates="users")
    comments = relationship("Comments", back_populates="users")
    view_history = relationship("ViewHistory", back_populates="users")
    search_history = relationship("SearchHistory", back_populates="users")
    user_roles = relationship("UserRoles", back_populates="users")
    subscribers = relationship("Subscribers", back_populates="users")
