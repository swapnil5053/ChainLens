# Running ChainLens

Two ways in. The first needs Node only and no backend at all; the second runs the real
system, database included.

---

## 1. The interface alone, no backend

The demo adapter serves the real 29-contract corpus from static fixtures and runs
retrieval in the browser over real chunk text at real character offsets. No database, no
API key, no Python.

```bash
cd apps/web
npm install
npm run dev        # then open the URL it prints, usually http://localhost:5173
```

- The landing page is at `/`.
- The reader is at `/app.html`.

What to try, in order:

1. **Pick a contract** from the selector in the reader's header.
   `Apollo-Endosurgery-Manufacturing-and-Supply-Agreement` is a good first one: fifteen
   pages with clear clause structure.
2. **Ask a question.** Click one of the five examples, or type
   `What is the cap on liability?` and press Enter.
3. **Hover a source chip.** Its clause lights up in the contract beside it. Click it and
   the document scrolls to that clause and marks the exact character span. This is the
   thing the whole design is built around.
4. **Switch contracts.** The question and the previous answer clear, so you never read an
   old finding against a new document.

Uploading a PDF needs the backend, because parsing, clause detection and embedding all
happen in Python. The demo says so rather than failing quietly.

Verify it the way CI does:

```bash
npm run verify     # typecheck, smoke test, production build, design detector
```

---

## 2. The whole system

Two terminals. The database runs in Docker; everything else is local.

### Once

```powershell
docker run -d --name chainlens-db `
  -e POSTGRES_USER=chainlens -e POSTGRES_PASSWORD=chainlens -e POSTGRES_DB=chainlens `
  -p 5433:5432 pgvector/pgvector:pg16

docker update --restart unless-stopped chainlens-db   # survives a Docker restart

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

Copy-Item .env.example .env
```

Then set `CHAINLENS_DATABASE_URL` in `.env` to match that container:

```
CHAINLENS_DATABASE_URL=postgresql+psycopg://chainlens:chainlens@localhost:5433/chainlens
```

Port 5433 rather than the default 5432, because a Postgres already listening on 5432
belongs to something else and the two will collide.

### Every time

```powershell
# terminal 1
cd ChainLens
.\.venv\Scripts\Activate.ps1        # prompt must show (.venv)
python scripts\serve.py
```

```powershell
# terminal 2
cd ChainLens\apps\web
npm run dev
```

`scripts/serve.py` does everything in one process: it migrates to head, indexes the
29-contract corpus if the database is empty, then serves the API. Running the database and
the web server as separate processes is how they end up unable to find each other, which
is the reason this script exists.

Expected output on a first run:

```
database ready: postgresql+psycopg://...
migrations applied
indexing the 29-contract corpus (about 30 seconds, first run only)...
corpus indexed
serving on http://127.0.0.1:8000
```

The indexing step prints nothing while it runs. That pause is normal.

### Without Docker

```powershell
$env:CHAINLENS_LOCAL_PG = "1"
python scripts\serve.py
```

This starts an embedded PostgreSQL instead. It is convenient but fragile on Windows:
antivirus real-time scanning interferes with the data directory and produces
`Timeout starting server`, a sharing violation, or `0xC000013A`. If you see any of those,
use the Docker path above.

---

## Answers

With no generation provider configured, answers are built by
`chainlens.generation.extractive`: it selects the sentences across the retrieved clauses
that bear on the question, discards redaction notices and page furniture, and suppresses
repetition. It quotes the contract and cannot invent text.

To use Gemini instead, put a key in `.env`:

```
CHAINLENS_GOOGLE_API_KEY=AIza...
```

It must be an `AIza...` key from <https://aistudio.google.com/apikey>. Other Google
credential formats are rejected at call time, and the answer then arrives as an error
rather than falling back silently. `.env` is gitignored.

---

## When it does not work

**`ModuleNotFoundError: No module named 'pgvector'`**
The virtual environment is not active. The prompt should read `(.venv)`. If
`Activate.ps1` is blocked, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.

**`connection timeout expired` on port 5433**
The database container is not running. `docker ps -a` will show it stopped; start it with
`docker start chainlens-db`.

**`password authentication failed for user chainlens`**
Something else is answering on that port, usually a native Postgres on 5432. Check the
port in `.env` matches the container's published port.

**The migration appears to hang**
A previous crashed run left a session holding a lock. `docker restart chainlens-db`
clears it.

**`Cannot find module '@rollup/rollup-...'` during `npm run build`**
`node_modules` was installed on a different platform. Delete it and run `npm install`
again on this machine.

---

## Verifying everything

```bash
make check                       # lint, types, tests, no-emoji, contrast, glossary parity
python -m eval.run --force       # re-run the ablation grid
python -m eval.gate              # the regression gate CI enforces
python -m eval.report            # regenerate every table in the repository
```

