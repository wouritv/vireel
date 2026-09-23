#!/bin/sh
# Regenerates env.js from this container's own env vars before nginx
# starts, so the same built image can serve any deployment (demo,
# production) against its own Supabase project -- see
# src/lib/supabase-browser.js and public/env.js for why this exists.
set -eu

cat <<EOF > /usr/share/nginx/html/env.js
window.__ENV__ = {
  VITE_SUPABASE_URL: "${VITE_SUPABASE_URL:-}",
  VITE_SUPABASE_ANON_KEY: "${VITE_SUPABASE_ANON_KEY:-}"
};
EOF

exec "$@"
