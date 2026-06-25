# Windows Packaging

Junas does not ship a Windows desktop artifact in this repo by default.

If a Windows SKU is shipped, build on a Windows runner with:

```powershell
uv sync --extra local --extra packaging
uv run python -m spacy download en_core_web_sm
uv run pyinstaller packaging/junas-local.spec
```

Required release gates:

- Authenticode-sign the produced executable and installer with the vendor certificate.
- Install as a per-user loopback service or startup task bound to `127.0.0.1:8765`.
- Enable `JUNAS_LOCAL_DAEMON_ACL_ENABLED=1`.
- Provide uninstall and update entries through the installer technology in use.
- Store the local daemon token in Windows Credential Manager or a user-only ACL file.
