# Bike Station Finder

An LLM-powered assistant that answers questions about a small, committed dataset
of Bangkok bike-share stations. It demonstrates:

- validated structured output with Pydantic;
- an agent loop that calls an allow-listed SQLite search tool;
- a served FastAPI interface;
- a reproducible retrieval evaluation against a lexical baseline.

The dataset is intentionally local and domain-specific; it is not the course
reference app's lecture corpus.

## Setup

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and add a newly generated key. Never commit .env.
```

## Run

```powershell
python -m uvicorn app:app --reload
```

Then send:

```powershell
curl -X POST http://127.0.0.1:8000/ask `
  -H "Content-Type: application/json" `
  -d '{"question":"Which station is near Siam and has bikes?"}'
```

The model is called through `from openai import OpenAI` with
`model="gemma-4-E4B-it"` and the class proxy URL from `OPENAI_BASE_URL`.
Tool arguments are validated before the SQL tool runs,
and the final answer is validated before it is returned.

## Evaluation

The 30 labelled questions live in `data/eval.json`. Run the offline evaluation:

```powershell
python evaluate.py
```

It reports Recall@1 for the lexical baseline and the retrieval configuration
used by the app. The second configuration uses a synonym expansion and a
minimum lexical score; both numbers are computed from the same labelled set.
The evaluation does not need an API key, so results are reproducible.

## Limitations

The station data is a static snapshot rather than a live availability feed.
The agent can only answer questions supported by the committed fields, and
questions outside that scope should be reported as unsupported rather than
invented.
