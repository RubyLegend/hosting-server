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
