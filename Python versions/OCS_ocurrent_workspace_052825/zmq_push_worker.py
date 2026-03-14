import threading

import zmq


class ZMQWorker(threading.Thread):
    """
    Minimal ZeroMQ PUSH client running in its own thread.

    Kept intentionally small so GUI code can own higher-level protocol (JSON schema, etc).
    """

    def __init__(self, host="localhost", port=5555):
        super().__init__()
        self.host = host
        self.port = port
        self.ctx = None
        self.sock = None
        self.running = False

    def run(self):
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.PUSH)
        self.sock.connect(f"tcp://{self.host}:{self.port}")
        self.running = True
        print(f"[ZMQ] Connected to tcp://{self.host}:{self.port}")

    def send_message(self, msg: str):
        if self.sock and self.running:
            try:
                self.sock.send_string(msg, flags=zmq.NOBLOCK)
                print(f"[ZMQ] Sent: {msg}")
            except zmq.Again:
                print("[ZMQ] Send would block (receiver not ready).")
        else:
            print("[ZMQ] Not connected or socket not ready.")

    def stop(self):
        if self.sock:
            self.sock.close(linger=0)
        if self.ctx:
            self.ctx.term()
        self.running = False
        print("[ZMQ] Connection closed.")


# Non-breaking alias for future rename
ZMQGUIPush = ZMQWorker
