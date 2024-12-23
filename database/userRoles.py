from .. import Base
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship


class UserRoles(Base):
    __tablename__ = 'UserRoles'

    IdUser = Column(Integer, ForeignKey("Users.IdUser"), primary_key=True)
    IdCompany = Column(Integer, ForeignKey("Companies.IdCompany"), primary_key=True, nullable=True)
    IdAccessLevel = Column(Integer, ForeignKey("AccessLevels.IdAccessLevel"))

    users = relationship("Users", back_populates="user_roles")
    companies = relationship("Companies", back_populates="user_roles")
    access_levels = relationship("AccessLevels", back_populates="user_roles")
