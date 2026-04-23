# SC3U_Headless Build Instructions

## Overview
This is a headless (no GUI dependencies) version of the SC3U stage control library written in C++. It eliminates all Windows Forms dependencies and provides a clean API for stage control.

## Features
- ✅ **No GUI dependencies** - pure serial communication
- ✅ **Cross-platform** - Windows, Linux, macOS
- ✅ **Python bindings** - can be called from Python
- ✅ **Real-time position tracking** - actually queries the stage
- ✅ **Parameter management** - saves/loads from INI files
- ✅ **Thread-safe** - uses mutexes for concurrent access

## Building the Library

### Prerequisites
- **C++17 compatible compiler** (GCC 7+, Clang 5+, MSVC 2017+)
- **CMake 3.12+**
- **Python 3.6+** (if building Python bindings)

### Windows (Visual Studio)
```bash
mkdir build
cd build
cmake .. -G "Visual Studio 16 2019" -A x64
cmake --build . --config Release
```

### Windows (MinGW)
```bash
mkdir build
cd build
cmake .. -G "MinGW Makefiles"
cmake --build .
```

### Linux/macOS
```bash
mkdir build
cd build
cmake ..
make -j4
```

### With Python Bindings
```bash
# Install pybind11 first
pip install pybind11

# Build with Python bindings
mkdir build
cd build
cmake .. -DBUILD_PYTHON_BINDING=ON
cmake --build .
```

## Usage Examples

### C++ Usage
```cpp
#include "SC3U_Headless.h"

int main() {
    SC3U_Headless stage;
    
    // Connect to stage
    if (!stage.Connect("COM3", 9600)) {
        std::cout << "Connection failed: " << stage.GetLastError() << std::endl;
        return -1;
    }
    
    // Set parameters for X axis
    SC3U_Headless::StageParameters params;
    params.type = 0;           // Linear stage
    params.unit = 0;           // mm
    params.motor_angle = 1.8f; // 1.8 degrees
    params.subdivision = 2;    // Microstepping
    params.pitch = 1.0f;       // 1mm per revolution
    params.travel = 100.0;     // 100mm travel
    
    stage.SetParameters(0, params);
    stage.SaveParameters(0);
    
    // Get current position
    auto pos = stage.GetCurrentPosition();
    std::cout << "Current position: X=" << pos.x << ", Y=" << pos.y << ", Z=" << pos.z << std::endl;
    
    // Move to position
    stage.MoveToPosition(0, 10.0);  // Move X axis to 10mm
    
    stage.Disconnect();
    return 0;
}
```

### Python Usage
```python
import sc3u_headless

# Create stage instance
stage = sc3u_headless.SC3U_Headless()

# Connect to stage
if not stage.connect("COM3", 9600):
    print(f"Connection failed: {stage.get_last_error()}")
    exit(-1)

# Set parameters for X axis
params = sc3u_headless.StageParameters()
params.type = 0           # Linear stage
params.unit = 0           # mm
params.motor_angle = 1.8  # 1.8 degrees
params.subdivision = 2    # Microstepping
params.pitch = 1.0        # 1mm per revolution
params.travel = 100.0     # 100mm travel

stage.set_parameters(0, params)
stage.save_parameters(0)

# Get current position
pos = stage.get_current_position()
print(f"Current position: X={pos.x}, Y={pos.y}, Z={pos.z}")

# Move to position
stage.move_to_position(0, 10.0)  # Move X axis to 10mm

stage.disconnect()
```

## Integration with PyQt Application

### Modified integrated_camera_stage_app.py
```python
import sc3u_headless

class StageWorker(QObject):
    def __init__(self):
        super().__init__()
        self.stage = sc3u_headless.SC3U_Headless()
        self.is_connected = False
    
    def connect_stage(self, port):
        self.is_connected = self.stage.connect(port, 9600)
        if self.is_connected:
            self.connection_changed.emit(True)
        return self.is_connected
    
    def set_parameters(self, axis, params):
        # No GUI dependencies!
        stage_params = sc3u_headless.StageParameters()
        stage_params.type = params["type"]
        stage_params.unit = params["unit"]
        stage_params.motor_angle = params["motor_angle"]
        stage_params.subdivision = params["subdivision"]
        stage_params.pitch = params["pitch"]
        stage_params.travel = params["travel"]
        
        self.stage.set_parameters(axis, stage_params)
        return self.stage.save_parameters(axis)
    
    def get_current_position(self, axis):
        return self.stage.get_current_position(axis)
    
    def move_to_position(self, axis, position):
        return self.stage.move_to_position(axis, position)
```

## Key Advantages Over Original DLL

1. **No GUI Dependencies**: Can be used in any application
2. **Cross-Platform**: Works on Windows, Linux, macOS
3. **Real Position Queries**: Actually communicates with the stage
4. **Clean API**: Simple, intuitive interface
5. **Thread-Safe**: Can be used in multi-threaded applications
6. **Python Integration**: Easy to use from Python
7. **OpenCV Compatible**: Perfect for computer vision applications

## Port Mapping
- **Windows**: COM1, COM2, COM3, etc.
- **Linux**: /dev/ttyUSB0, /dev/ttyACM0, etc.
- **macOS**: /dev/cu.usbserial-*, /dev/cu.usbmodem*, etc.

## Error Handling
All methods return boolean success/failure and error messages are available via `GetLastError()`.

## Performance
- **Serial Communication**: Optimized for real-time control
- **Position Updates**: Can be called frequently without blocking
- **Memory Efficient**: Minimal memory footprint
- **Fast Startup**: No GUI initialization overhead
