from .. import Base
from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship


class ViewHistory(Base):
    __tablename__ = 'ViewHistory'

    IdViewHistory = Column(Integer, primary_key=True, autoincrement=True)
    IdUser = Column(Integer, ForeignKey("Users.IdUser"))
    IdMedia = Column(Integer, ForeignKey("Media.IdMedia"))
    ViewTime = Column(TIMESTAMP)

    users = relationship("Users", back_populates="view_history")
    media = relationship("Media", back_populates="view_history")
