# Fuzzbin Single-User Mode

## Overview

Fuzzbin is configured to operate in **single-user mode**, meaning only one user account can be created and used. This design simplifies authentication and eliminates the need for complex user management features.

## Key Features

### 1. One User Account
- Only **one user account** can be created during the initial setup
- The user chooses their own username during setup
- No email address is required
- The account has full administrative access to all features

### 2. Username-Only Authentication
- Users log in with **username and password only**
- No email-based authentication or recovery
- Simple, straightforward login process

### 3. Password Reset Utility
Since there's no email-based password recovery, a separate command-line utility is provided:
- [`Fuzzbin.PasswordReset`](../Fuzzbin.PasswordReset/README.md) - Standalone console application
- Requires direct server access
- Secure password reset without email

## Implementation Details

### Enforcement Mechanisms

#### 1. Middleware Protection
The [`SingleUserEnforcementMiddleware`](Middleware/SingleUserEnforcementMiddleware.cs) blocks any API endpoints that might create additional users:
- Monitors requests to user creation endpoints
- Returns HTTP 403 if a user already exists
- Logs all blocked attempts

#### 2. Setup Validation
The setup wizard ([`Setup.razor`](Components/Pages/Setup.razor)) includes a user count check:
- Prevents creating additional users even if setup is rerun
- Displays clear message about single-user mode
- Logs warning if additional user creation is attempted

#### 3. No User Management UI
- No "Add User" buttons or forms
- No user invitation system
- No user management pages
- Profile page only allows changing display name and password

### Configuration

Single-user mode is **always enabled** and cannot be disabled. This is a core design decision for Fuzzbin.

## User Workflow

### Initial Setup
1. Run Fuzzbin for the first time
2. Complete the setup wizard
3. Create your admin account with chosen username
4. System prevents any additional accounts

### Daily Use
1. Log in with username and password
2. Access all features as the sole user
3. Change display name or password in profile if needed

### Password Recovery
If you forget your password:
1. Stop the Fuzzbin web application
2. Run the password reset utility from the server:
   ```bash
   Fuzzbin.PasswordReset --username yourusername --password NewPassword123
   ```
3. Restart Fuzzbin
4. Log in with new password

## Security Considerations

### Benefits
- ✅ Simplified authentication model
- ✅ No risk of unauthorized user creation
- ✅ Reduced attack surface (no user registration endpoints)
- ✅ Clear ownership of the Fuzzbin instance

### Best Practices
1. **Choose a strong password** during setup (minimum 8 characters)
2. **Keep the password reset utility secure** - only administrators should have access
3. **Regular backups** of the database include your user account
4. **Document your username** in a secure location

## Technical Architecture

### ASP.NET Core Identity
Fuzzbin still uses ASP.NET Core Identity for:
- Secure password hashing
- User authentication
- Session management
- Authorization policies

The single-user restriction is layered on top of Identity, not replacing it.

### Database Schema
The database still has all Identity tables, but:
- Only one row will exist in `AspNetUsers`
- Email fields contain placeholder values (`{username}@localhost`)
- All Identity features remain functional for the single user

## Troubleshooting

### "User already exists" Error During Setup
This means a user account was already created. Options:
1. Use the existing account (if you know the credentials)
2. Use the password reset utility to reset the password
3. Delete the database to start fresh (⚠️ loses all data)

### Cannot Create Additional Users
This is **by design**. Fuzzbin is intentionally limited to one user.

### Middleware Blocking Requests
If you see 403 errors related to user creation:
- This is the single-user enforcement working correctly
- Check application logs for details
- Verify no unauthorized access attempts

## Migration from Multi-User

If Fuzzbin previously supported multiple users, migrating to single-user mode:

1. **Identify the primary user** to keep
2. **Backup the database**
3. **Update to single-user version**
4. **Keep only one user** in the database
5. **Remove other user records** (optional, they won't be able to log in anyway)

## Support

For issues related to single-user mode:
1. Check the application logs
2. Verify middleware is registered in `Program.cs`
3. Ensure database permissions are correct
4. Review password reset utility documentation

## Related Documentation

- [Password Reset Utility](../Fuzzbin.PasswordReset/README.md)
- [Setup Guide](../Fuzzbin.implementation-guide.md)
- [Architecture Documentation](../Fuzzbin.architecture-csharp.md)