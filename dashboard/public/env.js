// Runtime configuration placeholder. In every deployed environment (demo,
// production), the Docker image's entrypoint (see Dockerfile /
// docker-entrypoint.sh) overwrites this exact file at container startup
// with the real VITE_SUPABASE_URL/VITE_SUPABASE_ANON_KEY for that
// deployment, read from its own env vars -- that's what lets a single
// built ":release" image serve both demo and production against their own
// separate Supabase projects.
//
// Left empty here (and in local `npm run dev`/`vite build`), so
// src/lib/supabase-browser.js falls back to the build-time
// import.meta.env value from a local .env file, same as before this file
// existed.
window.__ENV__ = {};
