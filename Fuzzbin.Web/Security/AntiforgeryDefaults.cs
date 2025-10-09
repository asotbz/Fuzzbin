using Microsoft.AspNetCore.Antiforgery;

namespace Fuzzbin.Web.Security
{
    /// <summary>
    /// Shared antiforgery configuration values so cookie names stay consistent.
    /// </summary>
    public static class AntiforgeryDefaults
    {
        public const string CookieName = "fz-antiforgery";

        public const string HeaderName = "X-CSRF-TOKEN";
    }
}
