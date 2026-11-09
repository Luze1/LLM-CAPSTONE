# Thai Table Menu Assistant

Thai Table is an LLM-powered restaurant menu assistant. It answers questions
about a committed Thai menu and cites matching menu IDs.

It demonstrates validated structured output (Pydantic), retrieval with a
lexical baseline and synonym expansion, a bounded agent loop with an
allow-listed and validated `search_menu` tool, and a FastAPI web interface.
The evaluation is offline and does not require an API key.

## Setup

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
# Add a newly generated class-proxy key to .env. Never commit .env.
```

## Run

```powershell
python -m uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`, or call:

```powershell
curl -X POST http://127.0.0.1:8000/ask `
  -H "Content-Type: application/json" `
  -d '{"question":"Find a vegan curry under 200 baht"}'
```

The app calls `from openai import OpenAI` with model `gemma-4-E4B-it`.
`OPENAI_API_KEY` and `OPENAI_BASE_URL` are read from the environment.

## Evaluation

The 30 labelled questions in `data/eval.json` compare Recall@1 for a
name/category-only lexical baseline against the app's expanded retrieval:

```powershell
python evaluate.py
pytest
```

The committed menu data is the corpus; it is not the reference app's lecture
corpus. The menu is a static sample, so availability and dietary advice should
be confirmed with restaurant staff.
