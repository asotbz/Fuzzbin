/**
 * Application version.
 *
 * In production Docker builds, this comes from VITE_APP_VERSION env var
 * set during the build process from the VERSION file.
 *
 * In development, falls back to "dev".
 */
export const APP_VERSION = import.meta.env.VITE_APP_VERSION || "dev"
