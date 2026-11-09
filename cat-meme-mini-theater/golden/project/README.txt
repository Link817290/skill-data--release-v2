Reproduce the accepted reference film

Requirements: Node.js 22, FFmpeg, Chrome/Chromium or Edge, and a Chinese font.
Run npm ci, npm run prepare-assets, then npm run render -- --output /absolute/path/final.mp4.
Set CHROME_PATH when the browser is not in a detected Windows location.
Microsoft YaHei was used for the accepted render; another Chinese font can change typography.
Generated transparent frames and soundtrack are intentionally omitted from the delivery ZIP and are regenerated locally.
The packaged source includes original media and the generation script.
