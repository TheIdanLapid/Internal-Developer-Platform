from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import Column, Integer, String, Index
from sqlalchemy.orm import declarative_base

# שימוש ב-asyncpg לתקשורת אסינכרונית מול PostgreSQL
DATABASE_URL = "sqlite+aiosqlite:///./idp_prod.db"

engine = create_async_engine(DATABASE_URL, pool_size=20, max_overflow=10)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class ProvisionRequestModel(Base):
    __tablename__ = "provision_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, nullable=False)
    environment = Column(String, nullable=False)
    ttl = Column(String)
    status = Column(String, default="PENDING")
    
    # Idempotency: מניעת כפילות בקשות על אותה סביבה אם היא כבר בתהליך
    __table_args__ = (
        Index(
            'idx_unique_active_provision',
            'service_name',
            'environment',
            unique=True,
            postgresql_where=(status.in_(["PENDING", "IN_PROGRESS"]))
        ),
    )