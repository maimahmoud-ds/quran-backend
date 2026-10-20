from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import init_db, get_db, User

app = FastAPI(title="Quran Reflection API")

init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()