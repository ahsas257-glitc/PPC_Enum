from dataclasses import dataclass


@dataclass(slots=True)
class Province:
    province_code: str
    province_name: str
