from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from database import AsyncSessionLocal, ProvisionRequestModel, engine, Base
from tasks import run_provisioning_pipeline

app = FastAPI(title="Internal Developer Platform API (Production Ready)")

# --- Pydantic Models ---
class ProvisionRequestCreate(BaseModel):
    service_name: str
    environment: str
    ttl: str = "2h"

class ProvisionResponse(BaseModel):
    id: int
    service_name: str
    environment: str
    ttl: str
    status: str

    class Config:
        from_attributes = True

# --- Database Dependency ---
async def get_async_db():
    async with AsyncSessionLocal() as db:
        yield db

# --- Startup Event ---
@app.on_event("startup")
async def startup():
    # יצירת טבלאות באופן אסינכרוני
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- Endpoints ---
@app.post("/provision", response_model=ProvisionResponse, status_code=status.HTTP_201_CREATED)
async def create_provision_request(request: ProvisionRequestCreate, db: AsyncSession = Depends(get_async_db)):
    new_request = ProvisionRequestModel(
        service_name=request.service_name,
        environment=request.environment,
        ttl=request.ttl
    )
    
    db.add(new_request)
    try:
        await db.commit()
        await db.refresh(new_request)
    except IntegrityError:
        await db.rollback()
        # מניעת כפילות: סביבה זו כבר מוקמת כרגע
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Provisioning for {request.service_name} in {request.environment} is already pending or in progress."
        )

    # העברת המשימה לתור של Celery
    run_provisioning_pipeline.delay(
        new_request.id, 
        new_request.environment, 
        new_request.service_name, 
        new_request.ttl
    )

    return new_request

@app.get("/provision/{request_id}", response_model=ProvisionResponse)
async def get_provision_status(request_id: int, db: AsyncSession = Depends(get_async_db)):
    # ביצוע שאילתה אסינכרונית (בגרסה 2.0 של SQLAlchemy יש להשתמש ב-execute וב-scalars)
    result = await db.execute(select(ProvisionRequestModel).filter(ProvisionRequestModel.id == request_id))
    db_request = result.scalars().first()
    
    if not db_request:
        raise HTTPException(status_code=404, detail="Provision request not found")
    return db_request