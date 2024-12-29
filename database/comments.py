from .. import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship


class Comments(Base):
    __tablename__ = 'Comments'

    IdComment = Column(Integer, primary_key=True, autoincrement=True)
    IdUser = Column(Integer, ForeignKey("Users.IdUser"))
    IdMedia = Column(Integer, ForeignKey("Media.IdMedia"))
    TextComment = Column(String(10000), nullable=False)
    Date = Column(DateTime, nullable=False)

    users = relationship("Users", back_populates="comments")
    media = relationship("Media", back_populates="comments")
    reports = relationship("Reports", back_populates="comments")
