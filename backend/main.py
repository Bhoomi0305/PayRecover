from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PayRecover")
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def serve_dashboard():
    return FileResponse("frontend/index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "message": "PayRecover backend is running"}
