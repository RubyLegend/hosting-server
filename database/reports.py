from .. import Base
from sqlalchemy import Column, Integer, String, ForeignKey, VARCHAR, TIMESTAMP
from sqlalchemy.orm import relationship


class Reports(Base):
    __tablename__ = 'Reports'

    IdReport = Column(Integer, primary_key=True, nullable=False, autoincrement="auto")
    ReportTime = Column(TIMESTAMP())
    IdComment = Column(Integer, ForeignKey("Comments.IdComment"))
    IdUser = Column(Integer, ForeignKey("Users.IdUser"))
    ReportReason = Column(VARCHAR(10000))

    comments = relationship("Comments", back_populates="reports")
    users = relationship("Users", back_populates="reports")
