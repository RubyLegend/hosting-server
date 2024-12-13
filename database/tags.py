from .. import Base
from sqlalchemy import Column, Integer, VARCHAR
from sqlalchemy.orm import relationship


class Tags(Base):
    __tablename__ = 'Tags'

    IdTag = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    TagName = Column(VARCHAR(50), nullable=False, unique=True)

    media = relationship("Media", secondary="MediaTagsConnector", back_populates="tags")
