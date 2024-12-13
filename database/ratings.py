from .. import Base
from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship


class Ratings(Base):
    __tablename__ = 'Ratings'

    IdRating = Column(Integer, primary_key=True, autoincrement=True)
    IdUser = Column(Integer, ForeignKey("Users.IdUser"))
    IdMedia = Column(Integer, ForeignKey("Media.IdMedia"))
    IdRatingType = Column(Integer, ForeignKey("RatingTypes.IdRatingType"))
    RatingTime = Column(TIMESTAMP)

    users = relationship("Users", back_populates="ratings")
    media = relationship("Media", back_populates="ratings")
    rating_types = relationship("RatingTypes", back_populates="ratings")
