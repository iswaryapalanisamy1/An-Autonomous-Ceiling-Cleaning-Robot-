let camIp = "192.168.1.100";
let robotIp = "192.168.1.101";
let isConnected = false;
let isAutoMode = false;
let brushActive = false;
let vacuumActive = false;

// DOM Elements
const camIpInput = document.getElementById('cam-ip');
const robotIpInput = document.getElementById('robot-ip');
const connectBtn = document.getElementById('connect-btn');
const connDot = document.getElementById('conn-dot');
const connText = document.getElementById('conn-text');
const cameraStream = document.getElementById('camera-stream');

const modeToggle = document.getElementById('mode-toggle');
const modeText = document.getElementById('mode-text');
const modeDesc = document.getElementById('mode-desc');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Setup connection button
    connectBtn.addEventListener('click', connectToRobot);

    // Setup mode toggle
    modeToggle.addEventListener('change', (e) => {
        isAutoMode = e.target.checked;
        if(isAutoMode) {
            modeText.innerText = "Auto Mode";
            modeDesc.innerText = "Robot is navigating autonomously.";
            sendCommand('AUTO');
        } else {
            modeText.innerText = "Manual Mode";
            modeDesc.innerText = "User controls movement.";
            sendCommand('MANUAL');
            sendCommand('S'); // Stop immediately when switching to manual
        }
    });

    // Start simulated sensor data fetching
    setInterval(fetchSensorData, 1000);
});

// Connect to ESP32
function connectToRobot() {
    camIp = camIpInput.value.trim();
    robotIp = robotIpInput.value.trim();
    
    if(!camIp) {
        alert("Please enter a valid IP address for the Camera (ESP32-CAM).");
        return;
    }

    // Set camera stream URL
    cameraStream.src = `http://${camIp}/`;
    
    // Simulate connection for UI feedback immediately
    updateConnectionStatus(true);
}

function updateConnectionStatus(status) {
    isConnected = status;
    if(status) {
        connDot.classList.add('connected');
        connText.innerText = "Connected";
    } else {
        connDot.classList.remove('connected');
        connText.innerText = "Disconnected";
    }
}

// Send Command via HTTP GET
function sendCommand(cmd) {
    if(!isConnected) return;
    if(isAutoMode && cmd !== 'MANUAL' && cmd !== 'AUTO') {
        console.log("Ignored movement command in Auto Mode");
        return;
    }

    console.log(`Sending command: ${cmd}`);
    
    fetch(`http://${camIp}/action?go=${cmd}`, { mode: 'no-cors' })
        .catch(err => {
            console.error("Command failed", err);
            updateConnectionStatus(false);
        });
}

// Arm Controls (Sliders)
function updateArm(joint, value) {
    document.getElementById(`${joint}-val`).innerHTML = `${value}&deg;`;
    
    let cmd = "";
    if (joint === 'base') cmd = `BASE=${value}`;
    else if (joint === 'shoulder') cmd = `SHLDR=${value}`;
    else if (joint === 'elbow') cmd = `ELBW=${value}`;
    else if (joint === 'head') cmd = `WRST=${value}`; // Map head to wrist in micropython code

    sendCommand(cmd);
}

// Cleaning Controls
function toggleBrush() {
    brushActive = !brushActive;
    const btn = document.querySelector('.brush-btn');
    if(brushActive) {
        btn.classList.add('active');
        sendCommand('CLEAN_BRUSH_ON'); // You can add logic for this in micropython later if needed
    } else {
        btn.classList.remove('active');
        sendCommand('CLEAN_BRUSH_OFF');
    }
}

function toggleVacuum() {
    vacuumActive = !vacuumActive;
    const btn = document.querySelector('.vacuum-btn');
    if(vacuumActive) {
        btn.classList.add('active');
        sendCommand('CLEAN_VAC_ON');
    } else {
        btn.classList.remove('active');
        sendCommand('CLEAN_VAC_OFF');
    }
}

// Fetch Sensor Data
function fetchSensorData() {
    if(!isConnected) return;

    // Simulated data for demonstration
    const mockData = {
        distance: Math.floor(Math.random() * 50) + 10, // 10-60 cm
        irEdge: Math.random() > 0.8 ? "Edge Detected!" : "Safe",
        limitSwitch: Math.random() > 0.9 ? "Closed (Hit)" : "Open",
        battery: Math.floor(Math.random() * 20) + 60 // 60-80%
    };
    updateSensors(mockData);
}

function updateSensors(data) {
    // Distance
    document.getElementById('dist-val').innerText = `${data.distance} cm`;
    
    // IR Edge
    const irElem = document.getElementById('ir-val');
    irElem.innerText = data.irEdge;
    if(data.irEdge !== "Safe") {
        irElem.className = "warn-text";
    } else {
        irElem.className = "safe-text";
    }

    // Limit Switch
    const limitElem = document.getElementById('limit-val');
    limitElem.innerText = data.limitSwitch;
    if(data.limitSwitch !== "Open") {
        limitElem.className = "warn-text";
    } else {
        limitElem.className = "";
    }

    // Battery
    document.getElementById('battery-level').innerText = `${data.battery}%`;
}

// Keyboard Controls (WASD / Arrows)
document.addEventListener('keydown', (e) => {
    if(!isConnected || isAutoMode || document.activeElement === camIpInput || document.activeElement === robotIpInput) return;
    
    switch(e.key.toLowerCase()) {
        case 'w':
        case 'arrowup': sendCommand('F'); break;
        case 's':
        case 'arrowdown': sendCommand('B'); break;
        case 'a':
        case 'arrowleft': sendCommand('L'); break;
        case 'd':
        case 'arrowright': sendCommand('R'); break;
    }
});

document.addEventListener('keyup', (e) => {
    if(!isConnected || isAutoMode || document.activeElement === camIpInput || document.activeElement === robotIpInput) return;
    
    switch(e.key.toLowerCase()) {
        case 'w':
        case 'arrowup': 
        case 's':
        case 'arrowdown': 
        case 'a':
        case 'arrowleft': 
        case 'd':
        case 'arrowright': 
            sendCommand('H'); // Send H to release/stop motors
            break;
    }
});
