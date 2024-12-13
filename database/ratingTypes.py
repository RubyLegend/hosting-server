from .. import Base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship


class RatingTypes(Base):
    __tablename__ = 'RatingTypes'

    IdRatingType = Column(Integer, primary_key=True, autoincrement=True)
    NameRating = Column(String(20), nullable=False)
    RatingFactor = Column(Integer, nullable=False)

    ratings = relationship("Ratings", back_populates="rating_types")
