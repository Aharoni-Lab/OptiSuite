import threading
import time

import zmq


class ZMQPullListener(threading.Thread):
    """
    Minimal ZeroMQ PULL listener in its own thread.

    Intended for C# -> Python status/event messages.
    """

    def __init__(self, host="localhost", port=5556, on_message=None, rcv_timeout_ms=200):
        super().__init__()
        self.host = host
        self.port = port
        self.on_message = on_message
        self.rcv_timeout_ms = int(rcv_timeout_ms)

        self.ctx = None
        self.sock = None
        self.running = False

    def run(self):
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.PULL)
        # Allow clean shutdown by timing out periodically.
        self.sock.RCVTIMEO = self.rcv_timeout_ms
        self.sock.connect(f"tcp://{self.host}:{self.port}")
        self.running = True
        print(f"[ZMQ-EVENT] Connected to tcp://{self.host}:{self.port}")

        while self.running:
            try:
                msg = self.sock.recv_string()
                if self.on_message:
                    try:
                        self.on_message(msg)
                    except Exception as cb_err:
                        print(f"[ZMQ-EVENT] on_message error: {cb_err}")
                else:
                    print(f"[ZMQ-EVENT] {msg}")
            except zmq.Again:
                # timeout
                continue
            except Exception as e:
                if not self.running:
                    break
                print(f"[ZMQ-EVENT] receive error: {e}")
                time.sleep(0.05)

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close(linger=0)
        finally:
            self.sock = None
        try:
            if self.ctx:
                self.ctx.term()
        finally:
            self.ctx = None
        print("[ZMQ-EVENT] Connection closed.")


# Non-breaking alias for future rename
ZMQGUIPull = ZMQPullListener
