from .. import Base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship


class Subscribers(Base):
    __tablename__ = 'Subscribers'

    IdSubscriber = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    IdCompany = Column(Integer, ForeignKey("Companies.IdCompany"))
    IdUser = Column(Integer, ForeignKey("Users.IdUser"))

    companies = relationship("Companies", back_populates="subscribers")
    users = relationship("Users", back_populates="subscribers")


