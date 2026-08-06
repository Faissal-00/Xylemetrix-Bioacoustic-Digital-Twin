import os
import time
import shutil
from fastapi import FastAPI, UploadFile, File, Form, Request # 👇 ADDED 'Form' to imports
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.predict_pipeline import predict_wav  
from src.database import init_db, log_prediction, get_history, delete_record, clear_all_history

# Initialize the SQLite database
init_db()

app = FastAPI(title="PlantPulse 3D API")

# Mount static files (3D models, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount HTML templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    """Serves the main frontend dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})

# 👇 ADDED field_id parameter to catch the JS formData
@app.post("/predict")
async def analyze_audio(file: UploadFile = File(...), field_id: str = Form("Unknown")):
    """Receives a .wav file from the frontend, runs the AI, and returns the result."""
    temp_file_path = f"temp_{file.filename}"
    
    # Save the uploaded file temporarily
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # 1. Start the timer
        start_time = time.time()

        # Run your ResNet model pipeline
        result = predict_wav(temp_file_path)
        
        # 2. Stop the timer
        inference_time_ms = int((time.time() - start_time) * 1000)

        # 3. Extract variables and log to database (if no errors occurred)
        if "error" not in result:
            overall_status = result.get("overall_status", "Unknown") 
            
            # Extract the specific event counts from the pipeline output
            class_breakdown = result.get("class_breakdown", {})
            empty_pot_count = class_breakdown.get("empty_pot_count", 0)
            tomato_cut_count = class_breakdown.get("tomato_cut_count", 0)
            tomato_dry_count = class_breakdown.get("tomato_dry_count", 0)

            # 👇 ADDED field_id to the database function call
            log_prediction(
                field_id=field_id,
                filename=file.filename,
                overall_status=overall_status,
                empty_pot_count=empty_pot_count,
                tomato_cut_count=tomato_cut_count,
                tomato_dry_count=tomato_dry_count,
                inference_time_ms=inference_time_ms
            )

    finally:
        # Clean up the temporary audio file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
    return result

@app.get("/api/history")
async def get_history_api():
    """Returns the last 50 analyses from the database."""
    data = get_history()
    return {"status": "success", "data": data}

@app.delete("/api/history/{record_id}")
async def delete_history_record(record_id: int):
    """API endpoint to delete a single record."""
    delete_record(record_id)
    return {"status": "success"}

@app.delete("/api/history")
async def delete_all_history():
    """API endpoint to clear all records."""
    clear_all_history()
    return {"status": "success"}