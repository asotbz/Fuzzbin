# Product Context

This file provides a high-level overview of the project and the expected product that will be created. Initially it is based upon productBrief.md and other available project information. This file is intended to be updated as the project evolves, and should be used to inform all other modes of the project's goals and context.

2025-10-13 11:10:19 - Log of updates made will be appended as footnotes to the end of this file.

*

## Project Goal

Create a modern, self-contained web application that automates acquisition, organization, enrichment, and playback of personal music video libraries using a single-language (C#) clean architecture deployed as one lightweight Docker container with zero external infrastructure dependencies.

## Key Features

- Music video ingest (yt-dlp) with queued, resilient, prioritized downloads
- Rich metadata aggregation (IMVDb primary, MusicBrainz secondary) with caching and resilience policies
- Library import, scanning, duplicate detection, and bulk file reorganization with flexible pattern-based naming
- Collection, playlist, tagging, and search facilities with advanced filtering and batch operations
- Kodi-compatible NFO generation and optional safe filename normalization
- Source verification (quality, authenticity, alternative source tracking)
- Real-time UI (Blazor Server + SignalR) with theming, keyboard shortcuts, integrated player
- Security: Identity, role management, CSRF protection, encrypted secrets, single-user mode
- Operational tooling: automated backups, metrics, structured logging, retry/circuit breaker policies

## Overall Architecture

Clean architecture layers: Web (Blazor Server UI + Hubs) -> Services (business logic, background workers, external API integration) -> Data (EF Core repositories, Unit of Work, specifications) -> Core (entities, interfaces, domain logic). Single container with embedded SQLite for persistence, IMemoryCache for performance, background processing via Channels, real-time updates via SignalR.

## Non-Functional Targets

- Idle memory <150MB, load memory <400MB
- Startup <5s
- Docker image <200MB
- Search latency <200ms, API responses <100ms, initial page load <1s

## Constraints & Philosophy

- Simplicity and portability favored over horizontal scalability
- Single embedded database; migration path to RDBMS deferred
- No external queue or cache services; rely on in-process primitives
- Resilience at network boundaries (Polly) to protect UI responsiveness

## Open Extension Areas (Future)

- Migration to multi-database support (PostgreSQL)
- Federation or remote library sharing
- Enhanced analytics / recommendation engine
- Plugin system for additional metadata providers

---

Footnotes / Update Log

(none yet)