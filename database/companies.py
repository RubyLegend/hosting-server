from .. import Base
from sqlalchemy import Column, Integer, String, VARCHAR, TEXT
from sqlalchemy.orm import relationship


class Companies(Base):
    __tablename__ = 'Companies'

    IdCompany = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    Name = Column(VARCHAR(255), nullable=False)
    About = Column(TEXT(65535))

    subscribers = relationship("Subscribers", back_populates="companies")
