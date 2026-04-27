import pg8000.dbapi
from fastapi import FastAPI, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import cast, String
import json

from models import SessionLocal, Garage
from scraper import run_deep_scrape_generator

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

SCRAPE_STATE = {"is_running": False}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- UI ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/login")
async def process_login(username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    raise HTTPException(status_code=401, detail="Invalid Credentials")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.get("/database-viewer", response_class=HTMLResponse)
async def database_viewer(request: Request):
    return templates.TemplateResponse(request=request, name="database.html")


# --- SCRAPING ROUTES ---
@app.get("/api/stop-scrape")
def stop_scrape():
    SCRAPE_STATE["is_running"] = False
    return {"message": "Scraping stopped"}


@app.get("/api/live-scrape")
def live_scrape(website: str, keyword: str, limit: int = 5, db: Session = Depends(get_db)):
    def generate():
        SCRAPE_STATE["is_running"] = True
        try:
            for result in run_deep_scrape_generator(keyword, limit):
                if not SCRAPE_STATE["is_running"]:
                    yield f"data: {json.dumps({'type': 'done', 'message': 'Stopped by user'})}\n\n"
                    break

                if result["type"] == "result":
                    exists = db.query(Garage).filter(Garage.source_url == result["data"]["source_url"]).first()
                    result["data"]["is_saved"] = bool(exists)

                yield f"data: {json.dumps(result)}\n\n"
        finally:
            SCRAPE_STATE["is_running"] = False

    return StreamingResponse(generate(), media_type="text/event-stream")


# --- DATABASE CRUD APIs ---
@app.post("/api/garages/save")
def save_garage(data: dict, db: Session = Depends(get_db)):
    # 1. REMOVE the UI-only flag before saving to PostgreSQL!
    data.pop("is_saved", None)

    new_garage = Garage(**data)
    try:
        db.add(new_garage)
        db.commit()
        return {"message": "Saved successfully!"}
    except IntegrityError:
        db.rollback()
        return {"message": "Garage already exists in DB!"}


@app.get("/api/garages")
def get_all(db: Session = Depends(get_db)):
    return db.query(Garage).order_by(Garage.id.desc()).all()


@app.get("/api/garages/location/{loc}")
def get_by_location(loc: str, db: Session = Depends(get_db)):
    return db.query(Garage).filter(Garage.location.ilike(f"%{loc}%")).all()


@app.get("/api/garages/service/{svc}")
def get_by_service(svc: str, db: Session = Depends(get_db)):
    return db.query(Garage).filter(cast(Garage.extra_data, String).ilike(f"%{svc}%")).all()


@app.put("/api/garages/{g_id}")
def update_garage(g_id: int, update_data: dict, db: Session = Depends(get_db)):
    garage = db.query(Garage).filter(Garage.id == g_id).first()
    if not garage: raise HTTPException(status_code=404, detail="Not found")

    garage.name = update_data.get("name", garage.name)
    garage.location = update_data.get("location", garage.location)
    garage.phone = update_data.get("phone", garage.phone)
    db.commit()
    return {"message": "Updated successfully"}


@app.delete("/api/garages/{g_id}")
def delete_garage(g_id: int, db: Session = Depends(get_db)):
    garage = db.query(Garage).filter(Garage.id == g_id).first()
    if not garage: raise HTTPException(status_code=404, detail="Not found")
    db.delete(garage)
    db.commit()
    return {"message": "Deleted successfully"}