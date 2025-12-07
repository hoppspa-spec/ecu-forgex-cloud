from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parent
STATIC = ROOT_DIR / "static"  # carpeta donde están index.html, usuarios.html, etc.

app = FastAPI(title="ECU FORGE X")

# Sirve los archivos estáticos
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Healthcheck
@app.get("/health")
def health():
    return {"ok": True}

# Redirección del root al index
@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")

