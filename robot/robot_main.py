from machine import Pin, PWM, time_pulse_us
import network, socket, time

# ===== UART SETUP =====
from machine import UART
# Assuming UART 2 on ESP32/STM32. Adjust pins as necessary for your board.
uart = UART(2, baudrate=115200)

# ===== MOTOR =====
IN1 = Pin(25, Pin.OUT)
IN2 = Pin(26, Pin.OUT)
IN3 = Pin(27, Pin.OUT)
IN4 = Pin(14, Pin.OUT)

# ===== ULTRASONIC =====
TRIG = Pin(33, Pin.OUT)
ECHO = Pin(32, Pin.IN)

# ===== IR =====
ir_left  = Pin(35, Pin.IN)
ir_right = Pin(34, Pin.IN)

# ===== SERVOS =====
base     = PWM(Pin(18), freq=50)
shoulder = PWM(Pin(19), freq=50)
elbow    = PWM(Pin(21), freq=50)
wrist    = PWM(Pin(22), freq=50)

# ===== SERVO ANGLES =====
b, s, e, w = 90, 115, 115, 90

# ===== LIMITS =====
BASE_MIN,  BASE_MAX  = 40, 140
SHLDR_MIN, SHLDR_MAX = 40, 140
ELBW_MIN,  ELBW_MAX  = 40, 140
WRST_MIN,  WRST_MAX  = 40, 140

INV_SHOULDER = True
INV_ELBOW    = True

# ===== STATE =====
mode        = "MANUAL"   # "MANUAL" or "AUTO"
armMode     = False       # AUTO only: True when arm sequence is running
current_cmd = 'S'         # MANUAL only: last held command

# ===== SERVO HELPERS =====
def angle_to_duty(angle):
    return int(40 + (angle / 180) * 115)

def set_servo(pwm, angle):
    pwm.duty(angle_to_duty(angle))

def clamp(val, mn, mx):
    return max(mn, min(mx, val))

def smooth_servo(pwm, pos, target, invert=False):
    final = 180 - target if invert else target
    step  = 1
    if pos < final:
        for i in range(pos, final, step):
            set_servo(pwm, i)
            time.sleep(0.02)
    else:
        for i in range(pos, final, -step):
            set_servo(pwm, i)
            time.sleep(0.02)
    return final

def move_base(target):
    global b
    if b < target:
        for i in range(b, target, 2):
            set_servo(base, i)
            time.sleep(0.02)
    else:
        for i in range(b, target, -2):
            set_servo(base, i)
            time.sleep(0.02)
    b = target

# ===== MOTOR SPEED (0.0 to 1.0) =====
MOTOR_SPEED = 0.5   # <-- Change this value to control speed

ENA = PWM(Pin(25), freq=1000)   # ← adjust pin numbers to match
ENB = PWM(Pin(14), freq=1000)   #   your actual EN pins

def set_speed(speed=MOTOR_SPEED):
    duty = int(speed * 1023)
    ENA.duty(duty)
    ENB.duty(duty)

def forward():  set_speed(); IN1.value(0); IN2.value(1); IN3.value(0); IN4.value(1)
def backward(): set_speed(); IN1.value(1); IN2.value(0); IN3.value(1); IN4.value(0)
def left():     set_speed(); IN1.value(1); IN2.value(0); IN3.value(0); IN4.value(1)
def right():    set_speed(); IN1.value(0); IN2.value(1); IN3.value(1); IN4.value(0)
def stop():     ENA.duty(0); ENB.duty(0); IN1.value(0); IN2.value(0); IN3.value(0); IN4.value(0)

# ===== ULTRASONIC =====
def get_distance():
    TRIG.value(0); time.sleep_us(2)
    TRIG.value(1); time.sleep_us(10); TRIG.value(0)
    duration = time_pulse_us(ECHO, 1, 30000)
    if duration < 0:
        return 0
    return (duration * 0.034) / 2

# ===== STABLE RANGE CHECK =====
def is_in_range():
    count = 0
    for _ in range(5):
        d = get_distance()
        if 10 <= d <= 15:
            count += 1
        time.sleep(0.05)
    return count >= 3

# ===== IR =====
def detect_left():
    return ir_left.value() == 0

def detect_right():
    return ir_right.value() == 0

# ===== ARM SEQUENCES (AUTO) =====
def lift_up():
    global s, e, w
    s = smooth_servo(shoulder, s, 88,  INV_SHOULDER)
    e = smooth_servo(elbow,    e, 88,  INV_ELBOW)
    w = smooth_servo(wrist,    w, 100)

def go_home():
    global s, e, w
    s = smooth_servo(shoulder, s, 115, INV_SHOULDER)
    e = smooth_servo(elbow,    e, 115, INV_ELBOW)
    w = smooth_servo(wrist,    w, 90)

def clean_range(left_angle, right_angle):
    for _ in range(3):
        move_base(left_angle)
        move_base(right_angle)
    move_base((left_angle + right_angle) // 2)

def smart_clean():
    global b
    direction = 1
    while True:
        if detect_right():
            clean_range(BASE_MIN, b)
            break
        if detect_left():
            clean_range(b, BASE_MAX)
            break
        b += direction
        b = clamp(b, BASE_MIN, BASE_MAX)
        set_servo(base, b)
        time.sleep(0.03)
        if b >= BASE_MAX:
            direction = -1
        if b <= BASE_MIN:
            direction = 1

# ===== AUTO MODE FUNCTIONS =====
def run_arm():
    global armMode, s, e, w
    stop()
    lift_up()
    time.sleep(0.5)
    smart_clean()
    go_home()
    time.sleep(2)
    armMode = False

def run_car():
    global armMode
    d = get_distance()
    print("Distance:", d)
    if d > 15:
        forward()
    elif 10 <= d <= 15:
        if is_in_range():
            stop()
            armMode = True
    elif 0 < d < 10:
        backward()

# ===== MANUAL APPLY COMMAND =====
def apply_cmd(c):
    global b, s, e, w

    # Motor
    if   c == 'F': forward()
    elif c == 'B': backward()
    elif c == 'L': left()
    elif c == 'R': right()
    elif c == 'S': stop()

# ===== INIT SERVOS =====
set_servo(base,     b)
set_servo(shoulder, 180 - s if INV_SHOULDER else s)
set_servo(elbow,    180 - e if INV_ELBOW    else e)
set_servo(wrist,    w)
time.sleep(1)

print("Ready. Listening to UART for commands...")

# ===== MAIN LOOP =====
while True:

    # --- Check UART request (non-blocking) ---
    if uart.any():
        try:
            req = uart.read().decode('utf-8').strip()
        except:
            req = ""
            
        if req:
            print("UART Received:", req)
            # Mode switch
            if   'AUTO'   in req: mode = "AUTO";   armMode = False; current_cmd = 'S'; stop()
            elif 'MANUAL' in req: mode = "MANUAL"; armMode = False; current_cmd = 'S'; stop()
    
            # Manual commands (only update when in MANUAL mode)
            elif mode == "MANUAL":
                # 1. Handle slider commands (e.g. BASE=90)
                if "BASE=" in req:
                    try:
                        val = int(req.split("BASE=")[1].split()[0])
                        b = clamp(val, 0, 180) # Slider is 0-180
                        set_servo(base, b)
                    except: pass
                elif "SHLDR=" in req:
                    try:
                        val = int(req.split("SHLDR=")[1].split()[0])
                        s = clamp(val, 0, 180)
                        set_servo(shoulder, 180 - s if INV_SHOULDER else s)
                    except: pass
                elif "ELBW=" in req:
                    try:
                        val = int(req.split("ELBW=")[1].split()[0])
                        e = clamp(val, 0, 180)
                        set_servo(elbow, 180 - e if INV_ELBOW else e)
                    except: pass
                elif "WRST=" in req:
                    try:
                        val = int(req.split("WRST=")[1].split()[0])
                        w = clamp(val, 0, 180)
                        set_servo(wrist, w)
                    except: pass
                    
                # 2. Handle movement commands
                else:
                    cmd = None
                    for c in ['F','B','L','R','S','H']:
                        if c in req:
                            cmd = c
                            break
                    if cmd == 'H':
                        current_cmd = 'S'   # servo release → hold position
                    elif cmd is not None:
                        current_cmd = cmd

    # --- Execute mode ---
    if mode == "AUTO":
        if armMode:
            run_arm()      # blocking arm sequence, sets armMode=False when done
        else:
            run_car()      # checks distance, may set armMode=True

    else:  # MANUAL
        apply_cmd(current_cmd)   # continuous command every loop

    time.sleep(0.05)
