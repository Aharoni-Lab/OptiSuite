import argparse
import json
import signal
import socket
import time
from datetime import datetime, timezone

import zmq

# could be indirectly used in 2camera_ZeroMQ_06132026.py
class PycroManagerStage:
    def __init__(self, mm_host="127.0.0.1", mm_port=4827):
        self.mm_host = mm_host
        self.mm_port = int(mm_port)
        if not self._is_port_open(self.mm_host, self.mm_port):
            raise RuntimeError(
                f"Micro-Manager ZMQ server is not reachable at {self.mm_host}:{self.mm_port}. "
                "Open Micro-Manager, load your hardware configuration, and enable the ZMQ server "
                "on that port before starting this bridge."
            )

        try:
            from pycromanager import Core
        except Exception as e:
            raise RuntimeError("pycromanager is not installed. Install it with: pip install pycromanager") from e

        self.core = Core(port=self.mm_port)
        self.xy_stage = self._call_optional("get_xy_stage_device")
        self.z_stage = self._call_optional("get_focus_device")

    def _is_port_open(self, host, port, timeout_s=0.75):
        try:
            with socket.create_connection((host, int(port)), timeout=float(timeout_s)):
                return True
        except OSError:
            return False

    def _call_optional(self, name, *args):
        fn = getattr(self.core, name, None)
        if fn is None:
            return None
        try:
            return fn(*args)
        except Exception:
            return None

    def get_position_xyz(self):
        x = self._call_optional("get_x_position")
        y = self._call_optional("get_y_position")
        z = self._call_optional("get_position")

        if x is None or y is None:
            xy = self._call_optional("get_xy_stage_position")
            if isinstance(xy, (tuple, list)) and len(xy) >= 2:
                x, y = xy[0], xy[1]

        return float(x or 0.0), float(y or 0.0), float(z or 0.0)

    def move_to_xyz(self, x, y, z):
        x = float(x)
        y = float(y)
        z = float(z)

        set_xyz = getattr(self.core, "set_xyz_position", None)
        if callable(set_xyz):
            try:
                set_xyz(x, y, z)
                self.wait_for_stage()
                return
            except Exception:
                pass

        set_xy = getattr(self.core, "set_xy_position", None)
        if callable(set_xy):
            set_xy(x, y)

        set_z = getattr(self.core, "set_position", None)
        if callable(set_z):
            set_z(z)

        self.wait_for_stage()

    def wait_for_stage(self):
        wait_for_device = getattr(self.core, "wait_for_device", None)
        if not callable(wait_for_device):
            return

        for device in (self.xy_stage, self.z_stage):
            if device:
                try:
                    wait_for_device(device)
                except Exception:
                    pass

    def stop(self):
        for name in ("stop", "stop_sequence_acquisition"):
            fn = getattr(self.core, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass


class PycroManagerZmqBridge:
    def __init__(self, host="127.0.0.1", command_port=5655, event_port=5656, mm_host="127.0.0.1", mm_port=4827):
        self.host = host
        self.command_port = int(command_port)
        self.event_port = int(event_port)
        self.mm_host = mm_host
        self.mm_port = int(mm_port)
        self.ctx = None
        self.command_sock = None
        self.event_sock = None
        self.running = False
        self.seq = 0
        self.stage = None

    def _next_seq(self):
        self.seq += 1
        return self.seq

    def _event(self, event, command=None, payload=None, message=None):
        msg = {
            "event": event,
            "seq": self._next_seq(),
            "ts_utc_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        if command:
            msg["command"] = command
        if payload is not None:
            msg["payload"] = payload
        if message:
            msg["message"] = str(message)
        self.event_sock.send_string(json.dumps(msg))
        print(f"[PycroBridge] Event: {msg}")

    def _payload_xyz(self, x, y, z):
        return {"X": float(x), "Y": float(y), "Z": float(z)}

    def _handle_command(self, raw_msg):
        try:
            data = json.loads(raw_msg)
        except Exception as e:
            self._event("ParseError", message=e)
            return

        command = data.get("command")
        if not command:
            self._event("ParseError", payload=data, message="Missing command")
            return

        self._event("CommandReceived", command=command, payload=data)

        try:
            if command == "GetCurrentPosition":
                x, y, z = self.stage.get_position_xyz()
                self._event("Position", command=command, payload=self._payload_xyz(x, y, z))
            elif command == "MoveToXYZ":
                x = float(data["x"])
                y = float(data["y"])
                z = float(data["z"])
                payload = self._payload_xyz(x, y, z)
                self._event("CommandStarted", command=command, payload=payload)
                self.stage.move_to_xyz(x, y, z)
                self._event("CommandCompleted", command=command, payload=payload)
            elif command == "StopRun":
                self.stage.stop()
                self._event("StopRun", command=command, message="Stop requested")
            else:
                self._event("CommandError", command=command, payload=data, message=f"Unsupported command: {command}")
        except Exception as e:
            self._event("CommandError", command=command, payload=data, message=e)

    def start(self):
        self.stage = PycroManagerStage(self.mm_host, self.mm_port)
        self.ctx = zmq.Context()
        self.command_sock = self.ctx.socket(zmq.PULL)
        self.command_sock.RCVTIMEO = 200
        self.command_sock.bind(f"tcp://{self.host}:{self.command_port}")
        self.event_sock = self.ctx.socket(zmq.PUSH)
        self.event_sock.bind(f"tcp://{self.host}:{self.event_port}")
        self.running = True
        self._event(
            "ServerStarted",
            message=f"Pycro-Manager bridge listening on {self.host}:{self.command_port}/{self.event_port}",
        )

        while self.running:
            try:
                raw_msg = self.command_sock.recv_string()
            except zmq.Again:
                continue
            self._handle_command(raw_msg)

    def stop(self):
        self.running = False
        try:
            if self.stage:
                self.stage.stop()
        except Exception:
            pass
        try:
            if self.event_sock:
                self._event("ServerStopped", message="Pycro-Manager bridge stopped")
        except Exception:
            pass
        for sock in (self.command_sock, self.event_sock):
            try:
                if sock:
                    sock.close(linger=0)
            except Exception:
                pass
        if self.ctx:
            self.ctx.term()


def main():
    parser = argparse.ArgumentParser(description="OptiSuite Pycro-Manager ZeroMQ bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--command-port", type=int, default=5655)
    parser.add_argument("--event-port", type=int, default=5656)
    parser.add_argument("--mm-host", default="127.0.0.1", help="Micro-Manager/Pycro-Manager ZMQ host")
    parser.add_argument("--mm-port", type=int, default=4827, help="Micro-Manager/Pycro-Manager ZMQ port")
    args = parser.parse_args()

    bridge = PycroManagerZmqBridge(args.host, args.command_port, args.event_port, args.mm_host, args.mm_port)

    def _stop(_signum=None, _frame=None):
        bridge.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        bridge.start()
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        print(f"[PycroBridge] {e}")
    finally:
        bridge.stop()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
