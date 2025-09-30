#IMPORTANT this version does NOT have safe boundaries implemented don't use

'''
import serial
import time

# === Configure Your Serial Port Here ===
PORT = 'COM3'  # <- Change this to match your actual port (e.g., COM4, /dev/ttyUSB0)

# === Open Serial Port ===
ser = serial.Serial(
    port=PORT,
    baudrate=9600,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1
)

def send_cmd(cmd, delay=0.2):
    """Send a command to the controller and return its response."""
    full_cmd = cmd + '\r'
    ser.write(full_cmd.encode())
    time.sleep(delay)
    response = ser.read_all().decode(errors='ignore').strip()
    print(f"> {cmd}\n< {response}")
    return response

def mm_to_pulses(mm):
    return int(mm * 1600)

def move_axis(axis, distance_mm):
    """Move axis (X, Y, or Z) by distance in mm (positive or negative)."""
    pulses = mm_to_pulses(distance_mm)
    direction = '+' if pulses >= 0 else '-'
    cmd = f"{axis.upper()}{direction}{abs(pulses)}"
    return send_cmd(cmd)

# === Initialization: Handshake ===
send_cmd('?R')  # Handshake. Controller should return "OK"

# === Set Speed (0–255) ===
send_cmd('V70')  # Set speed to 70

# === Example Moves ===
move_axis('x', 50.0)   # Move X forward 50mm
time.sleep(0.5)
move_axis('y', -30)  # Move Y backward 30mm
time.sleep(0.5)
move_axis('z', 10.0)   # Move Z up 10mm

# === Query Positions ===
send_cmd('?X')
send_cmd('?Y')
send_cmd('?Z')

# === Return to Origin ===
# Mode 0 = stop after zeroing, Mode 1 = return to last position
send_cmd('HX0')  # Home X axis
send_cmd('HY0')  # Home Y axis

# === Query Return-to-Origin Status ===
send_cmd('?H')  # Returns something like H100000 (X has homed)

# === Stop All Motion ===
send_cmd('S')  # Emergency stop

# === Close Serial Port ===
ser.close()

'''