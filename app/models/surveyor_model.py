from dataclasses import dataclass


@dataclass(slots=True)
class Surveyor:
    surveyor_id: int
    surveyor_code: str
    surveyor_name: str
    gender: str
    father_name: str
    tazkira_no: str
    email_address: str
    whatsapp_number: str
    phone_number: str
    permanent_province_code: str
    current_province_code: str
