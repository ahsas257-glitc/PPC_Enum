from app.core.database import fetch_all


class ProvinceRepository:
    def list_all(self) -> list[dict]:
        return fetch_all("SELECT * FROM provinces ORDER BY province_name")
