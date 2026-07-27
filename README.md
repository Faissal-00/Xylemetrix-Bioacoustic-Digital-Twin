# PlantPulse 3D
*Plant Electrophysiology Digital Twin for Hidden Stress Detection (Hardware-Free Approach)*

## Overview
This project builds a Digital Twin Simulation of a plant, designed to detect biological stress signals days before physical symptoms become visible. The unique aspect of this project is its strict "No Hardware" constraint; it relies entirely on processing raw, open-source biological signal data on a standard laptop.

The core pipeline processes 1D-time-series electrophysiology data (the plant's electrical "pulse"), runs it through a custom Deep Learning model, and translates the classification (e.g., "Acidic Stress Detected") into a real-time, dynamic visual response on a 3D plant model.

---

## Motivation
Current AgTech projects focus heavily on reactive diagnosis (classifying a disease *after* the plant is sick). This project moves toward proactive, predictive analytics. It addresses the complexity of understanding internal plant behavior, proving that advanced "sensing" can be achieved programmatically.

---

## Project Architecture & Pipeline

### 1. Data Ingestion & Preprocessing
*   The Signal: Plant electrophysiology (1D time-series voltages).
*   Action: Simulate a live data feed by streaming data row-by-row from a CSV dataset. Apply bandpass filters to remove electrical noise (like 50/60Hz mains power noise).

### 2. The Deep Learning Engine (Signal Classifier)
*   Model: A custom-built 1D Convolutional Neural Network (1D-CNN).
*   Task: This model is trained specifically on labeled datasets of plants undergoing various conditions (e.g., control group vs. salt stress). It learns the invisible patterns (features) that differentiate a healthy plant from a stressed one.

### 3. The 3D Digital Twin Bridge (Visualization)
*   Environment: Built using Python visualization libraries (e.g., Streamlit for the interface, PyVista or open3d for rendering the 3D model).
*   Logic: The 1D-CNN output (classification) controls the 3D mesh. If the model predicts stress with high confidence, the visualization script maps a new color (e.g., orange or yellow) over specific nodes or tissues of the 3D plant model in real-time.

---

## Hardware & Software Requirements
This project runs entirely on software:
*   Processor: Minimum Intel i5/i7 (or AMD equivalent) / Apple Silicon (M1/M2/M3).
*   GPU: Not strictly required, but beneficial for faster 1D-CNN training.
*   Memory (RAM): 8GB minimum; 16GB recommended for simultaneous 3D rendering and model inference.

### Python Dependencies (Core Libraries)
pandas            # Data manipulation
numpy             # Numerical operations
scipy             # Signal filtering
pytorch           # Deep Learning framework
open3d            # Advanced 3D rendering and mesh control
pyvista           # Alternate 3D mesh visualization
streamlit         # Interactive Dashboard UI

---

## Sourcing the Data
Finding high-quality, open plant electrophysiology datasets is key. You can use platforms like:
1.  Zenodo.org / Mendeley Data: Search "plant electrophysiology" or "plant action potential."

---
## Directory Structure

```text
PlantPulse_3D/
│
├── data/                    # Open-source datasets (ignored by Git)
│   ├── raw/                 # Original CSVs/Signal files
│   └── processed/           # Filtered and standardized signals
│
├── models/                  # Saved AI models (.pth, .h5, etc.)
│
├── visuals/                 # 3D assets and screenshots
│   └── plant_model.obj      # The base 3D plant file (can be free from sketchfab/turboSquid)
│
├── src/                     # Source Code
│   ├── __init__.py
│   ├── data_loader.py       # Handles reading datasets
│   ├── signal_processor.py   # Code to filter noise
│   ├── train_model.py       # Training the 1D-CNN
│   └── predict_pipeline.py   # Combines model inference + visualization
│
├── requirements.txt         # List of Python libraries needed
└── README.md                # The central document (detailed below)

## Step-by-Step Methodology

### Step 1: Signal Exploration & Preprocessing (signal_processor.py)
Load the raw CSV data. Plot the raw signal to visualize the noise. Apply a butterworth bandpass filter (e.g., 1-50Hz) to isolate biological signals. Standardize (Z-score normalize) the filtered signal.

### Step 2: Designing the 1D-CNN (train_model.py)
Define the input shape (your normalized signal window). Create Conv1D layers (to detect local patterns), MaxPooling1D layers (for downsampling), and Dense (Fully Connected) layers for final classification (Healthy vs. Stressed). Split your data (Train/Validation/Test) and train the model.

### Step 3: Integrating with 3D Rendering (predict_pipeline.py)
1.  Load your base 3D plant model (e.g., .obj file).
2.  Set up the Streamlit interface.
3.  Load your trained model. Start the simulation loop:
    *   Read one row of processed test data.
    *   Pass the window to the 1D-CNN for a prediction.
    *   Based on the prediction class, update the mesh color of the 3D model.
