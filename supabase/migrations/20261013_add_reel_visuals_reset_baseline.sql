-- Keep a stable rollback baseline for visuals reset.
-- reel_url/reel_s3_key keep the currently active media, while these base
-- fields store the pre-visuals media reference used by /visuals/reset.

alter table if exists public.reels
    add column if not exists reel_base_url text,
    add column if not exists reel_base_s3_key text;

