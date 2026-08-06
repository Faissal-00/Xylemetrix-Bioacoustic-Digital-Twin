import os
import json
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from scipy.io import wavfile
import torchaudio.transforms as T
import torchvision.models as models
import matplotlib
matplotlib.use('Agg') # Ensure matplotlib runs headlessly
import matplotlib.pyplot as plt
import io
import base64
import torch.nn.functional as F

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
# Ensure this points to the final locked model you just trained
MODEL_PATH = BASE_DIR / "models" / "solanum_ultrasonic_resnet.pth" 
TARGET_LENGTH = 1000    # 1,000 sample windows for bioacoustic pops
SAMPLE_RATE = 500000    # 500 kHz Ultrasonic

# Class mapping based on your training folder structure
CLASS_MAP = {
    0: "Normal (Background)",
    1: "Stress (Cut/Damage)",
    2: "Stress (Dehydration)"
}

# --- 1. MODEL ARCHITECTURE (3-CLASS) ---
class SolanumUltrasonicResNet(nn.Module):
    def __init__(self, num_classes=3):
        super(SolanumUltrasonicResNet, self).__init__()
        self.resnet = models.resnet18(weights=None)
        
        # Adapt for 1-channel grayscale Mel-spectrograms
        self.resnet.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
        num_ftrs = self.resnet.fc.in_features
        self.resnet.fc = nn.Sequential(
            nn.Dropout(0.4),
            nn.Linear(num_ftrs, num_classes)
        )

    def forward(self, x):
        return self.resnet(x)

# --- 2. INFERENCE ENGINE ---
def predict_wav(wav_path: str):
    """Processes a raw 500kHz WAV file and returns a 3-class prediction summary."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 1. Load Model
    model = SolanumUltrasonicResNet(num_classes=3).to(device)
    if not Path(MODEL_PATH).exists():
        return {"error": f"Model not found at {MODEL_PATH}"}
    
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    model.eval()

    # 2. Setup Bioacoustic Spectrogram Transformer (Matches Training Exactly)
    mel_spectrogram = T.MelSpectrogram(
        sample_rate=SAMPLE_RATE,
        n_fft=256,
        hop_length=32,
        n_mels=64
    ).to(device)
    amplitude_to_db = T.AmplitudeToDB().to(device)

    # 3. Read Audio
    try:
        fs, raw_data = wavfile.read(wav_path)
    except Exception as e:
        return {"error": f"Failed to read audio: {str(e)}"}

    if len(raw_data.shape) > 1:
        raw_data = raw_data[:, 0] # Convert to mono if stereo
        
    raw_data = raw_data.astype(np.float32)

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

    # 4. Slice and Predict
    predictions = []
    class_counts = {0: 0, 1: 0, 2: 0}
    
    max_stress_confidence = -1
    worst_window_tensor = None
    worst_window_start_idx = 0
    worst_class_pred = 0
    
    with torch.no_grad():
        # Iterate through the wav file in 1,000-sample chunks
        for start in range(0, len(raw_data) - TARGET_LENGTH + 1, TARGET_LENGTH):
            window = raw_data[start:start + TARGET_LENGTH]
            
            signal_tensor = torch.tensor(window, dtype=torch.float32).to(device)
            mel = mel_spectrogram(signal_tensor)
            mel_db = amplitude_to_db(mel)
            mel_db_input = mel_db.unsqueeze(0).unsqueeze(0) 
            
            output = model(mel_db_input)
            
            # Apply softmax to get proper probabilities across the 3 classes
            probs = torch.softmax(output, dim=1).squeeze()
            confidence, pred_class_idx = torch.max(probs, dim=0)
            
            pred_class = pred_class_idx.item()
            conf_val = confidence.item()
            
            class_counts[pred_class] += 1
            
            predictions.append({
                "window_index": sum(class_counts.values()) - 1,
                "prediction_id": pred_class,
                "prediction_label": CLASS_MAP[pred_class],
                "confidence": round(conf_val * 100, 2)
            })
            
            # Track the highest confidence STRESS event (Cut or Dry) for Grad-CAM
            if pred_class in [1, 2] and conf_val > max_stress_confidence:
                max_stress_confidence = conf_val
                worst_window_tensor = signal_tensor 
                worst_window_start_idx = start
                worst_class_pred = pred_class

    # --- 5. GENERATE GRAD-CAM HEATMAP (On worst stress event) ---
    # --- 5. GENERATE GRAD-CAM HEATMAP (On worst stress event) ---
    heatmap_base64 = None
    if worst_window_tensor is not None:
        cam_data = {'activations': None, 'gradients': None}

        def forward_hook(module, input, output):
            cam_data['activations'] = output

        def backward_hook(module, grad_input, grad_output):
            cam_data['gradients'] = grad_output[0]

        target_layer = model.resnet.layer4[-1].conv2
        hook_f = target_layer.register_forward_hook(forward_hook)
        hook_b = target_layer.register_full_backward_hook(backward_hook)

        with torch.enable_grad():
            mel = mel_spectrogram(worst_window_tensor)
            mel_db = amplitude_to_db(mel)
            mel_db_input = mel_db.unsqueeze(0).unsqueeze(0)
            
            worst_mel_db_np = mel_db.cpu().detach().numpy().squeeze() 
            
            mel_db_input.requires_grad_()
            output = model(mel_db_input)
            
            model.zero_grad()
            output[0, worst_class_pred].backward() 

        hook_f.remove()
        hook_b.remove()

        gradients = cam_data['gradients']
        activations = cam_data['activations']

        if gradients is not None and activations is not None:
            pooled_gradients = torch.mean(gradients, dim=[0, 2, 3])
            for i in range(activations.shape[1]):
                activations[:, i, :, :] *= pooled_gradients[i]
                
            heatmap = torch.mean(activations, dim=1) # Shape: [1, H, W]
            heatmap = F.relu(heatmap) 
            if torch.max(heatmap) > 0:
                heatmap = heatmap / (torch.max(heatmap) + 1e-8)
            
            # Ensure 4D shape [Batch=1, Channel=1, H, W] explicitly before interpolation
            if heatmap.dim() == 2:
                heatmap = heatmap.unsqueeze(0).unsqueeze(0)
            elif heatmap.dim() == 3:
                heatmap = heatmap.unsqueeze(1)
                
            heatmap = F.interpolate(
                heatmap, 
                size=(int(worst_mel_db_np.shape[0]), int(worst_mel_db_np.shape[1])), 
                mode='bilinear', 
                align_corners=False
            )
            heatmap = heatmap.squeeze().cpu().detach().numpy()
            
            fig, ax = plt.subplots(figsize=(6, 2))
            ax.imshow(worst_mel_db_np, aspect='auto', origin='lower', cmap='magma')
            ax.imshow(heatmap, aspect='auto', origin='lower', cmap='jet', alpha=0.5) 
            ax.axis('off')
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
            buf.seek(0)
            heatmap_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)
            
    # --- 6. COMPILE SUMMARY AND RETURN ---
    total_windows = sum(class_counts.values())
    
    # Determine overall status based on smart thresholding (15% tolerance)
    cut_count = class_counts[1]
    dry_count = class_counts[2]
    empty_count = class_counts[0]
    total_windows = cut_count + dry_count + empty_count

    if cut_count == 0 and dry_count == 0:
        overall_status = "Normal (Background)"
    elif cut_count > 0 and dry_count > 0:
        # If the minor stress is at least 15% of the major stress, it's a true mix
        if min(cut_count, dry_count) / max(cut_count, dry_count) >= 0.15:
            overall_status = "Mixed Stress"
        elif cut_count > dry_count:
            overall_status = "Stress (Cut)"
        else:
            overall_status = "Stress (Dehydration)"
    elif cut_count > 0:
        overall_status = "Stress (Cut)"
    elif dry_count > 0:
        overall_status = "Stress (Dehydration)"
    else:
        overall_status = "Normal (Background)"

    # Reduce downsample rate for UI graph payload
    visual_downsample = 10 
    visual_signal = raw_data[::visual_downsample]

    # --- 1. CALCULATE SCIENTIFIC CHART METRICS ---
    signal_array = np.array(visual_signal)
    
    # RMS Envelope: Calculates the energy power of the wave
    window_size = max(1, len(signal_array) // 100)
    squared_signal = np.square(signal_array)
    rms_data = np.sqrt(np.convolve(squared_signal, np.ones(window_size)/window_size, mode='same'))
    
    # Adaptive Noise Floor: Calculates the ambient background static
    ambient_threshold = float(np.median(rms_data) * 1.5)
    noise_floor_data = np.full(len(signal_array), ambient_threshold)

    # --- 2. GENERATE BASELINE HEATMAP ---
    if overall_status == "Normal (Background)":
        plt.figure(figsize=(10, 2))
        # Use the downsampled sample rate for the visual spectrogram
        plt.specgram(signal_array, Fs=SAMPLE_RATE/visual_downsample, cmap='viridis', NFFT=256, noverlap=128)
        plt.axis('off')
        plt.tight_layout(pad=0)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close()
        buf.seek(0)
        heatmap_base64 = base64.b64encode(buf.read()).decode('utf-8')

    result = {
        "file": Path(wav_path).name,
        "total_audio_windows": total_windows,
        "class_breakdown": {
            "empty_pot_count": class_counts[0],
            "tomato_cut_count": class_counts[1],
            "tomato_dry_count": class_counts[2]
        },
        "overall_status": overall_status,
        "detailed_predictions": predictions,
        "signal_data": visual_signal.tolist(),
        "rms_data": rms_data.tolist(),                # New array
        "noise_floor_data": noise_floor_data.tolist(),  # New array
        "xai_heatmap": heatmap_base64,
        "worst_stress_event": {
            "type": CLASS_MAP[worst_class_pred] if worst_window_tensor is not None else "None",
            "start_sec": worst_window_start_idx / fs,                
            "end_sec": (worst_window_start_idx + TARGET_LENGTH) / fs
        }
    }
    
    return result   

if __name__ == "__main__":
    # Point this to a raw 500kHz WAV file to test
    sample_wav = "../data/raw/bioacoustics/test_sample.wav"
    
    if Path(sample_wav).exists():
        print("Running 3-Class Bioacoustic Pipeline...\n")
        output = predict_wav(sample_wav)
        
        # Strip out the heavy signal data and base64 string for clean terminal printing
        output.pop("signal_data", None)
        if output.get("xai_heatmap"):
            output["xai_heatmap"] = "[BASE64_IMAGE_STRING_HIDDEN]"
            
        print(json.dumps(output, indent=4))
    else:
        print(f"Please update the 'sample_wav' path at the bottom of the script to test a file.")