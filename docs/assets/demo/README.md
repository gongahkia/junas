# README Demo Capture

`hero-ascii-redaction.svg` is the committed README-friendly hero loop for issue #4.
It is an 8-second SVG animation showing an iTerm-style fake AWS secret beside an
ASCII-redacted virtual-camera preview. It uses fake credentials only:
`AWS_SECRET_ACCESS_KEY=AKIA-FAKE-DEMO-0000`.

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
