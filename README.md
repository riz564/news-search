
# News Search (Guardian + NYT) — API + React UI

## Run locally (without Docker)
```bash
export GUARDIAN_API_KEY=your_guardian_key
export NYT_API_KEY=your_nyt_key
python app.py
# API: http://localhost:8080/search?query=apple
# OpenAPI: http://localhost:8080/openapi.json
# UI (after building CRA & copying to ui_build) served at http://localhost:8080/
