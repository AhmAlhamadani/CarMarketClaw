from fastapi import FastAPI
from api.routes.fb_vehicles import router as fb_vehicles_router

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db_test")
def test_db():
    return {"message": "Supabase connected successfully"}

app.include_router(fb_vehicles_router, prefix="/fb_vehicles")