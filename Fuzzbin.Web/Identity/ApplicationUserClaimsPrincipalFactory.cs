using System.Security.Claims;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.Options;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Web.Identity
{
    /// <summary>
    /// Customizes the identity claims to surface display names and profile metadata.
    /// </summary>
    public class ApplicationUserClaimsPrincipalFactory
        : UserClaimsPrincipalFactory<ApplicationUser, IdentityRole<Guid>>
    {
        public ApplicationUserClaimsPrincipalFactory(
            UserManager<ApplicationUser> userManager,
            RoleManager<IdentityRole<Guid>> roleManager,
            IOptions<IdentityOptions> optionsAccessor)
            : base(userManager, roleManager, optionsAccessor)
        {
        }

        protected override async Task<ClaimsIdentity> GenerateClaimsAsync(ApplicationUser user)
        {
            var identity = await base.GenerateClaimsAsync(user);

            if (!string.IsNullOrWhiteSpace(user.DisplayName))
            {
                var currentName = identity.FindFirst(identity.NameClaimType);
                if (currentName is not null)
                {
                    identity.RemoveClaim(currentName);
                }

                identity.AddClaim(new Claim(identity.NameClaimType, user.DisplayName));
            }

            var initials = BuildInitials(user.DisplayName ?? user.UserName ?? "User");
            identity.AddClaim(new Claim("fz:initials", initials));

            return identity;
        }

        private static string BuildInitials(string input)
        {
            var parts = input.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 0)
            {
                return "U";
            }

            if (parts.Length == 1)
            {
                return char.ToUpperInvariant(parts[0][0]).ToString();
            }

            return string.Concat(char.ToUpperInvariant(parts[0][0]), char.ToUpperInvariant(parts[^1][0]));
        }
    }
}
