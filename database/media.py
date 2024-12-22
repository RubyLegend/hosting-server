from .. import Base
from sqlalchemy import Column, Integer, String, ForeignKey, VARCHAR, TIMESTAMP
from sqlalchemy.orm import relationship


class Media(Base):
    __tablename__ = 'Media'

    IdMedia = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    IdCompany = Column(Integer, ForeignKey("Companies.IdCompany"))
    NameV = Column(VARCHAR(255), nullable=False)
    DescriptionV = Column(VARCHAR(10000))
    UploadTime = Column(TIMESTAMP())
    VideoPath = Column(VARCHAR(255), nullable=False, unique=True)
    IdMediaPreview = Column(Integer, ForeignKey("MediaPreview.IdMediaPreview"))

    companies = relationship("Companies", back_populates="media")
    ratings = relationship("Ratings", back_populates="media")
    comments = relationship("Comments", back_populates="media")
    view_history = relationship("ViewHistory", back_populates="media")
    tags = relationship("Tags", secondary="MediaTagsConnector", back_populates="media")
    preview = relationship("MediaPreview", back_populates="media")
