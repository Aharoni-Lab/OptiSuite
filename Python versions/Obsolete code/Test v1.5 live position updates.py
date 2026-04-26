import serial
import time

PORT = 'COM3'  # Change to your port
PULSES_PER_MM = 1600

def pulses_to_mm(pulses):
    return pulses / PULSES_PER_MM

def send_cmd(ser, cmd, delay=0.1):
    full_cmd = cmd + '\r'
    ser.write(full_cmd.encode())
    time.sleep(delay)
    response = ser.read_all().decode(errors='ignore').strip()
    return response

def query_position(ser, axis):
    response = send_cmd(ser, f'?{axis.upper()}')
    try:
        # Expected format: '?X\rX+123456\r\n' or similar
        for line in response.splitlines():
            if line.startswith(axis.upper()):
                num_str = line[1:].strip()  # skip 'X', get '+123456'
                return pulses_to_mm(int(num_str))
        return None
    except ValueError:
        print(f"[!] Could not parse response for axis {axis}: {response}")
        return None


def live_position_tracking(interval=0.5):
    with serial.Serial(PORT, baudrate=9600, timeout=1) as ser:
        print("🔄 Live tracking started. Press Ctrl+C to stop.\n")
        while True:
            x = query_position(ser, 'x')
            y = query_position(ser, 'y')
            z = query_position(ser, 'z')
            print(f"X: {x:.3f} mm | Y: {y:.3f} mm | Z: {z:.3f} mm", end='\r')
            time.sleep(interval)

if __name__ == "__main__":
    try:
        live_position_tracking(interval=0.5)  # Update every 0.5s
    except KeyboardInterrupt:
        print("\n🛑 Live tracking stopped.")
