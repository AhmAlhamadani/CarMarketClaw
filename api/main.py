from fastapi import FastAPI
from routes.fb_vehicles import router as vehicles_router

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db_test")
def test_db():
    return {"message": "Supabase connected successfully"}

app.include_router(vehicles_router, prefix="/fb_vehicles")