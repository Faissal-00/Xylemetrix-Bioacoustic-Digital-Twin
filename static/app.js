import * as THREE from 'three';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { MTLLoader } from 'three/addons/loaders/MTLLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// --- 1. SETUP 3D SCENE ---
const container = document.getElementById('canvas-container');
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 2000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); 
renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement);

const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
scene.add(ambientLight);
const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2);
directionalLight.position.set(50, 100, 50);
scene.add(directionalLight);

const controls = new OrbitControls(camera, renderer.domElement);
window.zoomCamera = (val) => { 
    camera.position.z += val; 
    if(camera.position.z < 2) camera.position.z = 2; 
};

// --- 2. SECTOR ROUTING STATE ---
window.activeSectorId = 'Field_1'; // Defaults to the first field
window.farmSectors = {};           // Will store all 6 fields and their plants

// --- 3. LOAD MODELS & BUILD MACRO FARM ---
const mtlLoader = new MTLLoader();
mtlLoader.setPath('/static/');
mtlLoader.load('plant_model.mtl?v=' + Date.now(), function (materials) {
    materials.preload();
    const objLoader = new OBJLoader();
    objLoader.setMaterials(materials);
    objLoader.setPath('/static/');
    
    objLoader.load('plant_model.obj?v=' + Date.now(), function (plantObject) {
        let templatePlant = plantObject;
        
        templatePlant.traverse(function (child) {
            if (child.isMesh) {
                child.castShadow = true;
                child.receiveShadow = true;
                if (child.material) {
                    const fixMaterial = (mat) => {
                        mat.transparent = true;
                        mat.alphaTest = 0.5;         
                        mat.side = THREE.DoubleSide; 
                        mat.userData.originalColor = mat.color.clone();
                    };
                    Array.isArray(child.material) ? child.material.forEach(fixMaterial) : fixMaterial(child.material);
                }
            }
        });

        const box = new THREE.Box3().setFromObject(templatePlant);
        const size = box.getSize(new THREE.Vector3());
        const scaleFactor = 16 / Math.max(size.x, size.y, size.z); 
        templatePlant.scale.set(scaleFactor, scaleFactor, scaleFactor);
        const newCenter = new THREE.Box3().setFromObject(templatePlant).getCenter(new THREE.Vector3());
        templatePlant.position.sub(newCenter);
        
        // NOW LOAD SOIL SO WE CAN BUILD EVERYTHING TOGETHER
        const gltfLoader = new GLTFLoader();
        gltfLoader.setPath('/static/');
        gltfLoader.load('clean_soil_land.glb', function (gltf) {
            const templateSoil = gltf.scene;
            templateSoil.scale.set(5, 5, 5); 
            
            buildMacroFarm(templatePlant, templateSoil);
        });
    });
});

// --- 3.5. CAMERA ANIMATION STATE VARIABLES ---
// let targetCameraPos = new THREE.Vector3(90, 80, 150); 
let targetCameraPos = new THREE.Vector3(90, 80, 130);
let targetLookAt = new THREE.Vector3(0, 0, 0);         
let isAnimatingCamera = false; 
let isMacroView = true; // 👇 NEW: Track whether we are zoomed in or out 👇

function buildMacroFarm(templatePlant, templateSoil) {
    const fieldRows = 2; 
    const fieldCols = 3; 
    const fieldSpacingX = 55.0; 
    const fieldSpacingZ = 65.0; 
    
    let fieldIndex = 1;

    for (let fr = 0; fr < fieldRows; fr++) {
        for (let fc = 0; fc < fieldCols; fc++) {
            const fieldId = `Field_${fieldIndex}`;
            
            const fPosX = (fc - (fieldCols - 1) / 2) * fieldSpacingX; 
            const fPosZ = (fr - (fieldRows - 1) / 2) * fieldSpacingZ;

            window.farmSectors[fieldId] = { 
                plants: [],
                centerX: fPosX,
                centerZ: fPosZ
            };

            const soilClone = templateSoil.clone();
            soilClone.position.set(fPosX, -2, fPosZ); 
            
            soilClone.userData.fieldId = fieldId;
            soilClone.traverse(child => { if (child.isMesh) child.userData.fieldId = fieldId; });
            scene.add(soilClone);

            const pRows = 4; 
            const pCols = 3; 
            const pSpacingX = 12.0;   
            const pSpacingZ = 10.0;   
            const pHeight = -0.8; 
            
            for (let r = 0; r < pRows; r++) {
                for (let c = 0; c < pCols; c++) {
                    const plantClone = templatePlant.clone();
                    
                    plantClone.traverse((child) => {
                        if (child.isMesh) {
                            child.userData.fieldId = fieldId;
                            if (child.material) {
                                if (Array.isArray(child.material)) {
                                    child.material = child.material.map(m => m.clone());
                                    child.material.forEach(m => m.userData.originalColor = m.color.clone());
                                } else {
                                    child.material = child.material.clone();
                                    child.material.userData.originalColor = child.material.color.clone();
                                }
                            }
                        }
                    });
                    
                    const localX = (c - (pCols - 1) / 2) * pSpacingX; 
                    const localZ = (r - (pRows - 1) / 2) * pSpacingZ;
                    
                    plantClone.position.set(fPosX + localX, pHeight, fPosZ + localZ); 
                    scene.add(plantClone);
                    window.farmSectors[fieldId].plants.push(plantClone);
                }
            } // <-- END OF PLANT LOOP
            
            // 👇 NEW: STANDALONE IOT SENSOR STATION IN THE CENTER OF THE FIELD 👇
            
            // 1. The Steel Mounting Pole (Slimmer and slightly shorter)
            const poleGeo = new THREE.CylinderGeometry(0.2, 0.2, 12, 16); 
            const poleMat = new THREE.MeshStandardMaterial({ color: 0x888888, metalness: 0.9, roughness: 0.2 });
            const poleMesh = new THREE.Mesh(poleGeo, poleMat);
            poleMesh.position.set(fPosX, pHeight + 6, fPosZ); 
            
            // 2. The Sleek Industrial Sensor Node (Slimmer, matte white/silver casing)
            const sensorGeo = new THREE.BoxGeometry(1.2, 3.5, 1.2); 
            const sensorMat = new THREE.MeshStandardMaterial({ color: 0xf8f9fa, metalness: 0.2, roughness: 0.8 }); 
            const sensorMesh = new THREE.Mesh(sensorGeo, sensorMat);
            sensorMesh.position.set(0, 6, 0); 
            poleMesh.add(sensorMesh);

            // 3. The IoT Antenna (Instantly makes it look like a wireless network node)
            const antennaGeo = new THREE.CylinderGeometry(0.05, 0.05, 2, 8);
            const antennaMat = new THREE.MeshStandardMaterial({ color: 0x222222 });
            const antennaMesh = new THREE.Mesh(antennaGeo, antennaMat);
            antennaMesh.position.set(0.4, 2.5, -0.4); // Mounted on the top back corner
            sensorMesh.add(antennaMesh);
            
            // 4. The High-Tech Cyan LED Indicator (Slightly smaller, moved up)
            const ledGeo = new THREE.CylinderGeometry(0.3, 0.3, 0.1, 16); 
            const ledMat = new THREE.MeshBasicMaterial({ color: 0x00ffcc, transparent: true, opacity: 1 });
            const ledMesh = new THREE.Mesh(ledGeo, ledMat);
            ledMesh.rotation.x = Math.PI / 2; 
            ledMesh.position.set(0, 1.0, 0.65); 
            sensorMesh.add(ledMesh);
            
            // 5. The LED Light Aura
            const ledLight = new THREE.PointLight(0x00ffcc, 1.0, 15);
            ledLight.position.set(0, 1.0, 1.5);
            sensorMesh.add(ledLight);
            
            // Add the entire station to the scene
            scene.add(poleMesh);
            
            // Save the LED materials for the animate() blink loop
            if (!window.sensorLEDs) window.sensorLEDs = [];
            window.sensorLEDs.push(ledMat);
            
            // 👆 END SENSOR STATION LOGIC 👆
            

            fieldIndex++; 
        }
    }
    
    camera.position.copy(targetCameraPos);
    controls.target.copy(targetLookAt);
    controls.update();
}

// --- 3.6. DOUBLE-CLICK RAYCASTER LOGIC ---
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

renderer.domElement.addEventListener('dblclick', (event) => {
    // If already zoomed in, double-click zooms us back out!
    if (!isMacroView) {
        window.resetCameraView();
        return; 
    }

    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(scene.children, true);
    
    if (intersects.length > 0) {
        let clickedFieldId = null;
        
        for (let i = 0; i < intersects.length; i++) {
            if (intersects[i].object.userData.fieldId) {
                clickedFieldId = intersects[i].object.userData.fieldId;
                break;
            }
        }

        if (clickedFieldId) {
            document.getElementById('field-selector').value = clickedFieldId;
            window.activeSectorId = clickedFieldId;

            const sector = window.farmSectors[clickedFieldId];
            
            targetCameraPos.set(sector.centerX + 35, 20, sector.centerZ + 35); 
            targetLookAt.set(sector.centerX, 4, sector.centerZ); 
            
            isAnimatingCamera = true; 
            isMacroView = false; 
            controls.enabled = false; // 👇 Lock mouse controls during flight
            document.getElementById('reset-view-btn').style.display = 'block';
        }
    }
});

window.resetCameraView = function() {
    targetCameraPos.set(120, 80, 150); 
    targetLookAt.set(0, 0, 0);         
    
    isAnimatingCamera = true; 
    isMacroView = true; 
    controls.enabled = false; // 👇 Lock mouse controls during flight
    document.getElementById('reset-view-btn').style.display = 'none';
};

// --- 4. ANIMATION LOOP ---
function animate() {
    requestAnimationFrame(animate);
    
    // 👇 NEW: HARDWARE LED BLINK LOGIC 👇
    if (window.sensorLEDs) {
        const time = Date.now() * 0.002; 
        // Creates a sharp "ping" effect instead of a smooth fade
        const isBlinking = Math.sin(time) > 0.85; 
        const blinkOpacity = isBlinking ? 1.0 : 0.15; 
        window.sensorLEDs.forEach(mat => mat.opacity = blinkOpacity);
    }
    // 👆 END BLINK LOGIC 👆

    if (isAnimatingCamera) {
        camera.position.lerp(targetCameraPos, 0.08); 
        controls.target.lerp(targetLookAt, 0.08);
        
        if (camera.position.distanceTo(targetCameraPos) < 2.0) {
            camera.position.copy(targetCameraPos); 
            controls.target.copy(targetLookAt);
            isAnimatingCamera = false; 
            controls.enabled = true;   
        }
    }
    
    controls.update();
    renderer.render(scene, camera);
}
animate();

// --- 5. TARGETED FIELD STRESS UPDATE FUNCTION ---
window.applyStressToFarm = function(meshTargetColor) {
    const activeSector = window.farmSectors[window.activeSectorId];
    if (!activeSector) return; 

    activeSector.plants.forEach(plant => {
        plant.traverse(function (child) {
            if (child.isMesh && child.material) {
                const updateColor = (mat) => {
                    if (meshTargetColor !== null) {
                        mat.color.setHex(meshTargetColor);
                    } else {
                        if (mat.userData.originalColor) mat.color.copy(mat.userData.originalColor);
                    }
                };
                Array.isArray(child.material) ? child.material.forEach(updateColor) : updateColor(child.material);
            }
        });
    });
};

// --- 6. SETUP CHART.JS (AUDIO WAVEFORM) ---
const ctx = document.getElementById('waveformChart').getContext('2d');
const waveformChart = new Chart(ctx, {
    type: 'line',
    data: { 
        labels: [], 
        datasets: [
            { label: 'Raw Acoustic Amplitude', data: [], borderColor: '#3fb950', borderWidth: 1.0, pointRadius: 0, tension: 0.1, order: 3 },
            { label: 'RMS Energy Envelope', data: [], borderColor: 'rgba(88, 166, 255, 0.8)', backgroundColor: 'rgba(88, 166, 255, 0.1)', borderWidth: 2.0, pointRadius: 0, tension: 0.4, fill: true, order: 2 },
            { label: 'Adaptive Noise Floor', data: [], borderColor: 'rgba(248, 81, 73, 0.6)', borderWidth: 1.5, borderDash: [5, 5], pointRadius: 0, tension: 0, order: 1 }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: {
            x: { display: true, grid: { color: '#21262d' }, ticks: { color: '#8b949e', maxTicksLimit: 10 }, title: { display: true, text: 'Time (seconds)', color: '#8b949e', font: { size: 10 } } },
            y: { grid: { color: '#30363d' }, ticks: { color: '#8b949e' }, title: { display: true, text: 'Amplitude', color: '#8b949e', font: { size: 10 } } }
        },
        plugins: { 
            legend: { display: true, labels: { color: '#8b949e', boxWidth: 12 } },
            zoom: { pan: { enabled: true, mode: 'x' }, zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' } },
            annotation: {
                annotations: {
                    focusBox: {
                        type: 'box', display: false, backgroundColor: 'rgba(255, 99, 132, 0.15)', borderColor: 'rgba(255, 99, 132, 0.8)', borderWidth: 1,
                        label: { display: true, content: 'AI FOCUS', color: 'rgba(255, 255, 255, 0.7)', backgroundColor: 'rgba(255, 99, 132, 0.5)', position: 'start' }
                    }
                }
            }
        }
    }
});

// --- 7. DATA FETCHING & HISTORY LOGIC ---
window.historyData = [];
window.loadHistory = async function() {
    try {
        const response = await fetch('/api/history');
        const result = await response.json();
        if (result.status === "success") {
            window.historyData = result.data;
            window.applyFilter();
        }
    } catch (error) {
        console.error("Error loading history:", error);
    }
};

window.applyFilter = function() {
    const statusFilter = document.getElementById('filter-select').value;
    const fieldFilter = document.getElementById('filter-field').value; 
    
    const tbody = document.getElementById('history-body');
    tbody.innerHTML = ""; 

    const filteredData = window.historyData.filter(row => {
        let statusMatch = (statusFilter === "All") ? true : row.overall_status.includes(statusFilter);
        let fieldMatch = (fieldFilter === "All") ? true : (row.field_id === fieldFilter);
        
        return statusMatch && fieldMatch;
    });

    filteredData.forEach(row => {
        const dateObj = new Date(row.timestamp);
        const formattedDate = dateObj.toLocaleString();
        const countsDisplay = `Empty: ${row.empty_pot_count} | Cut: ${row.tomato_cut_count} | Dry: ${row.tomato_dry_count}`;
        
        let classColor = '#888';
        if (row.overall_status.includes('Normal')) classColor = '#3fb950';
        else if (row.overall_status.includes('Dehydration')) classColor = '#f57c00';
        else if (row.overall_status.includes('Cut')) classColor = '#ff7b72';
        else classColor = '#d2a8ff';

        const displayField = row.field_id ? row.field_id.replace('_', ' 0').toUpperCase() : "UNKNOWN";

        const tr = document.createElement('tr');
        tr.style.borderBottom = "1px solid #333";
        tr.innerHTML = `
            <td style="padding: 12px;">${formattedDate}</td>
            <td style="padding: 12px; font-weight: bold; color: #58a6ff;">${displayField}</td>
            <td style="padding: 12px; font-family: monospace;">${row.filename}</td>
            <td style="padding: 12px; color: ${classColor}; font-weight: bold;">${row.overall_status}</td>
            <td style="padding: 12px; font-size: 12px;">${countsDisplay}</td>
            <td style="padding: 12px;">${row.inference_time_ms} ms</td>
            <td style="padding: 12px; text-align: center;">
                <button onclick="deleteRecord(${row.id})" style="background: none; border: none; color: #888; cursor: pointer; font-size: 16px;" title="Delete Record">✖</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
};

window.exportCSV = function() {
    const statusFilter = document.getElementById('filter-select').value;
    const fieldFilter = document.getElementById('filter-field').value;

    const dataToExport = window.historyData.filter(row => {
        let statusMatch = (statusFilter === "All") ? true : row.overall_status.includes(statusFilter);
        let fieldMatch = (fieldFilter === "All") ? true : (row.field_id === fieldFilter);
        return statusMatch && fieldMatch;
    });

    if (dataToExport.length === 0) return alert("No data to export for this filter!");
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "ID,Timestamp,Field_Node,Filename,Overall_Status,Empty_Pot_Count,Tomato_Cut_Count,Tomato_Dry_Count,Inference_Time_ms\n";
    
    dataToExport.forEach(row => {
        const rowData = [
            row.id, 
            row.timestamp, 
            row.field_id || "Unknown",
            row.filename, 
            `"${row.overall_status}"`, 
            row.empty_pot_count, 
            row.tomato_cut_count, 
            row.tomato_dry_count, 
            row.inference_time_ms
        ];
        csvContent += rowData.join(",") + "\n";
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `plantpulse_${fieldFilter}_${statusFilter}_logs.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

window.deleteRecord = async function(id) {
    if(!confirm("Are you sure you want to delete this specific record?")) return;
    await fetch(`/api/history/${id}`, { method: 'DELETE' });
    window.loadHistory(); 
};

window.clearHistory = async function() {
    if(!confirm("WARNING: Are you sure you want to delete ALL research history? This cannot be undone.")) return;
    await fetch(`/api/history`, { method: 'DELETE' });
    window.loadHistory(); 
};

// --- 8. HANDLE API CALL & INFERENCE ---
window.processAudio = async function() {
    const fileInput = document.getElementById('audioUpload');
    if (!fileInput.files.length) return alert("Select a .wav file.");

    const statusBar = document.getElementById('ai-prediction');
    statusBar.innerText = "PROCESSING ULTRASONIC AUDIO MATRICES...";
    statusBar.className = "";

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("field_id", window.activeSectorId);

    try {
        const response = await fetch("/predict", { method: "POST", body: formData });
        const data = await response.json();
        
        if (data.error) {
            statusBar.innerText = "[SYSTEM ERROR]: " + data.error;
            statusBar.className = "alert-active";
            return;
        }

        const realData = data.signal_data;
        const sampleRateHz = 500000; 
        const downsampleRatio = 10;  
        const secondsPerPoint = downsampleRatio / sampleRateHz; 

        waveformChart.data.labels = Array.from({ length: realData.length }, (_, i) => (i * secondsPerPoint).toFixed(4) + 's');
        waveformChart.data.datasets[0].data = realData;
        waveformChart.data.datasets[1].data = data.rms_data;
        waveformChart.data.datasets[2].data = data.noise_floor_data;
        
        const box = waveformChart.options.plugins.annotation.annotations.focusBox;
        let meshTargetColor = null; 
        
        if (data.overall_status === "Normal (Background)") {
            statusBar.innerHTML = `[AI PREDICTION: <span style="color: #3fb950; font-weight: bold;">NORMAL (BACKGROUND)</span>] - 0 STRESS EVENTS DETECTED`;
            waveformChart.data.datasets[0].borderColor = '#3fb950';
            if (box) box.display = false;
            document.getElementById('xai-panel').style.display = 'flex';
            document.getElementById('heatmap-img').style.filter = "grayscale(80%) sepia(20%) hue-rotate(90deg)"; 
            document.getElementById('heatmap-img').src = 'data:image/png;base64,' + data.xai_heatmap;

        } else if (data.overall_status === "Stress (Dehydration)") {
            statusBar.innerHTML = `[AI PREDICTION: <span style="color: #ffaa00; font-weight: bold;">DEHYDRATION DETECTED</span>] - ${data.class_breakdown.tomato_dry_count} EVENTS LOGGED`;
            waveformChart.data.datasets[0].borderColor = '#ffaa00';
            meshTargetColor = 0xffaa00; 

        } else if (data.overall_status === "Stress (Cut)") {
            statusBar.innerHTML = `[AI PREDICTION: <span class="alert-active" style="color: #ff0000; font-weight: bold;">CRITICAL STRESS (STEM CUT)</span>] - ${data.class_breakdown.tomato_cut_count} EVENTS LOGGED`;
            waveformChart.data.datasets[0].borderColor = '#ff0000'; 
            meshTargetColor = 0xff0000; 

        } else {
            const cutCount = data.class_breakdown.tomato_cut_count;
            const dryCount = data.class_breakdown.tomato_dry_count;
            const cutColor = new THREE.Color(0xff0000); 
            const dryColor = new THREE.Color(0xffaa00); 
            const blendedColor = dryColor.clone().lerp(cutColor, 0.5); 
            
            meshTargetColor = blendedColor.getHex();
            let blendedHex = blendedColor.getHexString();

            statusBar.innerHTML = `[AI PREDICTION: <span style="color: #${blendedHex}; font-weight: bold;">MIXED STRESS</span>] - ${cutCount} CUT | ${dryCount} DRY`;
            waveformChart.data.datasets[0].borderColor = `#${blendedHex}`;
        }

        // Send the color update to the currently selected field dropdown!
        window.applyStressToFarm(meshTargetColor);

        if (data.xai_heatmap && (data.overall_status.includes("Stress") || data.overall_status.includes("Mixed"))) {
            document.getElementById('xai-panel').style.display = 'flex';
            document.getElementById('heatmap-img').src = 'data:image/png;base64,' + data.xai_heatmap;
            document.getElementById('heatmap-img').style.filter = "none"; 
            
            if (box && data.worst_stress_event) {
                box.display = true;
                box.xMin = data.worst_stress_event.start_sec.toFixed(4) + 's';
                box.xMax = data.worst_stress_event.end_sec.toFixed(4) + 's';
                
                let boxColor = 'rgba(255, 99, 132, 0.8)';
                let boxBg = 'rgba(255, 99, 132, 0.15)';
                let labelText = 'CRITICAL POP DETECTED';

                if (data.overall_status.includes("Dehydration")) {
                    boxColor = 'rgba(245, 124, 0, 0.8)';
                    boxBg = 'rgba(245, 124, 0, 0.15)';
                    labelText = 'DEHYDRATION EVENT';
                }

                box.backgroundColor = boxBg; 
                box.borderColor = boxColor;
                box.label.content = labelText;
                box.label.backgroundColor = boxColor;
            }
        }

        waveformChart.update();
        waveformChart.resize(); 
        window.loadHistory();

    } catch (error) {
        console.error("Javascript Error:", error); 
        document.getElementById('ai-prediction').innerText = "[SYSTEM ERROR - Check Browser Console]";
    }
};

// --- 9. DRAGGABLE DIVIDER LOGIC ---
const divider = document.getElementById('divider');
const chartPanel = document.getElementById('chart-panel');
let isDragging = false;

divider.addEventListener('mousedown', (e) => {
    isDragging = true;
    document.body.style.cursor = 'col-resize';
});

document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const newWidth = (e.clientX / window.innerWidth) * 100;
    if (newWidth > 20 && newWidth < 80) { 
        chartPanel.style.width = `${newWidth}%`;
        waveformChart.resize();
        camera.aspect = document.getElementById('twin-panel').clientWidth / document.getElementById('twin-panel').clientHeight;
        camera.updateProjectionMatrix();
        // Syntax fix applied here! 
        renderer.setSize(document.getElementById('twin-panel').clientWidth, document.getElementById('twin-panel').clientHeight);
    }
});

document.addEventListener('mouseup', () => {
    isDragging = false;
    document.body.style.cursor = 'default';
});

// --- 10. TAB ROUTING LOGIC ---
window.switchTab = function(target) {
    const liveView = document.getElementById('view-live');
    const historyView = document.getElementById('view-history');
    const liveTab = document.getElementById('tab-live');
    const historyTab = document.getElementById('tab-history');

    if (target === 'live') {
        liveView.style.display = 'flex';
        historyView.style.display = 'none';
        liveTab.style.color = '#4ade80';
        liveTab.style.borderBottom = '2px solid #4ade80';
        historyTab.style.color = '#888';
        historyTab.style.borderBottom = 'none';
    } else if (target === 'history') {
        liveView.style.display = 'none';
        historyView.style.display = 'block';
        historyTab.style.color = '#4ade80';
        historyTab.style.borderBottom = '2px solid #4ade80';
        liveTab.style.color = '#888';
        liveTab.style.borderBottom = 'none';
        window.loadHistory(); 
    }
};