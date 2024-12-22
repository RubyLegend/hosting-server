from .. import Base
from sqlalchemy import Column, Integer, String, VARCHAR, TEXT
from sqlalchemy.orm import relationship


class Companies(Base):
    __tablename__ = 'Companies'

    IdCompany = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    Name = Column(VARCHAR(255), nullable=False)
    About = Column(TEXT(65535))
    Owner = Column(VARCHAR(255))

    media = relationship("Media", back_populates="companies")
    user_roles = relationship("UserRoles", back_populates="companies")
    subscribers = relationship("Subscribers", back_populates="companies")
