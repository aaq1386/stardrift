# STARDRIFT — Changelog

This file records notable gameplay, visual, audio, and technical changes.
The main README remains unchanged.

## Unreleased

### Added
- Six space regions: Nebula, Crimson, Emerald, Deep Space, Solar, and Ice Frontier.
- Region-specific backgrounds, ambient glows, star colors, HUD labels, and brick palettes.
- Automatic region cycling every five levels, repeating after level 30.
- Optional looping background music from `assets/music/OutThere.ogg`.
- Background music and sound effects can be toggled together with `M`.

### Changed
- Level brick colors now use the active region's palette.
- Star rendering supports region-specific colors while retaining its default behavior.
- Brick hit points are assigned using deterministic level and grid-position rules.

### Notes
- Background music is optional; the game can continue without an available audio device
  or the music file.
- Verify the music track's attribution and license requirements before redistributing it.
