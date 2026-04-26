using System;
using System.Collections.Concurrent;
using System.Threading;
using System.Threading.Tasks;
using NetMQ;
using NetMQ.Sockets;

namespace CSharp
{
    /// <summary>
    /// Thread-owned NetMQ PUSH publisher for status/events.
    /// Safe to call Publish() from any thread.
    /// </summary>
    public sealed class ZmqStageEventPublisher : IDisposable
    {
        private readonly string _bindAddress;
        private readonly BlockingCollection<string> _queue =
            new BlockingCollection<string>(new ConcurrentQueue<string>());

        private CancellationTokenSource _cts;
        private Task _runner;

        public ZmqStageEventPublisher(string bindAddress)
        {
            if (string.IsNullOrWhiteSpace(bindAddress))
                throw new ArgumentException("bindAddress is required", nameof(bindAddress));
            _bindAddress = bindAddress;
        }

        public void Start()
        {
            if (_runner != null) return;
            _cts = new CancellationTokenSource();
            _runner = Task.Run(RunLoop);
        }

        public void Publish(string json)
        {
            if (string.IsNullOrWhiteSpace(json)) return;
            if (_queue.IsAddingCompleted) return;
            try { _queue.Add(json); } catch { /* ignore */ }
        }

        public void Stop()
        {
            try { _queue.CompleteAdding(); } catch { /* ignore */ }
            try { _cts?.Cancel(); } catch { /* ignore */ }
        }

        public void Dispose() => Stop();

        private void RunLoop()
        {
            try
            {
                AsyncIO.ForceDotNet.Force();
                using (var push = new PushSocket())
                {
                    push.Bind(_bindAddress);
                    foreach (var msg in _queue.GetConsumingEnumerable(_cts.Token))
                    {
                        try
                        {
                            push.SendFrame(msg);
                        }
                        catch (Exception ex)
                        {
                            Console.WriteLine($"[ZMQ-EVENT] send error: {ex.Message}");
                        }
                    }
                }
            }
            catch (OperationCanceledException)
            {
                // expected on shutdown
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ZMQ-EVENT] publisher crashed: {ex.Message}");
            }
        }
    }
}

