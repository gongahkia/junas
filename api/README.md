# API Folder

This folder is a compatibility surface.

- `api/main.py` re-exports the canonical FastAPI app from `backend.main`
- `api/schemas.py` re-exports the canonical Pydantic models from `backend.schemas`

New runtime and integration work should target `backend/`, not this folder.
