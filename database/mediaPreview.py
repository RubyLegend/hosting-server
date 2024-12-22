from .. import Base
from sqlalchemy import Column, Integer, String, ForeignKey, VARCHAR, TIMESTAMP
from sqlalchemy.orm import relationship


class MediaPreview(Base):
    __tablename__ = 'MediaPreview'

    IdMediaPreview = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    PreviewPath = Column(VARCHAR(1024), nullable=False)

    media = relationship("Media", back_populates="preview")
