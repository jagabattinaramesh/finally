# FinAlly E2E Tests

Playwright end-to-end tests for the FinAlly trading workstation.

## Run locally (app must be running on http://localhost:8000)

```bash
cd test
npm install
npx playwright install chromium
npm test
```

## Run against containerized app

```bash
cd test
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

The Playwright runner connects to the `app` service via `http://app:8000`.
All E2E runs use `LLM_MOCK=true` for deterministic mock LLM responses.

## Override base URL

```bash
E2E_BASE_URL=http://localhost:8000 npm test
```
