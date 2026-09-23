import { createClient } from "@supabase/supabase-js";

let client = null;

// Read at runtime (window.__ENV__, injected by the Docker image's
// entrypoint from container env vars -- see public/env.js and
// Dockerfile) before falling back to the build-time Vite value. This is
// what lets one built image (":release") serve both the demo and
// production deployments against their own separate Supabase projects,
// rather than baking a single project's URL/key into the JS bundle at
// build time.
function _runtimeOrBuildTimeEnv(key) {
    return (typeof window !== "undefined" && window.__ENV__?.[key]) || import.meta.env[key];
}

export function getSupabaseBrowserClient() {
    if (client) return client;

    const url = _runtimeOrBuildTimeEnv("VITE_SUPABASE_URL");
    const anonKey = _runtimeOrBuildTimeEnv("VITE_SUPABASE_ANON_KEY");

    if (!url || !anonKey) {
        throw new Error("Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY");
    }

    client = createClient(url, anonKey, {
        auth: {
            persistSession: true,
            autoRefreshToken: true,
            detectSessionInUrl: true,
        },
    });

    return client;
}