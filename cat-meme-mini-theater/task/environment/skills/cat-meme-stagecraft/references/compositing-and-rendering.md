# Compositing and deterministic rendering

## Keying decisions

Sample the backing color from unobstructed regions of the actual source. Compression, lighting, and colored backdrops vary; a shared preset can remove gray fur from one clip while leaving a green border in another. Begin with a conservative similarity range, then adjust edge softness and spill suppression separately. Broadening the key is not a universal fix for spill.

Check ears, whiskers, moving limbs, pale fur, and any furniture already embedded in the clip. Inspect several moments against both a neutral surface and the intended background. If the subject becomes hollow or translucent, reduce the selection range before increasing edge smoothing. A soft, low-resolution source is different from a keying defect; do not claim to recover detail that was never present.

Crop transparent margins only after measuring the subject's motion across the usable range. A bounding box taken from one frame may cut off the next gesture. Small opaque borders in the source may also defeat automatic alpha-bound detection. Preserve enough margin to avoid slicing moving edges.

## Choosing a media representation

Browser effects keep the source compact but depend on the selected Remotion version and rendering backend. Test a representative rendered frame in the actual environment, not only in Studio.

Preprocessed alpha video or transparent image sequences are alternatives. Image sequences make frame addressing explicit and avoid video-alpha decoder differences, at the cost of disk usage. If using them, retain source-to-frame metadata and a regeneration script; do not require the recipient to discover how a temporary cache was made.

Choose an explicit relationship between source time and composition frames. Account for source frame rate, trimming, and playback speed. Clamp a held last frame or deliberately loop a usable range; accidental modulo loops can reset a gesture at the wrong point. Keep sound separate if a visual hold, speed change, or loop should not repeat the original audio.

## Staging and export

Build a small set of reusable components for performers, dialogue, role labels, and story graphics. Keep layout and typography consistent across shots, while allowing meaningful emphasis to break that pattern. Treat the environment, performers and props, story graphics, and captions as separate layers with deliberate overlap. Embedded furniture belongs to the performer's silhouette; adding a second desk may hide the intended activity.

Represent shot boundaries explicitly, preferably with start-inclusive and end-exclusive frame ranges. Convert between seconds and frames in one place. For animation inside a shot, derive a local frame from the composition frame minus the shot start; track source trim and speed separately. This keeps a moved shot from inheriting an already-completed entrance or an unintended source position. Clamp one-time entrances and holds; loop only actions that were selected to repeat.

Scale the visible subject rather than its original padded video rectangle. Treat cropped busts as close-ups or place their lower edges behind a justified foreground. Keep full-body characters in contact with a plausible surface. Use contrast, shadows, and grading to make layers legible without obscuring the performance.

Drive animation from the composition frame, including transitions and generated effects. Seed any procedural variation that must be reproducible. Use local assets and wait for required fonts and media before rendering. Inspect the installed package APIs instead of assuming an example from a different release applies.

Pin compatible Remotion package versions. Validate the output with a media probe and a full decode; a successful bundling step does not establish that all frames, fonts, and audio made it into the encoded file.
