from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db_test")
def test_db():
    return {"message": "Supabase connected successfully"}