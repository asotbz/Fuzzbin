# System Patterns

This file documents recurring patterns and standards used in the project.
2025-10-13 11:10:56 - Log of updates made.

*

## Coding Patterns

* Clean Architecture layering (Web > Services > Data > Core) enforcing inward dependency rule
* Specification pattern for composable query logic (filtering, sorting, paging)
* Async-first service methods; background coordination via Channels
* Strongly-typed options/config objects (e.g., DownloadWorkerOptions, MetadataSettings)
* Interface-driven services to facilitate unit testing & substitution

## Architectural Patterns

* Single-container deployment (monolithic but internally layered)
* Repository + Unit of Work abstraction over EF Core
* Background worker pipeline using System.Threading.Channels for backpressure
* Real-time notifications via SignalR hubs (job progress, video updates) decoupled through notifier interfaces
* Resilience layer using Polly (retry, circuit breaker, timeout) around external HTTP boundaries
* Caching decorator approach (IMemoryCache) for metadata lookups with TTL
* Hash-based duplicate detection (SHA-256) plus fuzzy metadata matching
* Template-driven file path and NFO generation with token substitution
* Source verification workflow: metadata extraction -> comparison -> scoring -> manual override path

## Testing Patterns

* Unit tests for services with mocked repositories/interfaces
* Specification tests to validate query predicates and ordering
* Integration-style tests for repository behavior against EF Core + SQLite
* Focus on deterministic test data builders for entities

## UI/Interaction Patterns

* Blazor Server components leveraging cascading parameters for shared state (theme, auth)
* Loading/empty/content pattern via shared LoadingContent component
* Keyboard shortcut service centralizing key binding logic
* Context menu + bulk selection patterns for batch operations

## Reliability & Operations Patterns

* Structured logging (Serilog) with enrichment and rolling file sinks
* Periodic background jobs (thumbnail generation, metadata refresh) scheduled via internal job service abstractions
* Configuration via strongly-typed options and environment variable overrides
* Graceful cancellation and cooperative shutdown for background tasks

## Security Patterns

* Centralized middleware for setup and single-user enforcement
* Antiforgery token handling with explicit cookie lifecycle management
* Encrypted secret storage using Data Protection API

---

Footnotes / Update Log

(none yet)