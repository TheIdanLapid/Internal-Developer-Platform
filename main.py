import os
import time
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# --- הגדרות GitHub (יום 2) ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "YourOrganizationOrUsername"
REPO_NAME = "Automated-Multi-Environment-Release"
WORKFLOW_FILENAME = "provision_env.yml"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# --- הגדרות מסד נתונים (יום 1) ---
DATABASE_URL = "sqlite:///./environments.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ProvisionRequestModel(Base):
    __tablename__ = "provision_requests"
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, index=True)
    environment = Column(String)
    ttl = Column(String)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# --- Pydantic Schemas ---
class ProvisionRequestCreate(BaseModel):
    service_name: str = Field(..., example="payment-service")
    environment: str = Field(..., example="staging")
    ttl: str = Field(default="2h", example="4h")

class ProvisionResponse(BaseModel):
    id: int
    service_name: str
    environment: str
    ttl: str
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

app = FastAPI(title="Internal Developer Platform API (Integrated)")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- לוגיקת הרקע (Background Worker Function) ---

def update_request_status(request_id: int, status: str):
    """עדכון סטטוס עצמאי במסד הנתונים."""
    db = SessionLocal()
    db_request = db.query(ProvisionRequestModel).filter(ProvisionRequestModel.id == request_id).first()
    if db_request:
        db_request.status = status
        db.commit()
    db.close()

def run_provisioning_pipeline(request_id: int, environment: str, service_name: str, ttl: str):
    """תהליך אסינכרוני שמנהל את ה-Workflow ב-GitHub ברקע."""
    update_request_status(request_id, "IN_PROGRESS")
    
    # 1. הפעלת ה-Workflow
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/{WORKFLOW_FILENAME}/dispatches"
    payload = {"ref": "main", "inputs": {"environment": environment, "service_name": service_name, "ttl": ttl}}
    
    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        if response.status_code != 204:
            update_request_status(request_id, "FAILED")
            return
    except Exception:
        update_request_status(request_id, "FAILED")
        return

    # המתנה קלה לרישום הריצה ב-GitHub
    time.sleep(10)

    # 2. ניטור (Polling) הסטטוס
    runs_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/{WORKFLOW_FILENAME}/runs"
    timeout = 300
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            res = requests.get(runs_url, headers=HEADERS)
            runs = res.json().get("workflow_runs", [])
            if runs:
                latest_run = runs[0]
                status = latest_run.get("status")
                conclusion = latest_run.get("conclusion")

                if status == "completed":
                    final_status = "COMPLETED" if conclusion == "success" else "FAILED"
                    update_request_status(request_id, final_status)
                    return
        except Exception:
            pass
        time.sleep(15)

    update_request_status(request_id, "FAILED")  # Timeout

# --- Endpoints ---

@app.post("/provision", response_model=ProvisionResponse, status_code=201)
def create_provision_request(
    request: ProvisionRequestCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    allowed_envs = ["dev", "qa", "staging"]
    if request.environment.lower() not in allowed_envs:
        raise HTTPException(status_code=400, detail=f"Environment must be one of {allowed_envs}")

    # שמירה ראשונית ב-DB
    db_request = ProvisionRequestModel(
        service_name=request.service_name,
        environment=request.environment.lower(),
        ttl=request.ttl,
        status="PENDING"
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    # רישום משימת הרקע לביצוע מידי לאחר החזרת התשובה למשתמש
    background_tasks.add_task(
        run_provisioning_pipeline,
        db_request.id,
        db_request.environment,
        db_request.service_name,
        db_request.ttl
    )

    return db_request

@app.get("/provision/{request_id}", response_model=ProvisionResponse)
def get_provision_status(request_id: int, db: Session = Depends(get_db)):
    db_request = db.query(ProvisionRequestModel).filter(ProvisionRequestModel.id == request_id).first()
    if not db_request:
        raise HTTPException(status_code=404, detail="Provision request not found")
    return db_request