"""
Maria Todo App v3 — Mobile-First, Render-ready
"""

import os
import smtplib
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, Boolean, Enum as SAEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import enum

load_dotenv()

# ── Database ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:ipQmoMpEjUgYIMMCUpysKPQpMxfkYPlN@postgres.railway.internal:5432/railway")
# Render gives postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── Models ────────────────────────────────────────────────
class CardStatus(str, enum.Enum):
    future = "future"
    now = "now"
    completed = "completed"

class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class TodoCard(Base):
    __tablename__ = "todo_cards"
    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String(200), nullable=False)
    description  = Column(Text, nullable=True)
    scheduled_date = Column(Date, nullable=False)
    status       = Column(SAEnum(CardStatus), default=CardStatus.future)
    priority     = Column(SAEnum(Priority), default=Priority.medium)
    color        = Column(String(20), default="#6c63ff")
    created_at   = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    notification_sent = Column(Boolean, default=False)
    order_index  = Column(Integer, default=0)

class Notification(Base):
    __tablename__ = "notifications"
    id         = Column(Integer, primary_key=True, index=True)
    message    = Column(Text, nullable=False)
    card_title = Column(String(200))
    card_id    = Column(Integer, nullable=True)
    is_read    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ── Schemas ───────────────────────────────────────────────
class CardCreate(BaseModel):
    title: str
    description: Optional[str] = None
    scheduled_date: date
    color: Optional[str] = "#6c63ff"
    priority: Optional[Priority] = Priority.medium

class CardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[date] = None
    status: Optional[CardStatus] = None
    priority: Optional[Priority] = None
    color: Optional[str] = None
    order_index: Optional[int] = None

class CardOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    scheduled_date: date
    status: CardStatus
    priority: Priority
    color: str
    created_at: datetime
    completed_at: Optional[datetime]
    order_index: int
    class Config:
        from_attributes = True

class NotificationOut(BaseModel):
    id: int
    message: str
    card_title: str
    card_id: Optional[int]
    is_read: bool
    created_at: datetime
    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── Email ─────────────────────────────────────────────────
def send_email_notification(card_title, card_date, description, priority="medium"):
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    to_email  = os.getenv("NOTIFY_EMAIL", smtp_user)
    if not smtp_user or not smtp_pass:
        print("⚠️  SMTP not configured.")
        return

    priority_label = {"high":"🔴 TINGGI","medium":"🟡 Sedang","low":"🟢 Rendah"}.get(priority,"🟡 Sedang")
    priority_color = {"high":"#ef4444","medium":"#f59e0b","low":"#10b981"}.get(priority,"#f59e0b")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌸 Reminder Maria: '{card_title}' — Besok!"
    msg["From"] = smtp_user
    msg["To"]   = to_email

    html = f"""<html><body style="font-family:Georgia,serif;background:#fafafa;padding:32px;">
    <div style="max-width:540px;margin:auto;background:#fff;border-radius:16px;padding:36px;border:1px solid #eee;">
        <h2 style="color:#1a1a1a;margin:0 0 4px;">🌸 Untuk Cintaku, Maria</h2>
        <p style="color:#888;margin:0 0 24px;font-size:14px;">Pengingat tugas besok</p>
        <div style="border-left:3px solid {priority_color};padding:16px 20px;background:#fafafa;border-radius:8px;margin-bottom:20px;">
            <div style="font-size:11px;font-weight:700;color:{priority_color};margin-bottom:6px;letter-spacing:1px;">{priority_label}</div>
            <div style="font-size:18px;font-weight:700;color:#1a1a1a;margin-bottom:6px;">{card_title}</div>
            <div style="font-size:14px;color:#555;">{description or 'Tidak ada catatan.'}</div>
            <div style="font-size:12px;color:#aaa;margin-top:10px;">📅 {card_date.strftime('%d %B %Y')}</div>
        </div>
        <p style="font-size:12px;color:#ccc;margin:0;">Dikirim otomatis · Maria Todo App 💜</p>
    </div></body></html>"""
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, to_email, msg.as_string())
        print(f"✅ Email sent: {card_title}")
    except Exception as e:
        print(f"❌ Email error: {e}")

# ── Scheduler ─────────────────────────────────────────────
def check_and_send_notifications():
    db = SessionLocal()
    try:
        today    = date.today()
        tomorrow = today + timedelta(days=1)

        # Pindahkan future → now kalau scheduled_date <= hari ini
        future_due = db.query(TodoCard).filter(
            TodoCard.status == CardStatus.future,
            TodoCard.scheduled_date <= today
        ).all()
        for card in future_due:
            card.status = CardStatus.now
            print(f"🔄 Auto-moved to NOW: {card.title} ({card.scheduled_date})")

        # Kirim notifikasi untuk kartu besok
        cards_tomorrow = db.query(TodoCard).filter(
            TodoCard.scheduled_date == tomorrow,
            TodoCard.status.in_([CardStatus.future, CardStatus.now]),
            TodoCard.notification_sent == False
        ).all()

        for card in cards_tomorrow:
            send_email_notification(
                card.title, card.scheduled_date,
                card.description or "",
                card.priority.value if card.priority else "medium"
            )
            card.notification_sent = True
            db.add(Notification(
                message=f"'{card.title}' dijadwalkan besok ({tomorrow.strftime('%d %B %Y')}). Prioritas: {card.priority.value}.",
                card_title=card.title,
                card_id=card.id
            ))

        db.commit()
    except Exception as e:
        print(f"❌ Scheduler error: {e}")
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(check_and_send_notifications, "cron", hour=8, minute=0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    check_and_send_notifications()
    yield
    scheduler.shutdown()

# ── App ───────────────────────────────────────────────────
app = FastAPI(title="Maria Todo", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── API Routes ────────────────────────────────────────────
@app.get("/api/cards", response_model=List[CardOut])
def get_cards(db: Session = Depends(get_db)):
    return db.query(TodoCard).order_by(TodoCard.scheduled_date, TodoCard.order_index).all()

@app.post("/api/cards", response_model=CardOut)
def create_card(card: CardCreate, db: Session = Depends(get_db)):
    today    = date.today()
    tomorrow = today + timedelta(days=1)
    # Tanggal <= hari ini → langsung NOW, lebih dari hari ini → FUTURE
    status = CardStatus.now if card.scheduled_date <= today else CardStatus.future
    db_card = TodoCard(**card.dict(), status=status)
    db.add(db_card)
    db.commit()
    db.refresh(db_card)

    if card.scheduled_date == tomorrow:
        db.add(Notification(
            message=f"'{card.title}' dijadwalkan besok. Jangan lupa! 💜",
            card_title=card.title,
            card_id=db_card.id
        ))
        send_email_notification(
            card.title, card.scheduled_date,
            card.description or "",
            card.priority.value if card.priority else "medium"
        )
        db_card.notification_sent = True
        db.commit()

    return db_card

@app.patch("/api/cards/{card_id}", response_model=CardOut)
def update_card(card_id: int, card: CardUpdate, db: Session = Depends(get_db)):
    db_card = db.query(TodoCard).filter(TodoCard.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card not found")

    update_data = card.dict(exclude_unset=True)

    if update_data.get("status") == CardStatus.completed:
        update_data["completed_at"] = datetime.utcnow()

    # Kalau tanggal diubah dan status belum completed → recalculate status
    if "scheduled_date" in update_data and "status" not in update_data:
        if db_card.status != CardStatus.completed:
            new_date = update_data["scheduled_date"]
            today    = date.today()
            update_data["status"] = CardStatus.now if new_date <= today else CardStatus.future

    for key, val in update_data.items():
        setattr(db_card, key, val)
    db.commit()
    db.refresh(db_card)
    return db_card

@app.delete("/api/cards/{card_id}")
def delete_card(card_id: int, db: Session = Depends(get_db)):
    db_card = db.query(TodoCard).filter(TodoCard.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(db_card)
    db.commit()
    return {"ok": True}

@app.get("/api/notifications", response_model=List[NotificationOut])
def get_notifications(db: Session = Depends(get_db)):
    return db.query(Notification).order_by(Notification.created_at.desc()).limit(50).all()

@app.get("/api/notifications/unread-count")
def unread_count(db: Session = Depends(get_db)):
    count = db.query(Notification).filter(Notification.is_read == False).count()
    return {"count": count}

@app.post("/api/notifications/mark-read")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Notification).delete()
    db.commit()
    return {"ok": True}

@app.post("/api/notifications/trigger")
def trigger_notifications():
    check_and_send_notifications()
    return {"ok": True}

@app.post("/api/notifications/reset-sent")
def reset_notification_sent(db: Session = Depends(get_db)):
    db.query(TodoCard).update({"notification_sent": False})
    db.commit()
    return {"ok": True}

# ── Frontend ──────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
