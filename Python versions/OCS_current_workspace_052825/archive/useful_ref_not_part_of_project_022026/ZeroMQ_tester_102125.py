import argparse
import time
import zmq

def main(host: str, port: int, message: str, count: int):
    ctx = zmq.Context()
    sock = ctx.socket(zmq.PUSH)
    sock.connect(f"tcp://{host}:{port}")
    time.sleep(0.05)  # let ZeroMQ establish the TCP connection

    for i in range(count):
        sock.send_string(message)
        print(f"Sent ({i+1}/{count}): {message} -> tcp://{host}:{port}")
        time.sleep(0.1)  # optional brief delay between sends

    sock.close()
    ctx.term()

#note: type in the terminal python ZeroMQ_tester_102125 --message presetX to send presetX to the C# file
#the C# file has if statements to check the case of the text to execute messages
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Send a ZeroMQ PUSH message multiple times to trigger RunPresetRouteAsync")
    p.add_argument("--host", default="localhost", help="Host where the C# app is listening")
    p.add_argument("--port", type=int, default=5555, help="Port the C# NetMQPullListener is bound to")
    p.add_argument("--message", default="preset1", help="Message text (C# checks for 'preset1')")
    p.add_argument("--count", type=int, default=1, help="Number of times to send the message")
    args = p.parse_args()

    main(args.host, args.port, args.message, args.count)
