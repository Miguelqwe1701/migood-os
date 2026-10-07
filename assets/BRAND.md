# Brand assets

The launcher and site load these by PATH, so replacing a file here updates
everything with no code change.

    migood-logo.png     wordmark, transparent background (splash, headers, sign-in)
    migood-square.png   square app icon (startup splash, 512x512)
    migood-logo.svg     fallback placeholder, used only if the .png is missing
    migood-square.svg   fallback placeholder

## How the real artwork was prepared

`migood-logo.png` came from `migood-full-logo.png`. The flat black background
was knocked out to transparency using a soft alpha ramp just above the cutoff,
so edges do not stair-step against a light background, then the empty margin
was trimmed so the mark scales predictably.

`migood-square.png` came from `migood-square-logo.png`, padded to a square and
resized to 512x512.

## One thing to know

The wordmark's text is **white**. It reads correctly on a dark background - the
app is dark throughout - but it will disappear on a light page. If a light
theme ever happens, a dark-text variant is needed rather than reusing this one.

## Replacing them

Overwrite the .png files here. Sizes that work well:

  - wordmark: around 760x200, transparent PNG
  - square:   512x512 PNG (CSS applies the rounded corners)
