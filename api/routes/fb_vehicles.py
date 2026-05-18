from fastapi import APIRouter

from api.db.fb_vehicles_repo import get_by_id, save_scraped_vehicle

router = APIRouter()


@router.post("/")
def create_fb_vehicle(vehicle: dict):
    saved = save_scraped_vehicle(vehicle)
    return {"message": "vehicle saved", "vehicle": saved}


@router.get("/{vehicle_id}")
def get_fb_vehicle(vehicle_id: str):
    return {"vehicle": get_by_id(vehicle_id)}
