from .. import Base
from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship


class SearchHistory(Base):
    __tablename__ = 'SearchHistory'

    IdSearchHistory = Column(Integer, primary_key=True, autoincrement=True)
    IdUser = Column(Integer, ForeignKey("Users.IdUser"))
    SearchQuery = Column(String(255))
    SearchTime = Column(TIMESTAMP)

    users = relationship("Users", back_populates="search_history")
