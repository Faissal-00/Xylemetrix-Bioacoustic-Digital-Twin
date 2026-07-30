import os
import json
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt
import torchaudio.transforms as T
import torchvision.models as models
import matplotlib
matplotlib.use('Agg') # Ensure matplotlib runs headlessly without opening physical windows
import matplotlib.pyplot as plt
import io
import base64
import torch.nn.functional as F

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "solanum_resnet18_mel.pth"
TARGET_LENGTH = 5000
SAMPLE_RATE = 10000

# --- 1. MODEL ARCHITECTURE ---
class PlantPulseResNet(nn.Module):
    def __init__(self):
        super(PlantPulseResNet, self).__init__()
        self.resnet = models.resnet18(weights=None)
        
        # Adapt for 1-channel grayscale Mel-spectrograms
        self.resnet.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
        num_ftrs = self.resnet.fc.in_features
        self.resnet.fc = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(num_ftrs, 1)
        )

    def forward(self, x):
        return self.resnet(x)

# --- 2. SIGNAL PROCESSING ---
def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    """Stable SOS bandpass filter."""
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    sos = butter(order, [low, high], btype='band', output='sos')
    return sosfiltfilt(sos, data)

def butter_lowpass_filter(data, cutoff, fs, order=4):
    """Stable SOS lowpass filter for underlying biological rhythms."""
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    sos = butter(order, normal_cutoff, btype='low', output='sos')
    return sosfiltfilt(sos, data)

# --- 3. INFERENCE ENGINE ---
def predict_wav(wav_path: str):
    """Processes a raw WAV file and returns a JSON-friendly prediction summary."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 1. Load Model
    model = PlantPulseResNet().to(device)
    if not Path(MODEL_PATH).exists():
        return {"error": f"Model not found at {MODEL_PATH}"}
    
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    model.eval()

    # 2. Setup Spectrogram Transformer
    mel_spectrogram = T.MelSpectrogram(
        sample_rate=SAMPLE_RATE,
        n_fft=1024,
        hop_length=128,
        n_mels=128
    ).to(device)
    amplitude_to_db = T.AmplitudeToDB().to(device)

    # 3. Read & Process Audio
    try:
        fs, raw_data = wavfile.read(wav_path)
    except Exception as e:
        return {"error": f"Failed to read audio: {str(e)}"}

    if len(raw_data.shape) > 1:
        raw_data = raw_data[:, 0]
        
    raw_data = raw_data.astype(np.float64)
    
    try:
        filtered = butter_bandpass_filter(raw_data, 0.5, 50.0, fs=fs)
    except ValueError as e:
        return {"error": f"Filtering error: {str(e)}"}
        
    std = np.std(filtered)
    if std == 0:
        return {"error": "Signal is flat (std=0)."}
    normalized = (filtered - np.mean(filtered)) / std

    # 4. Slice and Predict
    # --- GRAD-CAM HOOKS SETUP ---
    activations = None
    gradients = None

    def forward_hook(module, input, output):
        global activations
        activations = output

    def backward_hook(module, grad_input, grad_output):
        global gradients
        gradients = grad_output[0]

    # Attach hooks to the final convolutional layer of ResNet18
    target_layer = model.resnet.layer4[-1].conv2
    target_layer.register_forward_hook(forward_hook)
    target_layer.register_full_backward_hook(backward_hook)

    # 4. Slice and Predict (Fast Mode - No Gradients)
    predictions = []
    total_windows = 0
    stressed_windows = 0
    
    max_stress_prob = -1
    worst_window_tensor = None
    worst_window_start_idx = 0
    
    # Run the main loop fast and light
    with torch.no_grad():
        for start in range(0, len(normalized) - TARGET_LENGTH + 1, TARGET_LENGTH):
            window = normalized[start:start + TARGET_LENGTH].astype(np.float32)
            
            signal_tensor = torch.tensor(window, dtype=torch.float32).to(device)
            mel = mel_spectrogram(signal_tensor)
            mel_db = amplitude_to_db(mel)
            mel_db_input = mel_db.unsqueeze(0).unsqueeze(0) 
            
            output = model(mel_db_input)
            prob = torch.sigmoid(output).item()
            is_stressed = int(prob >= 0.5)
            
            predictions.append({
                "window_index": total_windows,
                "stress_probability": round(prob, 4),
                "prediction": "Stressed" if is_stressed else "Healthy"
            })
            
            # Keep a copy of the raw tensor for the worst stress event
            if prob > max_stress_prob:
                max_stress_prob = prob
                worst_window_tensor = signal_tensor 
                worst_window_start_idx = start
                
            total_windows += 1
            if is_stressed:
                stressed_windows += 1

    # --- 5. GENERATE GRAD-CAM HEATMAP (Only on the worst event) ---
    heatmap_base64 = None
    if worst_window_tensor is not None:
        # Use a dictionary to safely hold hook data (solves the NoneType error)
        cam_data = {'activations': None, 'gradients': None}

        def forward_hook(module, input, output):
            cam_data['activations'] = output

        def backward_hook(module, grad_input, grad_output):
            cam_data['gradients'] = grad_output[0]

        # Attach hooks to the ResNet
        target_layer = model.resnet.layer4[-1].conv2
        hook_f = target_layer.register_forward_hook(forward_hook)
        hook_b = target_layer.register_full_backward_hook(backward_hook)

        # Run JUST the worst window with gradients enabled
        with torch.enable_grad():
            mel = mel_spectrogram(worst_window_tensor)
            mel_db = amplitude_to_db(mel)
            mel_db_input = mel_db.unsqueeze(0).unsqueeze(0)
            
            # Save a clean 2D array for the background image
            worst_mel_db_np = mel_db.cpu().detach().numpy().squeeze() 
            
            mel_db_input.requires_grad_()
            output = model(mel_db_input)
            
            model.zero_grad()
            output[0, 0].backward() # Run math backwards to trigger hooks

        # Remove hooks so they don't leak memory on the next run
        hook_f.remove()
        hook_b.remove()

        # Calculate the heatmap mathematically using the safely stored data
        gradients = cam_data['gradients']
        activations = cam_data['activations']

        if gradients is not None and activations is not None:
            pooled_gradients = torch.mean(gradients, dim=[0, 2, 3])
            for i in range(activations.shape[1]):
                activations[:, i, :, :] *= pooled_gradients[i]
                
            heatmap = torch.mean(activations, dim=1).squeeze()
            heatmap = F.relu(heatmap) 
            heatmap /= torch.max(heatmap) + 1e-8 # Add tiny epsilon to prevent divide-by-zero
            
            # Resize heatmap to fit the spectrogram perfectly
            heatmap = heatmap.unsqueeze(0).unsqueeze(0)
            heatmap = F.interpolate(heatmap, size=(worst_mel_db_np.shape[0], worst_mel_db_np.shape[1]), mode='bilinear', align_corners=False)
            heatmap = heatmap.squeeze().cpu().detach().numpy()
            
            # Plot and encode to Base64
            fig, ax = plt.subplots(figsize=(6, 2))
            ax.imshow(worst_mel_db_np, aspect='auto', origin='lower', cmap='magma')
            ax.imshow(heatmap, aspect='auto', origin='lower', cmap='jet', alpha=0.5) 
            ax.axis('off')
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
            buf.seek(0)
            heatmap_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)
        # --- 6. CALCULATE REAL TECHNICAL INDICATORS FOR UI ---
    window_size = 1000 
    moving_avg = np.convolve(normalized, np.ones(window_size)/window_size, mode='same')
    
    try:
        low_pass = butter_lowpass_filter(normalized, 2.0, fs=fs)
    except Exception:
        low_pass = np.zeros_like(normalized)

    # --- 7. COMPILE SUMMARY AND RETURN ---
    stress_ratio = stressed_windows / total_windows if total_windows > 0 else 0
    overall_status = "Stressed" if stress_ratio >= 0.5 else "Healthy"

    result = {
        "file": Path(wav_path).name,
        "total_windows": total_windows,
        "stressed_windows": stressed_windows,
        "stress_ratio": round(stress_ratio, 4),
        "overall_status": overall_status,
        "detailed_predictions": predictions,
        "signal_data": normalized[::100].tolist(),
        "moving_average": moving_avg[::100].tolist(),
        "low_pass_filter": low_pass[::100].tolist(),
        "xai_heatmap": heatmap_base64,
        "worst_start_sec": worst_window_start_idx / fs,                 
        "worst_end_sec": (worst_window_start_idx + TARGET_LENGTH) / fs
    }
    
    return result    

if __name__ == "__main__":
    sample_wav = "../data/raw/TAMC_PLANTAS_DERIVED_DATASET_ZENODO_v1_PIPELINE_READY_LIGHT/data/raw_plants/Solanum/BYB_Recording_2022-10-25_10.47.58.wav"
    
    if Path(sample_wav).exists():
        print("Running prediction pipeline...\n")
        output = predict_wav(sample_wav)
        print(json.dumps(output, indent=4))
    else:
        print(f"Update the 'sample_wav' path at the bottom of the script to test a file.")