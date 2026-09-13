"""
Launch Micro-Manager Core in headless mode (ZMQ server, no MM GUI).

Use this instead of opening Micro-Manager and checking
Tools -> Options -> "Run server on port 4827".

Keep this process running, then start:
  1) python pycro_manager_zmq_bridge.py
  2) OptiSuite GUI with Backend = Pycro-Manager

Example:
  python pycro_server_headless.py ^
    --mm-app-path "C:\\Program Files\\Micro-Manager-2.0" ^
    --config "C:\\path\\to\\YourHardware.cfg"
"""

from __future__ import annotations

import argparse
import signal
import socket
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MM_APP_PATH = r"C:\Program Files\Micro-Manager-2.0"
DEFAULT_PORT = 4827
DEFAULT_CONFIG = SCRIPT_DIR / "MMConfig_Optsuite.cfg"


def _resolve_config_path(path: str | Path) -> Path:
    """Resolve config path; relative paths are anchored to this script's directory."""
    p = Path(path)
    if not p.is_absolute():
        p = SCRIPT_DIR / p
    return p.resolve()


def _is_port_open(host: str, port: int, timeout_s: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=float(timeout_s)):
            return True
    except OSError:
        return False


def _parse_args():
    parser = argparse.ArgumentParser(description="Start Micro-Manager headless ZMQ server for OptiSuite/Pycro")
    parser.add_argument(
        "--mm-app-path",
        default=DEFAULT_MM_APP_PATH,
        help="Top-level Micro-Manager install folder (contains ImageJ.exe / MMCoreJ etc.)",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to Micro-Manager hardware config (.cfg); relative paths use this script's folder",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="ZMQ server port (default 4827)")
    parser.add_argument(
        "--python-backend",
        action="store_true",
        help="Use pymmcore Python backend instead of Java MMCoreJ (advanced)",
    )
    parser.add_argument("--java-loc", default=None, help="Optional path to java executable")
    parser.add_argument("--debug", action="store_true", help="Print pycromanager debug output")
    return parser.parse_args()


def main():
    args = _parse_args()
    mm_app_path = str(Path(args.mm_app_path))
    config_path = _resolve_config_path(args.config)
    config_file = str(config_path)
    port = int(args.port)

    if not Path(mm_app_path).is_dir():
        raise SystemExit(f"[PycroHeadless] Micro-Manager folder not found: {mm_app_path}")
    if not config_path.is_file():
        raise SystemExit(f"[PycroHeadless] Config file not found: {config_file}")

    if _is_port_open("127.0.0.1", port):
        raise SystemExit(
            f"[PycroHeadless] Port {port} is already in use. "
            "Close the Micro-Manager GUI ZMQ server or another headless instance first."
        )

    try:
        from pycromanager import Core, start_headless, stop_headless
    except Exception as e:
        raise SystemExit(
            "[PycroHeadless] pycromanager is not installed. Install with: pip install pycromanager"
        ) from e

    print(f"[PycroHeadless] Starting headless MM at {mm_app_path}")
    print(f"[PycroHeadless] Config: {config_file}")
    print(f"[PycroHeadless] ZMQ port: {port}")

    kwargs = {
        "python_backend": bool(args.python_backend),
        "port": port,
        "debug": bool(args.debug),
    }
    if args.java_loc:
        kwargs["java_loc"] = args.java_loc

    start_headless(mm_app_path, config_file, **kwargs)

    try:
        core = Core(port=port)
        camera = None
        try:
            camera = core.get_camera_device()
        except Exception:
            pass
        print(f"[PycroHeadless] Core ready. Camera={camera!r}")
        print("[PycroHeadless] Server running. Press Ctrl+C to stop.")
    except Exception as e:
        print(f"[PycroHeadless] Warning: started but Core probe failed: {e}", file=sys.stderr)

    stopping = {"done": False}

    def _stop(_signum=None, _frame=None):
        if stopping["done"]:
            return
        stopping["done"] = True
        print("\n[PycroHeadless] Stopping...")
        try:
            stop_headless()
        except Exception as e:
            print(f"[PycroHeadless] stop_headless error: {e}", file=sys.stderr)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    # Windows: GUI sends CTRL_BREAK_EVENT to a CREATE_NEW_PROCESS_GROUP child.
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _stop)

    try:
        while not stopping["done"]:
            time.sleep(0.5)
    finally:
        _stop()
        print("[PycroHeadless] Stopped.")


if __name__ == "__main__":
    main()
