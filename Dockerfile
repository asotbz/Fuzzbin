# Stage 1: Build frontend
ARG NODE_VERSION=24
FROM node:${NODE_VERSION} AS frontend-build

ARG VERSION=0.0.0

WORKDIR /app/frontend

# Copy package files first for better caching
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies
RUN npm ci

# Copy remaining frontend files
COPY frontend/ ./

# Build with empty API base URL for same-origin requests and version
ENV VITE_API_BASE_URL=""
ENV VITE_APP_VERSION=${VERSION}
RUN npm run build


# Stage 2: Final image with Python backend
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}

ARG VERSION=0.0.0

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy VERSION file and Python project files
COPY VERSION pyproject.toml README.md ./
COPY fuzzbin/ ./fuzzbin/

# Set version environment variable
ENV FUZZBIN_VERSION=${VERSION}

# Install Python dependencies (production only)
RUN pip install --no-cache-dir ".[prod]"
# deno (yt-dlp dependency)
ARG DENO_VERSION=2.6.7
COPY --from=denoland/deno:bin-${DENO_VERSION} /deno /usr/local/bin/deno

# Copy frontend build from stage 1 (includes dist and public assets)
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY --from=frontend-build /app/frontend/public ./frontend/dist

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set environment variables for Docker deployment
ENV FUZZBIN_DOCKER=1
ENV FUZZBIN_API_HOST=0.0.0.0

# Expose API port
EXPOSE 8000

# Define volumes for persistent data
VOLUME ["/config", "/music_videos"]

# Use entrypoint for JWT secret management
ENTRYPOINT ["docker-entrypoint.sh"]

# Default command
CMD ["fuzzbin-api"]
