#IMPORTANT: Identical implementation to Test v1 py unsafe dont use.py BUT with safe bound motor move limits implemented

import serial
import time

# === SERIAL CONFIGURATION ===
PORT = 'COM3'  # Change to your actual COM port

ser = serial.Serial(
    port=PORT,
    baudrate=9600,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1
)

# === LIMITS (mm) ===
MIN_MM = 0
MAX_MM = 100

# === UNIT CONVERSION ===
def mm_to_pulses(mm):
    return int(mm * 1600)

def pulses_to_mm(pulses):
    return int(pulses) / 1600

# === SERIAL COMMAND HELPER ===
def send_cmd(cmd, delay=0.2):
    full_cmd = cmd + '\r'
    ser.write(full_cmd.encode())
    time.sleep(delay)
    response = ser.read_all().decode(errors='ignore').strip()
    print(f"> {cmd}\n< {response}")
    return response

# === POSITION HELPERS ===
def get_position_mm(axis):
    pos_pulses = send_cmd(f'?{axis.upper()}')
    try:
        return pulses_to_mm(int(pos_pulses))
    except ValueError:
        print(f"[!] Could not parse position response: {pos_pulses}")
        return None

# === SAFE MOVE ===
def safe_move(axis, distance_mm):
    axis = axis.upper()
    current_pos = get_position_mm(axis)
    if current_pos is None:
        print(f"[!] Failed to get {axis} position. Aborting move.")
        return

    target_pos = current_pos + distance_mm

    if MIN_MM <= target_pos <= MAX_MM:
        move_axis(axis, distance_mm)
    else:
        print(f"[!] Move aborted. {axis} target {target_pos:.3f} mm is out of bounds ({MIN_MM}-{MAX_MM}).")
        distance_not_moved = abs(target_pos - MAX_MM) if target_pos > MAX_MM else abs(MIN_MM - target_pos)
        print(f"[!] Distance not moved on {axis}: {distance_not_moved:.3f} mm")

# === RAW MOVE (after safety check) ===
def move_axis(axis, distance_mm):
    pulses = mm_to_pulses(distance_mm)
    direction = '+' if pulses >= 0 else '-'
    cmd = f"{axis.upper()}{direction}{abs(pulses)}"
    return send_cmd(cmd)

# === MAIN ROUTINE ===
if __name__ == "__main__":
    send_cmd('?R')  # Handshake
    send_cmd('V70')  # Set speed

    # === Example Safe Moves ===
    safe_move('x', 50.0)
    time.sleep(0.5)

    safe_move('y', -30.0)
    time.sleep(0.5)

    safe_move('z', 10.0)
    time.sleep(0.5)

    # === Position Check ===
    print("\nCurrent Positions:")
    print(f"X: {get_position_mm('x'):.3f} mm")
    print(f"Y: {get_position_mm('y'):.3f} mm")
    print(f"Z: {get_position_mm('z'):.3f} mm")

    # === Homing Example ===
    send_cmd('HX0')  # Home X
    send_cmd('HY0')  # Home Y
    send_cmd('?H')   # Query home status

    # === Emergency Stop (if needed) ===
    # send_cmd('S')

    ser.close()
