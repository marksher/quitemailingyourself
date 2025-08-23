# Pocketish
An open-source, intelligent link saver with:
- **Google-only login** (OAuth 2.0 / OIDC)
- **Bookmarklet** and **iOS Share Target (PWA)**
- **FastAPI** backend
- **SQS** optional queue + background worker
- **MySQL** (production) with FULLTEXT search and **SQLite** (dev) fallback
- **OpenAI**-powered summaries, tags, and categories

## Quick start (local dev)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: GOOGLE_* keys + OPENAI_API_KEY
uvicorn backend.app:app --reload --port 8000
```
Open http://localhost:8000, click **Login with Google**, then drag the **Save to Pocketish** bookmarklet to your bookmarks bar.

### Environment
Copy `.env.example` to `.env` and fill:
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `OAUTH_REDIRECT_URI` (e.g., http://localhost:8000/auth/callback)
- `SESSION_SECRET` (random string)
- `DATABASE_URL` (mysql+pymysql://user:pass@host:3306/dbname) or leave blank for SQLite
- `OPENAI_API_KEY` (optional for summaries)
- Optional SQS: `SQS_QUEUE_URL`, `AWS_REGION`

### PWA Share Target (iOS)
After logging in, on iPhone Safari: Share → **Add to Home Screen**. The app registers as a Share Target; shared URLs are queued automatically.

### Full-text search
- MySQL: uses `FULLTEXT(title, summary)` + `MATCH ... AGAINST`.
- SQLite: fallback search via `LIKE` (FTS5 not required).

### Services via Docker
```bash
docker-compose up -d
# create SQS queue in LocalStack (optional)
aws --endpoint-url http://localhost:4566 sqs create-queue --queue-name pocketish
```
Then run the API locally (still hitting MySQL in docker).

### Worker
```bash
python -m worker.worker
```
The worker consumes local tasks (from API) and SQS if configured.

---
MIT License.
