using System;

namespace Fuzzbin.Services.Models
{
    /// <summary>
    /// Defines retry behavior based on error type
    /// </summary>
    public class RetryStrategy
    {
        /// <summary>
        /// The type of error that occurred
        /// </summary>
        public DownloadErrorType ErrorType { get; set; }
        
        /// <summary>
        /// Whether this error type should be retried
        /// </summary>
        public bool ShouldRetry { get; set; }
        
        /// <summary>
        /// Maximum number of retry attempts for this error type
        /// </summary>
        public int MaxRetries { get; set; }
        
        /// <summary>
        /// Base delay in seconds before first retry
        /// </summary>
        public int BaseDelaySeconds { get; set; }
        
        /// <summary>
        /// Whether to use exponential backoff
        /// </summary>
        public bool UseExponentialBackoff { get; set; }
        
        /// <summary>
        /// Maximum delay in seconds (cap for exponential backoff)
        /// </summary>
        public int MaxDelaySeconds { get; set; }
        
        /// <summary>
        /// Calculates the delay for a specific retry attempt
        /// </summary>
        public TimeSpan CalculateDelay(int retryAttempt)
        {
            if (!ShouldRetry || retryAttempt >= MaxRetries)
            {
                return TimeSpan.Zero;
            }

            if (!UseExponentialBackoff)
            {
                return TimeSpan.FromSeconds(BaseDelaySeconds);
            }

            // Exponential backoff: delay = baseDelay * 2^(attempt - 1)
            var exponentialDelay = BaseDelaySeconds * Math.Pow(2, retryAttempt);
            var cappedDelay = Math.Min(exponentialDelay, MaxDelaySeconds);
            
            return TimeSpan.FromSeconds(cappedDelay);
        }
    }

    /// <summary>
    /// Types of download errors
    /// </summary>
    public enum DownloadErrorType
    {
        /// <summary>
        /// Unknown or unclassified error
        /// </summary>
        Unknown,
        
        /// <summary>
        /// Network connectivity issues (timeout, connection refused, etc.)
        /// </summary>
        NetworkError,
        
        /// <summary>
        /// HTTP 4xx client errors (403 Forbidden, 404 Not Found, etc.)
        /// </summary>
        ClientError,
        
        /// <summary>
        /// HTTP 5xx server errors (500 Internal Server Error, 503 Service Unavailable, etc.)
        /// </summary>
        ServerError,
        
        /// <summary>
        /// Rate limiting or too many requests (429)
        /// </summary>
        RateLimitError,
        
        /// <summary>
        /// Authentication or authorization failures
        /// </summary>
        AuthenticationError,
        
        /// <summary>
        /// Video unavailable, deleted, or geo-restricted
        /// </summary>
        ContentUnavailable,
        
        /// <summary>
        /// Disk space or file system errors
        /// </summary>
        DiskError,
        
        /// <summary>
        /// Invalid URL or malformed request
        /// </summary>
        InvalidUrl,
        
        /// <summary>
        /// Extraction or parsing errors
        /// </summary>
        ExtractionError
    }

    /// <summary>
    /// Factory for creating retry strategies based on error types
    /// </summary>
    public static class RetryStrategyFactory
    {
        /// <summary>
        /// Gets the appropriate retry strategy for an error type
        /// </summary>
        public static RetryStrategy GetStrategy(DownloadErrorType errorType)
        {
            return errorType switch
            {
                // Network errors: retry with exponential backoff
                DownloadErrorType.NetworkError => new RetryStrategy
                {
                    ErrorType = errorType,
                    ShouldRetry = true,
                    MaxRetries = 5,
                    BaseDelaySeconds = 10,
                    UseExponentialBackoff = true,
                    MaxDelaySeconds = 300 // 5 minutes max
                },
                
                // Server errors: retry with exponential backoff
                DownloadErrorType.ServerError => new RetryStrategy
                {
                    ErrorType = errorType,
                    ShouldRetry = true,
                    MaxRetries = 4,
                    BaseDelaySeconds = 30,
                    UseExponentialBackoff = true,
                    MaxDelaySeconds = 600 // 10 minutes max
                },
                
                // Rate limiting: retry with aggressive exponential backoff
                DownloadErrorType.RateLimitError => new RetryStrategy
                {
                    ErrorType = errorType,
                    ShouldRetry = true,
                    MaxRetries = 3,
                    BaseDelaySeconds = 60,
                    UseExponentialBackoff = true,
                    MaxDelaySeconds = 1800 // 30 minutes max
                },
                
                // Extraction errors: retry a few times (might be temporary)
                DownloadErrorType.ExtractionError => new RetryStrategy
                {
                    ErrorType = errorType,
                    ShouldRetry = true,
                    MaxRetries = 3,
                    BaseDelaySeconds = 5,
                    UseExponentialBackoff = false,
                    MaxDelaySeconds = 5
                },
                
                // Client errors: generally don't retry (permanent failures)
                DownloadErrorType.ClientError => new RetryStrategy
                {
                    ErrorType = errorType,
                    ShouldRetry = false,
                    MaxRetries = 0,
                    BaseDelaySeconds = 0,
                    UseExponentialBackoff = false,
                    MaxDelaySeconds = 0
                },
                
                // Authentication errors: don't retry (need user intervention)
                DownloadErrorType.AuthenticationError => new RetryStrategy
                {
                    ErrorType = errorType,
                    ShouldRetry = false,
                    MaxRetries = 0,
                    BaseDelaySeconds = 0,
                    UseExponentialBackoff = false,
                    MaxDelaySeconds = 0
                },
                
                // Content unavailable: don't retry (permanent)
                DownloadErrorType.ContentUnavailable => new RetryStrategy
                {
                    ErrorType = errorType,
                    ShouldRetry = false,
                    MaxRetries = 0,
                    BaseDelaySeconds = 0,
                    UseExponentialBackoff = false,
                    MaxDelaySeconds = 0
                },
                
                // Disk errors: don't retry (need manual intervention)
                DownloadErrorType.DiskError => new RetryStrategy
                {
                    ErrorType = errorType,
                    ShouldRetry = false,
                    MaxRetries = 0,
                    BaseDelaySeconds = 0,
                    UseExponentialBackoff = false,
                    MaxDelaySeconds = 0
                },
                
                // Invalid URL: don't retry (permanent)
                DownloadErrorType.InvalidUrl => new RetryStrategy
                {
                    ErrorType = errorType,
                    ShouldRetry = false,
                    MaxRetries = 0,
                    BaseDelaySeconds = 0,
                    UseExponentialBackoff = false,
                    MaxDelaySeconds = 0
                },
                
                // Unknown errors: retry with moderate backoff
                _ => new RetryStrategy
                {
                    ErrorType = DownloadErrorType.Unknown,
                    ShouldRetry = true,
                    MaxRetries = 3,
                    BaseDelaySeconds = 15,
                    UseExponentialBackoff = true,
                    MaxDelaySeconds = 120
                }
            };
        }

        /// <summary>
        /// Classifies an error message into an error type
        /// </summary>
        public static DownloadErrorType ClassifyError(string? errorMessage)
        {
            if (string.IsNullOrWhiteSpace(errorMessage))
            {
                return DownloadErrorType.Unknown;
            }

            var message = errorMessage.ToLowerInvariant();

            // Network errors
            if (message.Contains("timeout") || message.Contains("connection") || 
                message.Contains("network") || message.Contains("socket"))
            {
                return DownloadErrorType.NetworkError;
            }

            // Rate limiting
            if (message.Contains("429") || message.Contains("too many requests") || 
                message.Contains("rate limit"))
            {
                return DownloadErrorType.RateLimitError;
            }

            // Server errors
            if (message.Contains("500") || message.Contains("502") || 
                message.Contains("503") || message.Contains("504") ||
                message.Contains("internal server error") || message.Contains("service unavailable"))
            {
                return DownloadErrorType.ServerError;
            }

            // Client errors
            if (message.Contains("403") || message.Contains("404") || 
                message.Contains("400") || message.Contains("forbidden") ||
                message.Contains("not found") || message.Contains("bad request"))
            {
                return DownloadErrorType.ClientError;
            }

            // Authentication
            if (message.Contains("401") || message.Contains("unauthorized") || 
                message.Contains("authentication") || message.Contains("login required"))
            {
                return DownloadErrorType.AuthenticationError;
            }

            // Content unavailable
            if (message.Contains("unavailable") || message.Contains("deleted") || 
                message.Contains("geo") || message.Contains("region") ||
                message.Contains("private") || message.Contains("removed"))
            {
                return DownloadErrorType.ContentUnavailable;
            }

            // Disk errors
            if (message.Contains("disk") || message.Contains("space") || 
                message.Contains("filesystem") || message.Contains("permission"))
            {
                return DownloadErrorType.DiskError;
            }

            // Invalid URL
            if (message.Contains("invalid url") || message.Contains("malformed"))
            {
                return DownloadErrorType.InvalidUrl;
            }

            // Extraction errors
            if (message.Contains("extract") || message.Contains("parse") || 
                message.Contains("format"))
            {
                return DownloadErrorType.ExtractionError;
            }

            return DownloadErrorType.Unknown;
        }
    }
}