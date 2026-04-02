# API Folder

This folder is a compatibility surface.

- `api/main.py` re-exports the canonical FastAPI app from `backend.main`
- `api/client.py` re-exports the canonical sync and async Python clients from `backend.client`
- `api/schemas.py` re-exports the canonical Pydantic models from `backend.schemas`

New runtime work should target `backend/`, and new Python integration work should target `src/noupe/client.py` via `noupe.client`.
