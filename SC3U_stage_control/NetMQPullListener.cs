// csharp SC3U_stage_control\NetMQPullListener.cs
using System;
using System.Threading.Tasks;
using NetMQ;
using NetMQ.Sockets;

public class NetMQPullListener : IDisposable
{
    private readonly string _bindAddress;
    private volatile bool _running;

    public event Action<string> MessageReceived;

    public NetMQPullListener(string bindAddress = "tcp://*:5555")
    {
        _bindAddress = bindAddress;
    }

    public void Start()
    {
        Task.Run(() =>
        {
            AsyncIO.ForceDotNet.Force(); // NetMQ init (optional with recent NetMQ)
            using (var pull = new PullSocket())
            {
                pull.Bind(_bindAddress);
                _running = true;
                while (_running)
                {
                    try
                    {
                        // blocking receive; will throw on socket disposed when stopping
                        var msg = pull.ReceiveFrameString();
                        MessageReceived?.Invoke(msg);
                    }
                    catch (Exception)
                    {
                        // swallow or log; break on shutdown
                        if (!_running) break;
                    }
                }
            }
        });
    }

    public void Stop() => _running = false;

    public void Dispose() => Stop();
}