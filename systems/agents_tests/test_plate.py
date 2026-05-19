from systems.agents.plate_reader import read_plate
from systems.vision import build_vision_context 
from api.db.supabase_client import supabase

print("Fetching vehicle...")

row = (
    supabase
    .table("fb_vehicles")
    .select("*")
    .limit(1)
    .execute()
)

print("Vehicle fetched")

vehicle = row.data[0]

print("Title:", vehicle["title"])
print("Images:", len(vehicle["image_urls"]))

print("Building vision context and running OCR...")

# FIX: Build the vision context dictionary before passing it to the agent
vision = build_vision_context(vehicle["image_urls"]) 

result = read_plate(vision)

print("Result:")
print(result)