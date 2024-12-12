from .. import Base
from sqlalchemy import Column, Integer, String, VARCHAR, DateTime, TIMESTAMP, Boolean
from sqlalchemy.orm import relationship


class Users(Base):
    __tablename__ = 'Users'

    IdUser = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    Email = Column(VARCHAR(255), unique=True, nullable=False)
    LoginUser = Column(VARCHAR(255), unique=True, nullable=False)
    NameUser = Column(VARCHAR(255))
    Surname = Column(VARCHAR(255))
    Patronymic = Column(VARCHAR(255))
    Birthday = Column(DateTime())
    RegisterTime = Column(TIMESTAMP())
    About = Column(VARCHAR(255))
    Password = Column(String(255), nullable=False)
    IsAdmin = Column(Boolean(), default=0)

    subscribers = relationship("Subscribers", back_populates="users")
