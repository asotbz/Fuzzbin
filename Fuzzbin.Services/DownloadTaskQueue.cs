using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Channels;

namespace Fuzzbin.Services;

public interface IDownloadTaskQueue
{
    ValueTask QueueAsync(Guid queueItemId, CancellationToken cancellationToken = default);
    IAsyncEnumerable<Guid> DequeueAsync(CancellationToken cancellationToken);
}

public sealed class DownloadTaskQueue : IDownloadTaskQueue
{
    private readonly Channel<Guid> _channel;

    public DownloadTaskQueue()
    {
        _channel = Channel.CreateUnbounded<Guid>(new UnboundedChannelOptions
        {
            SingleReader = true,
            SingleWriter = false,
            AllowSynchronousContinuations = false
        });
    }

    public ValueTask QueueAsync(Guid queueItemId, CancellationToken cancellationToken = default)
    {
        return _channel.Writer.WriteAsync(queueItemId, cancellationToken);
    }

    public IAsyncEnumerable<Guid> DequeueAsync(CancellationToken cancellationToken)
    {
        return _channel.Reader.ReadAllAsync(cancellationToken);
    }
}
