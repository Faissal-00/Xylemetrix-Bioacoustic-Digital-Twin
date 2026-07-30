import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from src.predict_pipeline import predict_wav  # Import your inference engine

app = FastAPI(title="PlantPulse 3D API")

# Mount static files (3D models, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount HTML templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    """Serves the main frontend dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/predict")
async def analyze_audio(file: UploadFile = File(...)):
    """Receives a .wav file from the frontend, runs the AI, and returns the result."""
    temp_file_path = f"temp_{file.filename}"
    
    # Save the uploaded file temporarily
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Run your ResNet model pipeline
        result = predict_wav(temp_file_path)
    finally:
        # Clean up the temporary audio file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
    return result