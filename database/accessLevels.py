from .. import Base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship


class AccessLevels(Base):
    __tablename__ = 'AccessLevels'

    IdAccessLevel = Column(Integer, primary_key=True, autoincrement=True)
    AccessName = Column(String(20), nullable=False)
    AccessLevel = Column(Integer, nullable=False, default=1)

    user_roles = relationship("UserRoles", back_populates="access_levels")
