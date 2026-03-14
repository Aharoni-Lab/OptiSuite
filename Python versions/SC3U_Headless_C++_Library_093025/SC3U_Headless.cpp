// SC3U_Headless.cpp - Implementation of headless SC3U stage control
// No GUI dependencies, pure serial communication

#include "SC3U_Headless.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <chrono>
#include <thread>
#include <regex>

#ifdef _WIN32
    #include <windows.h>
#else
    #include <termios.h>
    #include <fcntl.h>
    #include <unistd.h>
#endif

// Serial port implementation
class SC3U_Headless::SerialPort {
public:
    SerialPort() : handle_(-1) {}
    
    ~SerialPort() {
        Close();
    }
    
    bool Open(const std::string& port, int baudrate) {
        Close();
        
#ifdef _WIN32
        handle_ = CreateFileA(port.c_str(), GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
        if (handle_ == INVALID_HANDLE_VALUE) {
            return false;
        }
        
        DCB dcb = {};
        dcb.DCBlength = sizeof(DCB);
        if (!GetCommState(handle_, &dcb)) {
            Close();
            return false;
        }
        
        dcb.BaudRate = baudrate;
        dcb.ByteSize = 8;
        dcb.Parity = NOPARITY;
        dcb.StopBits = ONESTOPBIT;
        dcb.fDtrControl = DTR_CONTROL_ENABLE;
        dcb.fRtsControl = RTS_CONTROL_DISABLE;
        
        if (!SetCommState(handle_, &dcb)) {
            Close();
            return false;
        }
        
        // Set timeouts
        COMMTIMEOUTS timeouts = {};
        timeouts.ReadIntervalTimeout = 50;
        timeouts.ReadTotalTimeoutConstant = 50;
        timeouts.ReadTotalTimeoutMultiplier = 10;
        timeouts.WriteTotalTimeoutConstant = 50;
        timeouts.WriteTotalTimeoutMultiplier = 10;
        
        if (!SetCommTimeouts(handle_, &timeouts)) {
            Close();
            return false;
        }
        
        return true;
#else
        handle_ = open(port.c_str(), O_RDWR | O_NOCTTY | O_SYNC);
        if (handle_ < 0) {
            return false;
        }
        
        struct termios tty;
        if (tcgetattr(handle_, &tty) != 0) {
            Close();
            return false;
        }
        
        cfsetospeed(&tty, baudrate);
        cfsetispeed(&tty, baudrate);
        
        tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;     // 8-bit chars
        tty.c_iflag &= ~IGNBRK;         // disable break processing
        tty.c_lflag = 0;                // no signaling chars, no echo, no canonical processing
        tty.c_oflag = 0;                // no remapping, no delays
        tty.c_cc[VMIN]  = 0;            // read doesn't block
        tty.c_cc[VTIME] = 5;            // 0.5 seconds read timeout
        
        tty.c_iflag &= ~(IXON | IXOFF | IXANY); // shut off xon/xoff ctrl
        tty.c_cflag |= (CLOCAL | CREAD);        // ignore modem controls, enable reading
        tty.c_cflag &= ~(PARENB | PARODD);      // shut off parity
        tty.c_cflag &= ~CSTOPB;
        tty.c_cflag &= ~CRTSCTS;
        
        if (tcsetattr(handle_, TCSANOW, &tty) != 0) {
            Close();
            return false;
        }
        
        return true;
#endif
    }
    
    void Close() {
        if (handle_ >= 0) {
#ifdef _WIN32
            CloseHandle(handle_);
#else
            close(handle_);
#endif
            handle_ = -1;
        }
    }
    
    bool IsOpen() const {
        return handle_ >= 0;
    }
    
    bool Write(const std::string& data) {
        if (!IsOpen()) return false;
        
#ifdef _WIN32
        DWORD written;
        return WriteFile(handle_, data.c_str(), data.length(), &written, NULL) && written == data.length();
#else
        return write(handle_, data.c_str(), data.length()) == data.length();
#endif
    }
    
    std::string Read(int timeout_ms = 1000) {
        if (!IsOpen()) return "";
        
        std::string result;
        auto start = std::chrono::steady_clock::now();
        
        while (std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::steady_clock::now() - start).count() < timeout_ms) {
            
            char buffer[256];
            int bytes_read = 0;
            
#ifdef _WIN32
            DWORD bytes_read_dw;
            if (ReadFile(handle_, buffer, sizeof(buffer) - 1, &bytes_read_dw, NULL)) {
                bytes_read = bytes_read_dw;
            }
#else
            bytes_read = read(handle_, buffer, sizeof(buffer) - 1);
#endif
            
            if (bytes_read > 0) {
                buffer[bytes_read] = '\0';
                result += buffer;
                
                // Check if we have a complete response (ends with \n)
                if (result.find('\n') != std::string::npos) {
                    break;
                }
            }
            
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
        
        return result;
    }
    
private:
    int handle_;
};

// SC3U_Headless implementation
SC3U_Headless::SC3U_Headless() 
    : serial_port_(std::make_unique<SerialPort>())
    , connected_(false)
    , busy_(false)
    , parameters_set_(false)
    , current_speed_(0) {
    
    // Initialize parameters
    for (int i = 0; i < 6; i++) {
        parameters_[i] = StageParameters{};
        pulse_equivalent_[i] = -1.0;
    }
}

SC3U_Headless::~SC3U_Headless() {
    Disconnect();
}

bool SC3U_Headless::Connect(const std::string& port, int baudrate) {
    if (connected_) {
        Disconnect();
    }
    
    if (!serial_port_->Open(port, baudrate)) {
        SetLastError("Failed to open serial port: " + port);
        return false;
    }
    
    // Test connection
    if (!SendCommand("?R\r")) {
        SetLastError("Failed to send connection test command");
        Disconnect();
        return false;
    }
    
    std::string response = ReadResponse(5000);
    if (response.find("OK") == std::string::npos) {
        SetLastError("Connection test failed. Response: " + response);
        Disconnect();
        return false;
    }
    
    // Get current speed
    if (SendCommand("?V\r")) {
        response = ReadResponse(1000);
        if (!response.empty()) {
            current_speed_ = StringToLong(response);
        }
    }
    
    connected_ = true;
    
    // Load parameters from INI file
    LoadFromIni();
    
    // Check if parameters are set
    bool has_params = false;
    for (int i = 0; i < 6; i++) {
        if (parameters_[i].type != 0) {
            has_params = true;
            break;
        }
    }
    parameters_set_ = has_params;
    
    return true;
}

void SC3U_Headless::Disconnect() {
    if (connected_) {
        Stop();
        serial_port_->Close();
        connected_ = false;
        busy_ = false;
    }
}

bool SC3U_Headless::IsConnected() const {
    return connected_;
}

bool SC3U_Headless::SetParameters(int axis, const StageParameters& params) {
    if (axis < 0 || axis >= 6) {
        SetLastError("Invalid axis: " + std::to_string(axis));
        return false;
    }
    
    parameters_[axis] = params;
    return true;
}

bool SC3U_Headless::SaveParameters(int axis) {
    if (axis < 0 || axis >= 6) {
        SetLastError("Invalid axis: " + std::to_string(axis));
        return false;
    }
    
    // Calculate pulse equivalent (this is the key calculation from the original DLL)
    CalculatePulseEquivalent(axis);
    
    // Save to INI file
    if (!SaveToIni()) {
        SetLastError("Failed to save parameters to INI file");
        return false;
    }
    
    // Check if any parameters are set
    bool has_params = false;
    for (int i = 0; i < 6; i++) {
        if (parameters_[i].type != 0) {
            has_params = true;
            break;
        }
    }
    parameters_set_ = has_params;
    
    return true;
}

void SC3U_Headless::CalculatePulseEquivalent(int axis) {
    const auto& params = parameters_[axis];
    
    switch (params.type) {
        case 1: // Linear stage
            pulse_equivalent_[axis] = params.motor_angle * params.pitch / (360.0 * params.subdivision);
            break;
            
        case 2: // Rotary stage
        case 3: // Goniometer
            pulse_equivalent_[axis] = params.motor_angle / (params.transmission_ratio * params.subdivision);
            break;
            
        case 4: // Elevating stage
            pulse_equivalent_[axis] = params.pitch / params.transmission_ratio / (360.0 / params.motor_angle * params.subdivision);
            break;
            
        default:
            pulse_equivalent_[axis] = -1.0;
            break;
    }
}

SC3U_Headless::Position SC3U_Headless::GetCurrentPosition() {
    std::lock_guard<std::mutex> lock(position_mutex_);
    return current_position_;
}

double SC3U_Headless::GetCurrentPosition(int axis) {
    if (axis < 0 || axis >= 6) {
        return -1.0;
    }
    
    std::lock_guard<std::mutex> lock(position_mutex_);
    switch (axis) {
        case 0: return current_position_.x;
        case 1: return current_position_.y;
        case 2: return current_position_.z;
        case 3: return current_position_.r;
        case 4: return current_position_.t1;
        case 5: return current_position_.t2;
        default: return -1.0;
    }
}

bool SC3U_Headless::MoveToPosition(int axis, double position) {
    if (!connected_ || !parameters_set_) {
        SetLastError("Not connected or parameters not set");
        return false;
    }
    
    if (axis < 0 || axis >= 6) {
        SetLastError("Invalid axis: " + std::to_string(axis));
        return false;
    }
    
    // Convert position to steps
    long steps = static_cast<long>(position / pulse_equivalent_[axis]);
    
    std::string command = GetAxisName(axis);
    if (steps >= 0) {
        command += "+" + std::to_string(steps) + "\r";
    } else {
        command += std::to_string(steps) + "\r";
    }
    
    if (!SendCommand(command)) {
        SetLastError("Failed to send move command");
        return false;
    }
    
    busy_ = true;
    
    // Wait for movement to complete (simplified - in reality you'd need to monitor position)
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    
    busy_ = false;
    
    // Update position
    RefreshCurrentPosition();
    
    return true;
}

bool SC3U_Headless::MoveToPosition(const Position& target) {
    // Move all axes to target positions
    bool success = true;
    for (int i = 0; i < 6; i++) {
        double pos = 0.0;
        switch (i) {
            case 0: pos = target.x; break;
            case 1: pos = target.y; break;
            case 2: pos = target.z; break;
            case 3: pos = target.r; break;
            case 4: pos = target.t1; break;
            case 5: pos = target.t2; break;
        }
        
        if (pos != 0.0) {  // Only move if position is not zero
            success &= MoveToPosition(i, pos);
        }
    }
    return success;
}

bool SC3U_Headless::MoveRelative(int axis, double distance) {
    if (axis < 0 || axis >= 6) {
        SetLastError("Invalid axis: " + std::to_string(axis));
        return false;
    }
    
    double current_pos = GetCurrentPosition(axis);
    return MoveToPosition(axis, current_pos + distance);
}

bool SC3U_Headless::Stop() {
    if (!connected_) {
        return false;
    }
    
    if (SendCommand("S\r")) {
        busy_ = false;
        return true;
    }
    return false;
}

bool SC3U_Headless::SetSpeed(int speed) {
    if (speed < 0 || speed > 255) {
        SetLastError("Speed must be between 0 and 255");
        return false;
    }
    
    if (!SendCommand("V" + std::to_string(speed) + "\r")) {
        SetLastError("Failed to set speed");
        return false;
    }
    
    current_speed_ = speed;
    return true;
}

int SC3U_Headless::GetSpeed() const {
    return current_speed_;
}

bool SC3U_Headless::IsBusy() const {
    return busy_;
}

bool SC3U_Headless::AreParametersSet() const {
    return parameters_set_;
}

std::string SC3U_Headless::GetLastError() const {
    std::lock_guard<std::mutex> lock(error_mutex_);
    return last_error_;
}

bool SC3U_Headless::SendCommand(const std::string& command) {
    if (!connected_) {
        return false;
    }
    
    return serial_port_->Write(command);
}

std::string SC3U_Headless::ReadResponse(int timeout_ms) {
    if (!connected_) {
        return "";
    }
    
    return serial_port_->Read(timeout_ms);
}

void SC3U_Headless::RefreshCurrentPosition() {
    for (int i = 0; i < 6; i++) {
        if (parameters_[i].type != 0) {  // Only query axes with parameters set
            QueryAxisPosition(i);
        }
    }
}

bool SC3U_Headless::QueryAxisPosition(int axis) {
    if (!connected_) {
        return false;
    }
    
    std::string command = "?" + GetAxisName(axis) + "\r";
    if (!SendCommand(command)) {
        return false;
    }
    
    std::string response = ReadResponse(1000);
    if (response.empty()) {
        return false;
    }
    
    // Parse response and update position
    long steps = StringToLong(response);
    double position = steps * pulse_equivalent_[axis];
    
    std::lock_guard<std::mutex> lock(position_mutex_);
    switch (axis) {
        case 0: current_position_.x = position; break;
        case 1: current_position_.y = position; break;
        case 2: current_position_.z = position; break;
        case 3: current_position_.r = position; break;
        case 4: current_position_.t1 = position; break;
        case 5: current_position_.t2 = position; break;
    }
    
    return true;
}

bool SC3U_Headless::SaveToIni(const std::string& filename) {
    std::ofstream file(filename);
    if (!file.is_open()) {
        return false;
    }
    
    std::string axis_names[] = {"XAxis", "YAxis", "ZAxis", "RAxis", "T1Axis", "T2Axis"};
    
    for (int i = 0; i < 6; i++) {
        const auto& params = parameters_[i];
        file << "[" << axis_names[i] << "]\n";
        file << "Type=" << params.type << "\n";
        file << "Unit=" << params.unit << "\n";
        file << "MotorAngle=" << params.motor_angle << "\n";
        file << "Subsection=" << params.subdivision << "\n";
        file << "Pitch=" << params.pitch << "\n";
        file << "TranRatio=" << params.transmission_ratio << "\n";
        file << "Travel=" << params.travel << "\n";
        file << "NegaTravel=0\n";
        file << "PosiTravel=0\n";
        file << "ZeroOffset=0\n";
        file << "\n";
    }
    
    return true;
}

bool SC3U_Headless::LoadFromIni(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        return false;
    }
    
    std::string line;
    std::string current_section;
    std::string axis_names[] = {"XAxis", "YAxis", "ZAxis", "RAxis", "T1Axis", "T2Axis"};
    
    while (std::getline(file, line)) {
        // Remove whitespace
        line.erase(0, line.find_first_not_of(" \t"));
        line.erase(line.find_last_not_of(" \t") + 1);
        
        if (line.empty() || line[0] == ';') continue;
        
        if (line[0] == '[' && line.back() == ']') {
            current_section = line.substr(1, line.length() - 2);
        } else {
            size_t eq_pos = line.find('=');
            if (eq_pos != std::string::npos) {
                std::string key = line.substr(0, eq_pos);
                std::string value = line.substr(eq_pos + 1);
                
                // Find which axis this belongs to
                int axis = -1;
                for (int i = 0; i < 6; i++) {
                    if (current_section == axis_names[i]) {
                        axis = i;
                        break;
                    }
                }
                
                if (axis >= 0) {
                    auto& params = parameters_[axis];
                    
                    if (key == "Type") params.type = std::stoi(value);
                    else if (key == "Unit") params.unit = std::stoi(value);
                    else if (key == "MotorAngle") params.motor_angle = std::stof(value);
                    else if (key == "Subsection") params.subdivision = std::stoi(value);
                    else if (key == "Pitch") params.pitch = std::stof(value);
                    else if (key == "TranRatio") params.transmission_ratio = std::stoi(value);
                    else if (key == "Travel") params.travel = std::stod(value);
                }
            }
        }
    }
    
    // Recalculate pulse equivalents for loaded parameters
    for (int i = 0; i < 6; i++) {
        if (parameters_[i].type != 0) {
            CalculatePulseEquivalent(i);
        }
    }
    
    return true;
}

std::string SC3U_Headless::GetAxisName(int axis) const {
    std::string names[] = {"XAxis", "YAxis", "ZAxis", "RAxis", "T1Axis", "T2Axis"};
    if (axis >= 0 && axis < 6) {
        return names[axis];
    }
    return "";
}

long SC3U_Headless::StringToLong(const std::string& str) const {
    try {
        return std::stol(str);
    } catch (...) {
        return 0;
    }
}

void SC3U_Headless::SetLastError(const std::string& error) {
    std::lock_guard<std::mutex> lock(error_mutex_);
    last_error_ = error;
}
