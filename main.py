from datetime import date
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import init_db, get_db, User, UserTask

app = FastAPI(title="Quran Reflection API")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

ALLOWED_STATUSES = ["pending", "completed", "late"]


# ---------- شكل البيانات ----------
class UserCreate(BaseModel):
    name: str
    email: str


class TaskCreate(BaseModel):
    user_id: int
    verse_number: int
    action_text: str
    status: str = "pending"
    due_date: Optional[date] = None
    end_date: Optional[date] = None
    custom_actions: bool = False


class StatusUpdate(BaseModel):
    status: str


class SyncRequest(BaseModel):
    user_id: int
    verse_number: int
    action_text: str
    start_date: date
    end_date: date
    is_custom: bool = False


# ---------- Endpoints ----------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@app.post("/users")
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    user = User(name=data.name, email=data.email)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already exists")
    db.refresh(user)
    return user


@app.post("/tasks")
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == data.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    task = UserTask(
        user_id=data.user_id,
        verse_number=data.verse_number,
        action_text=data.action_text,
        status=data.status,
        due_date=data.due_date,
        end_date=data.end_date,
        custom_actions=data.custom_actions,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.get("/tasks/{user_id}")
def get_user_tasks(user_id: int, db: Session = Depends(get_db)):
    return db.query(UserTask).filter(UserTask.user_id == user_id).all()


@app.put("/tasks/{task_id}/status")
def update_task_status(task_id: int, data: StatusUpdate, db: Session = Depends(get_db)):
    if data.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Use one of: {ALLOWED_STATUSES}",
        )

    task = db.query(UserTask).filter(UserTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = data.status
    db.commit()
    db.refresh(task)
    return task


@app.post("/sync")
def sync_task(data: SyncRequest, db: Session = Depends(get_db)):
    if data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    user = db.query(User).filter(User.user_id == data.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    task = UserTask(
        user_id=data.user_id,
        verse_number=data.verse_number,
        action_text=data.action_text,
        status="pending",
        due_date=data.start_date,
        end_date=data.end_date,
        custom_actions=data.is_custom,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # البيانات اللي بسمة هتستخدمها في add_event_to_calendar
    calendar_payload = {
        "summary": data.action_text,
        "start_date": data.start_date.isoformat(),
        "end_date": data.end_date.isoformat(),
    }

    return {"task": task, "calendar_payload": calendar_payload}