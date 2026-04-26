using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace CSharp
{
    public class StageCommand
    {
        public string Type; // "MoveToXY", "MoveToXYZ", "Stop"
        public double X;
        public double Y;
        public double Z;
    }

    /// <summary>
    /// Owns ZeroMQ (NetMQ) receive + stage-command queue.
    /// Conservative extraction from Form1: behavior should remain the same.
    /// </summary>
    public sealed class ZmqStageServer : IDisposable
    {
        private readonly NetMQPullListener _listener;
        private readonly ConcurrentQueue<StageCommand> _commandQueue = new ConcurrentQueue<StageCommand>();
        private readonly CancellationTokenSource _runnerCts = new CancellationTokenSource();
        private readonly Task _queueRunnerTask;

        private readonly Func<short, double, Task> _runToTargetAsync;
        private readonly Func<Task> _runTestRouteAsync;
        private readonly Action _stopRun;
        private readonly Action _setOrigin;
        private readonly Func<short, Task<double>> _getCurrentPositionAsync;
        private readonly ZmqStageEventPublisher _eventPublisher;
        private long _eventSeq = 0;
        private long _stopEpoch = 0;

        public ZmqStageServer(
            string bindAddress,
            Func<short, double, Task> runToTargetAsync,
            Func<Task> runTestRouteAsync,
            Action stopRun,
            Action setOrigin,
            Func<short, Task<double>> getCurrentPositionAsync = null,
            string eventBindAddress = "tcp://*:5556")
        {
            if (string.IsNullOrWhiteSpace(bindAddress)) throw new ArgumentException("bindAddress is required", nameof(bindAddress));
            _runToTargetAsync = runToTargetAsync ?? throw new ArgumentNullException(nameof(runToTargetAsync));
            _runTestRouteAsync = runTestRouteAsync ?? throw new ArgumentNullException(nameof(runTestRouteAsync));
            _stopRun = stopRun ?? throw new ArgumentNullException(nameof(stopRun));
            _setOrigin = setOrigin ?? throw new ArgumentNullException(nameof(setOrigin));
            _getCurrentPositionAsync = getCurrentPositionAsync;

            _listener = new NetMQPullListener(bindAddress);
            _listener.MessageReceived += OnZmqMessage;

            _queueRunnerTask = Task.Run(ProcessQueueAsync);
            _eventPublisher = new ZmqStageEventPublisher(eventBindAddress);
        }

        public void Start()
        {
            _eventPublisher.Start();
            _listener.Start();
            PublishEvent("ServerStarted", command: null, payload: null, message: null);
        }

        public void Stop()
        {
            try
            {
                _runnerCts.Cancel();
            }
            catch { /* ignore */ }

            try
            {
                _listener.Stop();
            }
            catch { /* ignore */ }

            try
            {
                PublishEvent("ServerStopped", command: null, payload: null, message: null);
                _eventPublisher.Stop();
            }
            catch { /* ignore */ }
        }

        public void Dispose() => Stop();

        private async Task ProcessQueueAsync()
        {
            while (!_runnerCts.IsCancellationRequested)
            {
                if (_commandQueue.TryDequeue(out var cmd))
                {
                    try
                    {
                        PublishEvent(
                            "CommandStarted",
                            cmd.Type,
                            cmd.Type == "MoveToXY"
                                ? (object)new { X = cmd.X, Y = cmd.Y }
                                : (object)new { X = cmd.X, Y = cmd.Y, Z = cmd.Z },
                            message: null
                        );
                        await ExecuteCommand(cmd).ConfigureAwait(false);
                        PublishEvent(
                            "CommandCompleted",
                            cmd.Type,
                            cmd.Type == "MoveToXY"
                                ? (object)new { X = cmd.X, Y = cmd.Y }
                                : (object)new { X = cmd.X, Y = cmd.Y, Z = cmd.Z },
                            message: null
                        );
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[ZMQ] ExecuteCommand error: {ex.Message}");
                        PublishEvent("CommandError", cmd?.Type, payload: null, message: ex.Message);
                    }
                }
                else
                {
                    await Task.Delay(10).ConfigureAwait(false);
                }
            }
        }

        private void ClearQueue()
        {
            while (_commandQueue.TryDequeue(out _)) { }
        }

        private async Task ExecuteCommand(StageCommand cmd)
        {
            if (cmd == null) return;

            if (cmd.Type == "MoveToXY")
            {
                var epoch = Interlocked.Read(ref _stopEpoch);
                await _runToTargetAsync(0, cmd.X).ConfigureAwait(false);
                if (Interlocked.Read(ref _stopEpoch) != epoch) return;
                await _runToTargetAsync(1, cmd.Y).ConfigureAwait(false);
            }
            else if (cmd.Type == "MoveToXYZ")
            {
                var epoch = Interlocked.Read(ref _stopEpoch);
                await _runToTargetAsync(0, cmd.X).ConfigureAwait(false);
                if (Interlocked.Read(ref _stopEpoch) != epoch) return;
                await _runToTargetAsync(1, cmd.Y).ConfigureAwait(false);
                if (Interlocked.Read(ref _stopEpoch) != epoch) return;
                await _runToTargetAsync(2, cmd.Z).ConfigureAwait(false);
            }
            else if (cmd.Type == "Stop")
            {
                _stopRun();
                ClearQueue();
            }
        }

        private void OnZmqMessage(string msg)
        {
            Console.WriteLine("Message Received");
            try
            {
                using (var doc = JsonDocument.Parse(msg))
                {
                    var root = doc.RootElement;
                    string command = root.GetProperty("command").GetString();

                    Console.WriteLine("parsed command: " + command);
                    switch (command)
                    {
                        case "MoveToXY":
                            var moveXY = new StageCommand
                            {
                                Type = "MoveToXY",
                                X = root.GetProperty("x").GetDouble(),
                                Y = root.GetProperty("y").GetDouble(),
                            };
                            _commandQueue.Enqueue(moveXY);
                            PublishEvent("CommandQueued", moveXY.Type, new { X = moveXY.X, Y = moveXY.Y }, message: null);
                            break;

                        case "MoveToXYZ":
                            var moveXYZ = new StageCommand
                            {
                                Type = "MoveToXYZ",
                                X = root.GetProperty("x").GetDouble(),
                                Y = root.GetProperty("y").GetDouble(),
                                Z = root.GetProperty("z").GetDouble(),
                            };
                            _commandQueue.Enqueue(moveXYZ);
                            PublishEvent("CommandQueued", moveXYZ.Type, new { X = moveXYZ.X, Y = moveXYZ.Y, Z = moveXYZ.Z }, message: null);
                            break;

                        case "StopRun":
                            // Preempt: stop immediately and clear pending queue.
                            Interlocked.Increment(ref _stopEpoch);
                            ClearQueue();
                            _stopRun();
                            PublishEvent("StopRun", "StopRun", payload: null, message: null);
                            break;

                        case "RunToTarget":
                            {
                                short axis = (short)root.GetProperty("axis").GetInt32();
                                double target = root.GetProperty("target").GetDouble();
                                PublishEvent("CommandReceived", "RunToTarget", payload: new { axis, target }, message: null);
                                _ = _runToTargetAsync(axis, target);
                                break;
                            }

                        case "GetCurrentPosition":
                            {
                                if (_getCurrentPositionAsync == null)
                                {
                                    PublishEvent("PositionError", "GetCurrentPosition", payload: null, message: "GetCurrentPosition not wired");
                                    break;
                                }

                                _ = Task.Run(async () =>
                                {
                                    try
                                    {
                                        var x = await _getCurrentPositionAsync(0).ConfigureAwait(false);
                                        var y = await _getCurrentPositionAsync(1).ConfigureAwait(false);
                                        var z = await _getCurrentPositionAsync(2).ConfigureAwait(false);
                                        PublishEvent("Position", "GetCurrentPosition", payload: new { X = x, Y = y, Z = z }, message: null);
                                    }
                                    catch (Exception ex2)
                                    {
                                        PublishEvent("PositionError", "GetCurrentPosition", payload: null, message: ex2.Message);
                                    }
                                });

                                break;
                            }

                        case "SetOrigin":
                            PublishEvent("CommandReceived", "SetOrigin", payload: null, message: null);
                            _setOrigin();
                            break;

                        case "RunTestRoute":
                            PublishEvent("CommandReceived", "RunTestRoute", payload: null, message: null);
                            _ = _runTestRouteAsync();
                            break;

                        default:
                            Console.WriteLine($"[ZMQ] Unknown command: {command}");
                            PublishEvent("CommandUnknown", command, payload: null, message: null);
                            break;
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ZMQ] Error parsing JSON: {ex.Message}");
                PublishEvent("ParseError", command: null, payload: null, message: ex.Message);
            }
        }

        private void PublishEvent(string evt, string command, object payload, string message)
        {
            try
            {
                var data = new Dictionary<string, object>
                {
                    ["event"] = evt,
                    ["seq"] = Interlocked.Increment(ref _eventSeq),
                    ["ts_utc_ms"] = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                };

                if (!string.IsNullOrWhiteSpace(command))
                    data["command"] = command;

                if (payload != null)
                    data["payload"] = payload;

                if (!string.IsNullOrWhiteSpace(message))
                    data["message"] = message;

                string json = JsonSerializer.Serialize(data);
                _eventPublisher.Publish(json);
            }
            catch
            {
                // never let telemetry break stage control
            }
        }
    }
}

