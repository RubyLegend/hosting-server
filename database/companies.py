from .. import Base
from sqlalchemy import Column, Integer, String, VARCHAR, TEXT, ForeignKey
from sqlalchemy.orm import relationship


class Companies(Base):
    __tablename__ = 'Companies'

    IdCompany = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    Name = Column(VARCHAR(255), nullable=False)
    About = Column(TEXT(65535))
    IdCompanyLogo = Column(Integer, ForeignKey("CompanyLogo.IdCompanyLogo"), default=1)

    media = relationship("Media", back_populates="companies")
    user_roles = relationship("UserRoles", back_populates="companies")
    subscribers = relationship("Subscribers", back_populates="companies")
    companyLogo = relationship("CompanyLogo", back_populates="companies")
