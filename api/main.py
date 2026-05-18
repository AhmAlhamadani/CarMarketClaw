from fastapi import FastAPI
from api.routes.fb_vehicles import router as vehicles_router
from api.routes.scraper import router as scraper_router
from api.routes.agents import router as agents_router
from api.routes.autotrader import router as autotrader_router

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

@app.get("/db_test")
def test_db():
    return {"message": "Supabase connected successfully"}


app.include_router(vehicles_router, prefix="/fb_vehicles")

app.include_router(scraper_router, prefix="/scrape")
app.include_router(agents_router, prefix="/agents")
app.include_router(autotrader_router, prefix="/autotrader")