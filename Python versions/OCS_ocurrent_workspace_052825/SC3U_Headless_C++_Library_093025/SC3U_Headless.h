// SC3U_Headless.h - Headless version of SC3U stage control
// No GUI dependencies, pure serial communication

#pragma once
#include <string>
#include <vector>
#include <memory>
#include <thread>
#include <mutex>
#include <atomic>

class SC3U_Headless {
public:
    // Constructor/Destructor
    SC3U_Headless();
    ~SC3U_Headless();
    
    // Connection management
    bool Connect(const std::string& port, int baudrate = 9600);
    void Disconnect();
    bool IsConnected() const;
    
    // Parameter management (no GUI dependencies!)
    struct StageParameters {
        int type = 0;           // 0=Linear, 1=Translation, 2=Rotary, 3=Goniometer, 4=Elevating
        int unit = 0;           // 0=mm, 1=degree, 2=step
        float motor_angle = 1.8f;  // 0.9 or 1.8 degrees
        int subdivision = 2;    // Microstepping
        float pitch = 1.0f;     // Screw pitch (mm/rev)
        double travel = 100.0;  // Travel range
        int transmission_ratio = 1; // For rotary stages
    };
    
    // Set parameters for specific axis (no GUI needed!)
    bool SetParameters(int axis, const StageParameters& params);
    bool SaveParameters(int axis);  // Saves to INI file and calculates pulse equivalents
    
    // Position management
    struct Position {
        double x = 0.0;
        double y = 0.0;
        double z = 0.0;
        double r = 0.0;
        double t1 = 0.0;
        double t2 = 0.0;
    };
    
    // Get current position (actually queries the stage!)
    Position GetCurrentPosition();
    double GetCurrentPosition(int axis);
    
    // Movement control
    bool MoveToPosition(int axis, double position);
    bool MoveToPosition(const Position& target);
    bool MoveRelative(int axis, double distance);
    bool Stop();
    
    // Speed control
    bool SetSpeed(int speed);  // 0-255
    int GetSpeed() const;
    
    // Status
    bool IsBusy() const;
    bool AreParametersSet() const;
    
    // Error handling
    std::string GetLastError() const;
    
private:
    // Serial communication
    class SerialPort;
    std::unique_ptr<SerialPort> serial_port_;
    
    // Stage state
    std::atomic<bool> connected_;
    std::atomic<bool> busy_;
    std::atomic<bool> parameters_set_;
    std::atomic<int> current_speed_;
    
    // Parameters for all 6 axes
    StageParameters parameters_[6];
    double pulse_equivalent_[6];  // Calculated in SaveParameters()
    
    // Position tracking
    Position current_position_;
    std::mutex position_mutex_;
    
    // Communication
    std::string last_error_;
    mutable std::mutex error_mutex_;
    
    // Internal methods
    bool SendCommand(const std::string& command);
    std::string ReadResponse(int timeout_ms = 1000);
    bool WaitForResponse(const std::string& expected, int timeout_ms = 1000);
    
    // Position querying
    void RefreshCurrentPosition();
    bool QueryAxisPosition(int axis);
    
    // Parameter calculation
    void CalculatePulseEquivalent(int axis);
    
    // INI file operations
    bool SaveToIni(const std::string& filename = "34SysParam.ini");
    bool LoadFromIni(const std::string& filename = "34SysParam.ini");
    
    // Utility functions
    std::string GetAxisName(int axis) const;
    long StringToLong(const std::string& str) const;
    void SetLastError(const std::string& error);
};

// Python binding helper (if using pybind11)
#ifdef PYTHON_BINDING
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

PYBIND11_MODULE(sc3u_headless, m) {
    pybind11::class_<SC3U_Headless>(m, "SC3U_Headless")
        .def(pybind11::init<>())
        .def("connect", &SC3U_Headless::Connect)
        .def("disconnect", &SC3U_Headless::Disconnect)
        .def("is_connected", &SC3U_Headless::IsConnected)
        .def("set_parameters", &SC3U_Headless::SetParameters)
        .def("save_parameters", &SC3U_Headless::SaveParameters)
        .def("get_current_position", pybind11::overload_cast<>(&SC3U_Headless::GetCurrentPosition))
        .def("get_current_position", pybind11::overload_cast<int>(&SC3U_Headless::GetCurrentPosition))
        .def("move_to_position", pybind11::overload_cast<int, double>(&SC3U_Headless::MoveToPosition))
        .def("move_to_position", pybind11::overload_cast<const Position&>(&SC3U_Headless::MoveToPosition))
        .def("move_relative", &SC3U_Headless::MoveRelative)
        .def("stop", &SC3U_Headless::Stop)
        .def("set_speed", &SC3U_Headless::SetSpeed)
        .def("get_speed", &SC3U_Headless::GetSpeed)
        .def("is_busy", &SC3U_Headless::IsBusy)
        .def("are_parameters_set", &SC3U_Headless::AreParametersSet)
        .def("get_last_error", &SC3U_Headless::GetLastError);
    
    pybind11::class_<SC3U_Headless::StageParameters>(m, "StageParameters")
        .def(pybind11::init<>())
        .def_readwrite("type", &SC3U_Headless::StageParameters::type)
        .def_readwrite("unit", &SC3U_Headless::StageParameters::unit)
        .def_readwrite("motor_angle", &SC3U_Headless::StageParameters::motor_angle)
        .def_readwrite("subdivision", &SC3U_Headless::StageParameters::subdivision)
        .def_readwrite("pitch", &SC3U_Headless::StageParameters::pitch)
        .def_readwrite("travel", &SC3U_Headless::StageParameters::travel)
        .def_readwrite("transmission_ratio", &SC3U_Headless::StageParameters::transmission_ratio);
    
    pybind11::class_<SC3U_Headless::Position>(m, "Position")
        .def(pybind11::init<>())
        .def_readwrite("x", &SC3U_Headless::Position::x)
        .def_readwrite("y", &SC3U_Headless::Position::y)
        .def_readwrite("z", &SC3U_Headless::Position::z)
        .def_readwrite("r", &SC3U_Headless::Position::r)
        .def_readwrite("t1", &SC3U_Headless::Position::t1)
        .def_readwrite("t2", &SC3U_Headless::Position::t2);
}
#endif
