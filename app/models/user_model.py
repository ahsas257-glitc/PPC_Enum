from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class User:
    user_id: int
    username: str
    full_name: str | None
    role: str
    is_active: bool
    email: str | None
    created_at: datetime | None = None
