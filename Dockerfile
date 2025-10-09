# Multi-stage build for Fuzzbin C# application
# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Copy solution and project files
COPY Fuzzbin.sln ./
COPY Fuzzbin.Core/Fuzzbin.Core.csproj Fuzzbin.Core/
COPY Fuzzbin.Data/Fuzzbin.Data.csproj Fuzzbin.Data/
COPY Fuzzbin.Web/Fuzzbin.Web.csproj Fuzzbin.Web/
COPY Fuzzbin.Tests/Fuzzbin.Tests.csproj Fuzzbin.Tests/

# Restore dependencies
RUN dotnet restore

# Copy source code
COPY . .

# Build the application
WORKDIR /src/Fuzzbin.Web
RUN dotnet build -c Release --no-restore

# Publish the application
RUN dotnet publish -c Release --no-build -o /app/publish

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS runtime
WORKDIR /app

# Install yt-dlp and ffmpeg
RUN apt-get update && \
    apt-get install -y \
        python3 \
        ffmpeg \
        curl \
        wget && \
    wget -O /usr/local/bin/yt-dlp https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp && \
    chmod a+rx /usr/local/bin/yt-dlp && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs /app/media/videos /app/media/thumbnails

# Copy published application
COPY --from=build /app/publish .

# Set environment variables
ENV ASPNETCORE_URLS=http://+:8080
ENV ASPNETCORE_ENVIRONMENT=Production
ENV DOTNET_RUNNING_IN_CONTAINER=true

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Volume for persistent data
VOLUME ["/app/data", "/app/logs", "/app/media"]

# Run the application
ENTRYPOINT ["dotnet", "Fuzzbin.Web.dll"]