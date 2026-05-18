from clawbot.agents.plate_reader import read_plate
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

print("Running OCR...")

result = read_plate(
    vehicle["image_urls"]
)

print("Result:")
print(result)