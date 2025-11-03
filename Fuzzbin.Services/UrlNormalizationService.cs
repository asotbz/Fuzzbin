using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using System.Web;

namespace Fuzzbin.Services
{
    /// <summary>
    /// Provides advanced URL normalization to detect duplicate URLs with variations
    /// </summary>
    public class UrlNormalizationService
    {
        // Common query parameters that don't affect the actual content
        private static readonly HashSet<string> IgnorableQueryParameters = new(StringComparer.OrdinalIgnoreCase)
        {
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "fbclid", "gclid", "msclkid", "_ga", "mc_cid", "mc_eid",
            "ref", "referrer", "source", "from"
        };

        // YouTube-specific patterns
        private static readonly Regex YouTubeVideoIdRegex = new(
            @"(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^""&?\/\s]{11})",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        /// <summary>
        /// Normalizes a URL for consistent comparison
        /// </summary>
        public string NormalizeUrl(string url)
        {
            if (string.IsNullOrWhiteSpace(url))
            {
                return string.Empty;
            }

            url = url.Trim();

            // Handle YouTube URLs specially
            if (IsYouTubeUrl(url))
            {
                return NormalizeYouTubeUrl(url);
            }

            try
            {
                var uri = new Uri(url, UriKind.Absolute);
                
                // Normalize the scheme (always use lowercase)
                var scheme = uri.Scheme.ToLowerInvariant();
                
                // Normalize the host (remove www., lowercase)
                var host = uri.Host.ToLowerInvariant();
                if (host.StartsWith("www."))
                {
                    host = host.Substring(4);
                }
                
                // Normalize the path (remove trailing slash, decode, lowercase)
                var path = Uri.UnescapeDataString(uri.AbsolutePath).ToLowerInvariant();
                if (path.EndsWith("/") && path.Length > 1)
                {
                    path = path.TrimEnd('/');
                }
                
                // Normalize query parameters (sort, remove ignorable ones)
                var queryParams = NormalizeQueryString(uri.Query);
                
                // Reconstruct the URL
                var normalizedUrl = $"{scheme}://{host}{path}";
                if (!string.IsNullOrEmpty(queryParams))
                {
                    normalizedUrl += $"?{queryParams}";
                }
                
                // Don't include fragment (hash) as it's client-side only
                
                return normalizedUrl;
            }
            catch (UriFormatException)
            {
                // If it's not a valid URI, just return the lowercase trimmed version
                return url.ToLowerInvariant();
            }
        }

        /// <summary>
        /// Checks if two URLs are equivalent after normalization
        /// </summary>
        public bool AreUrlsEquivalent(string url1, string url2)
        {
            if (string.IsNullOrWhiteSpace(url1) && string.IsNullOrWhiteSpace(url2))
            {
                return true;
            }

            if (string.IsNullOrWhiteSpace(url1) || string.IsNullOrWhiteSpace(url2))
            {
                return false;
            }

            return NormalizeUrl(url1).Equals(NormalizeUrl(url2), StringComparison.Ordinal);
        }

        /// <summary>
        /// Normalizes YouTube URLs to a canonical format
        /// </summary>
        private string NormalizeYouTubeUrl(string url)
        {
            var videoId = ExtractYouTubeVideoId(url);
            if (string.IsNullOrEmpty(videoId))
            {
                // Can't extract video ID, return lowercase URL without YouTube-specific handling
                return url.ToLowerInvariant();
            }

            // Return canonical YouTube format
            return $"https://youtube.com/watch?v={videoId}";
        }

        /// <summary>
        /// Extracts the YouTube video ID from various URL formats
        /// </summary>
        private string? ExtractYouTubeVideoId(string url)
        {
            var match = YouTubeVideoIdRegex.Match(url);
            return match.Success ? match.Groups[1].Value : null;
        }

        /// <summary>
        /// Checks if a URL is a YouTube URL
        /// </summary>
        private bool IsYouTubeUrl(string url)
        {
            return url.Contains("youtube.com", StringComparison.OrdinalIgnoreCase) ||
                   url.Contains("youtu.be", StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>
        /// Normalizes query string parameters
        /// </summary>
        private string NormalizeQueryString(string queryString)
        {
            if (string.IsNullOrWhiteSpace(queryString))
            {
                return string.Empty;
            }

            // Remove leading '?'
            if (queryString.StartsWith("?"))
            {
                queryString = queryString.Substring(1);
            }

            // Parse query parameters
            var parameters = HttpUtility.ParseQueryString(queryString);
            var normalizedParams = new SortedDictionary<string, string>(StringComparer.Ordinal);

            foreach (var key in parameters.AllKeys)
            {
                if (key == null || IgnorableQueryParameters.Contains(key))
                {
                    continue;
                }

                var value = parameters[key];
                if (!string.IsNullOrEmpty(value))
                {
                    // Store in lowercase for case-insensitive parameter names
                    normalizedParams[key.ToLowerInvariant()] = value;
                }
            }

            // Rebuild query string in sorted order
            if (normalizedParams.Count == 0)
            {
                return string.Empty;
            }

            return string.Join("&", normalizedParams.Select(kvp => 
                $"{Uri.EscapeDataString(kvp.Key)}={Uri.EscapeDataString(kvp.Value)}"));
        }

        /// <summary>
        /// Gets variations of a URL that should be considered equivalent
        /// </summary>
        public IEnumerable<string> GetUrlVariations(string url)
        {
            var variations = new List<string>();
            
            if (string.IsNullOrWhiteSpace(url))
            {
                return variations;
            }

            // Original URL
            variations.Add(url);

            // Normalized version
            var normalized = NormalizeUrl(url);
            if (!string.Equals(url, normalized, StringComparison.Ordinal))
            {
                variations.Add(normalized);
            }

            try
            {
                var uri = new Uri(url, UriKind.Absolute);
                
                // With and without www
                if (uri.Host.StartsWith("www.", StringComparison.OrdinalIgnoreCase))
                {
                    var withoutWww = url.Replace("://www.", "://", StringComparison.OrdinalIgnoreCase);
                    variations.Add(withoutWww);
                }
                else
                {
                    var withWww = url.Replace("://", "://www.", StringComparison.OrdinalIgnoreCase);
                    variations.Add(withWww);
                }

                // HTTP vs HTTPS
                if (uri.Scheme.Equals("https", StringComparison.OrdinalIgnoreCase))
                {
                    variations.Add(url.Replace("https://", "http://", StringComparison.OrdinalIgnoreCase));
                }
                else if (uri.Scheme.Equals("http", StringComparison.OrdinalIgnoreCase))
                {
                    variations.Add(url.Replace("http://", "https://", StringComparison.OrdinalIgnoreCase));
                }

                // With and without trailing slash
                if (uri.AbsolutePath.EndsWith("/"))
                {
                    variations.Add(url.TrimEnd('/'));
                }
                else
                {
                    variations.Add(url + "/");
                }
            }
            catch (UriFormatException)
            {
                // If it's not a valid URI, just return what we have
            }
            
            return variations;
        }
    }
}