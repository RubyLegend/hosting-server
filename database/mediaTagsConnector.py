from .. import Base
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship


class MediaTagsConnector(Base):
    __tablename__ = 'MediaTagsConnector'

    IdConnection = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    IdTag = Column(Integer, ForeignKey("Tags.IdTag"))
    IdMedia = Column(Integer, ForeignKey("Media.IdMedia"))
