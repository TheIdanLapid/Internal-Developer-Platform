import time
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import ProvisionRequestModel

# הגדרת Celery מול Redis כ-Broker
celery_app = Celery(
    "provisioning_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)

# Celery עובד בצורה סינכרונית, לכן משתמשים בדרייבר סינכרוני (psycopg2) מול אותו DB
SYNC_DB_URL = "postgresql+psycopg2://user:password@localhost:5432/idp_db"
sync_engine = create_engine(SYNC_DB_URL)
SessionLocalSync = sessionmaker(bind=sync_engine)

def update_status(request_id: int, status: str):
    with SessionLocalSync() as db:
        req = db.query(ProvisionRequestModel).filter(ProvisionRequestModel.id == request_id).first()
        if req:
            req.status = status
            db.commit()

@celery_app.task(bind=True, max_retries=3)
def run_provisioning_pipeline(self, request_id: int, environment: str, service_name: str, ttl: str):
    """
    Celery Worker Task.
    """
    try:
        update_status(request_id, "IN_PROGRESS")
        
        # סימולציה: הקצאת תשתית בפועל מול AWS / GitHub Actions
        time.sleep(15)
        
        update_status(request_id, "COMPLETED")
    except Exception as exc:
        update_status(request_id, "FAILED")
        # מנגנון Resiliency: ניסיון חוזר במידה ושרת חיצוני מחזיר שגיאה
        raise self.retry(exc=exc, countdown=60)