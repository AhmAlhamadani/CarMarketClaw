from fastapi import APIRouter
from api.db.supabase_client import supabase

router = APIRouter()

@router.post("/")
def create_fb_vehicle(vehicle: dict):

    response = supabase.table("fb_vehicles").insert(vehicle).execute()

    return {
        "message": "vehicle inserted",
        "data": response.data
    }