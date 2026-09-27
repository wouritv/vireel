# Film summary background music

Optional instrumental (no lyrics) music bed, mixed at low volume under the
AI voice-over narration in film summaries. This repo ships **no audio
files** -- until tracks are added below, this feature is inactive and every
render behaves exactly as before.

## How it works

`film_summary_render.resolve_background_music_track(mood)` picks one file
from `music/<mood>/`. The planning AI chooses one `mood` for the whole film
(see `PLANNING_SYSTEM_PROMPT`'s "BACKGROUND MUSIC MOOD" section in
`film_summary.py`) based on the movie's actual tone. If that mood's folder
has no tracks, it falls back to `music/neutral/`; if that's empty too, no
music plays -- nothing fails either way.

The chosen track is only ever mixed under `voice_over` segments (the
narration-only parts of the summary). It is never mixed under
`original_dialogue` or `breathing` segments, where the film's own audio is
meant to be the only thing heard.

## Adding tracks

Drop one or more audio files directly into the matching mood folder:

```
music/tense/track-1.mp3
music/dark/track-1.mp3
music/hopeful/track-1.mp3
music/romantic/track-1.mp3
music/melancholic/track-1.mp3
music/triumphant/track-1.mp3
music/comedic/track-1.mp3
music/neutral/track-1.mp3
```

Supported extensions: `.mp3`, `.wav`, `.m4a`, `.aac`. If a mood folder has
several tracks, the first one alphabetically is used -- name files so the
one you want picked first sorts first (e.g. `01-track.mp3`).

Requirements for any track added here:

- **Instrumental only, no vocals/lyrics** -- it plays under spoken
  narration, so lyrics would compete with it.
- **Genuinely royalty-free / licensed for this use** -- e.g. tracks from
  the YouTube Audio Library or Pixabay Music filtered to "no attribution
  required", or any track whose license explicitly covers commercial video
  use without per-video clearance. Keep a note of the source/license
  somewhere (e.g. this README) for each track you add.
- A short track is fine -- it loops automatically to cover longer segments
  (`film_summary_render.mix_background_music`).

## Tuning

- `FILM_SUMMARY_MUSIC_DIR` (default `music`): where mood folders live.
- `FILM_SUMMARY_MUSIC_VOLUME` (default `0.10`): relative mix volume of the
  music bed under the narration.
