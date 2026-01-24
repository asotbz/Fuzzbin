#!/bin/bash
set -e

# Auto-generate JWT secret if not provided and not already persisted
JWT_SECRET_FILE="/config/jwt_secret.txt"

if [ -z "$FUZZBIN_API_JWT_SECRET" ]; then
    # Check if secret file exists
    if [ -f "$JWT_SECRET_FILE" ]; then
        echo "Loading JWT secret from $JWT_SECRET_FILE"
        export FUZZBIN_API_JWT_SECRET=$(cat "$JWT_SECRET_FILE")
    else
        echo "Generating new JWT secret..."
        # Ensure /config directory exists
        mkdir -p /config
        # Generate secret using Python
        NEW_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
        echo "$NEW_SECRET" > "$JWT_SECRET_FILE"
        chmod 600 "$JWT_SECRET_FILE"
        export FUZZBIN_API_JWT_SECRET="$NEW_SECRET"
        echo "JWT secret generated and saved to $JWT_SECRET_FILE"
    fi
fi

# Execute the main command
exec "$@"
