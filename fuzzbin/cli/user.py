"""CLI commands for user management."""

import argparse
import asyncio
import getpass
import sys

import structlog

# Lazy imports to avoid circular dependencies
logger = structlog.get_logger(__name__)


async def set_password(username: str, password: str | None = None) -> bool:
    """
    Set or update password for a user.

    Args:
        username: Username to update
        password: New password (if None, prompts interactively)

    Returns:
        True if successful, False otherwise
    """
    import fuzzbin
    from fuzzbin.auth import hash_password

    # Initialize fuzzbin
    await fuzzbin.configure()

    # Prompt for password if not provided
    if password is None:
        password = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Error: Passwords do not match", file=sys.stderr)
            return False

    if len(password) < 8:
        print("Error: Password must be at least 8 characters", file=sys.stderr)
        return False

    # Hash the password
    password_hash = hash_password(password)

    # Update in database
    repo = await fuzzbin.get_repository()

    if repo._connection is None:
        raise RuntimeError("Database connection not initialized")

    # Check if user exists
    cursor = await repo._connection.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = await cursor.fetchone()

    if not row:
        print(f"Error: User '{username}' not found", file=sys.stderr)
        return False

    # Update password
    from datetime import datetime, timezone

    await repo._connection.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE username = ?",
        (password_hash, datetime.now(timezone.utc).isoformat(), username),
    )
    await repo._connection.commit()

    print(f"Password updated successfully for user '{username}'")
    logger.info("password_set_via_cli", username=username)
    return True


async def list_users() -> None:
    """List all users in the database."""
    import fuzzbin

    await fuzzbin.configure()
    repo = await fuzzbin.get_repository()

    if repo._connection is None:
        raise RuntimeError("Database connection not initialized")

    cursor = await repo._connection.execute(
        "SELECT id, username, is_active, created_at, last_login_at FROM users"
    )
    rows = await cursor.fetchall()

    if not rows:
        print("No users found")
        return

    print(f"{'ID':<4} {'Username':<20} {'Active':<8} {'Created':<20} {'Last Login':<20}")
    print("-" * 76)
    for row in rows:
        user_id, username, is_active, created_at, last_login = row
        active_str = "Yes" if is_active else "No"
        last_login_str = last_login[:19] if last_login else "Never"
        created_str = created_at[:19] if created_at else "Unknown"
        print(f"{user_id:<4} {username:<20} {active_str:<8} {created_str:<20} {last_login_str:<20}")


def main() -> None:
    """Main entry point for user CLI commands."""
    parser = argparse.ArgumentParser(
        prog="fuzzbin-user",
        description="Fuzzbin user management commands",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # set-password command
    set_pw_parser = subparsers.add_parser(
        "set-password",
        help="Set password for a user",
        description="Update the password for an existing user account",
    )
    set_pw_parser.add_argument(
        "--username",
        "-u",
        default="admin",
        help="Username to update (default: admin)",
    )
    set_pw_parser.add_argument(
        "--password",
        "-p",
        help="New password (if not provided, will prompt interactively)",
    )

    # list command
    subparsers.add_parser(
        "list",
        help="List all users",
        description="Display all users in the database",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "set-password":
        success = asyncio.run(set_password(args.username, args.password))
        sys.exit(0 if success else 1)
    elif args.command == "list":
        asyncio.run(list_users())
        sys.exit(0)


if __name__ == "__main__":
    main()
