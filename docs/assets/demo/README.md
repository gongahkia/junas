# README Demo Capture

The README demo GIF and fallback PNG are generated from the real one-command demo:

```sh
vhs docs/assets/demo/junas-demo.tape
magick /tmp/junas-demo.gif -coalesce /tmp/junas-demo-frame-%03d.png
cp /tmp/junas-demo-frame-120.png /tmp/junas-demo-fallback.png
```

Current hosted assets:

- GIF: `https://github.com/gongahkia/junas/releases/download/readme-demo-assets-2026-06-30/junas-demo.gif`
- Static fallback: `https://github.com/gongahkia/junas/releases/download/readme-demo-assets-2026-06-30/junas-demo-fallback.png`

Generated hashes are not stable because the demo prints a dynamic local port and elapsed runtime. Do not commit generated GIF/PNG binaries to the repo. Upload refreshed media to a GitHub-hosted asset location, then update the README URLs here.
