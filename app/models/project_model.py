from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class Project:
    project_id: int
    project_code: str
    project_name: str
    phase_number: int
    project_type: str
    status: str
    client_name: str | None = None
    implementing_partner: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None
    project_document_link: str | None = None
    project_short_name: str | None = None
    created_at: datetime | None = None
