from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: Optional[str]
    is_suspended: bool
    created_at: Optional[datetime]
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class TicketStatusUpdate(BaseModel):
    status: str
    admin_reply: Optional[str] = None


class CounsellorAction(BaseModel):
    remarks: Optional[str] = None


class ModerationFlagAction(BaseModel):
    status: str
    admin_note: Optional[str] = None


class PasswordReset(BaseModel):
    new_password: str