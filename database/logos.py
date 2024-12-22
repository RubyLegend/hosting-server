from .. import Base
from sqlalchemy import Column, Integer, String, ForeignKey, VARCHAR, TIMESTAMP
from sqlalchemy.orm import relationship


class CompanyLogo(Base):
    __tablename__ = 'CompanyLogo'

    IdCompanyLogo = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    LogoPath = Column(VARCHAR(1024), nullable=False)

    companies = relationship("Companies", back_populates="companyLogo")
