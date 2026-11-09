import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from retrieval import search_stations

load_dotenv()
app = FastAPI(title="Bike Station Finder")

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bike Station Finder</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #eef5f1; color: #17352b; }
    main { max-width: 720px; margin: 8vh auto; padding: 32px; }
    .card { background: white; border-radius: 20px; padding: 28px; box-shadow: 0 8px 30px #17352b18; }
    h1 { margin-top: 0; } p { color: #587067; }
    form { display: flex; gap: 10px; margin: 24px 0; }
    input { flex: 1; border: 1px solid #c8d8d0; border-radius: 10px; padding: 13px; font-size: 16px; }
    button { border: 0; border-radius: 10px; padding: 0 20px; background: #18794e; color: white; font-weight: 700; cursor: pointer; }
    button:disabled { opacity: .6; cursor: wait; }
    .examples { display: flex; flex-wrap: wrap; gap: 8px; margin: -10px 0 24px; }
    .example { padding: 8px 12px; background: #e8f3ed; color: #17613f; font-weight: 500; }
    #result { border-top: 1px solid #e1ebe6; padding-top: 20px; white-space: pre-wrap; }
    .error { color: #b42318; } .hint { font-size: 14px; }
  </style>
</head>
<body>
  <main><section class="card">
    <h1>Bike Station Finder</h1>
    <p>Ask about bike stations, nearby landmarks, bikes, docks, or covered stations.</p>
    <form id="form">
      <input id="question" minlength="3" placeholder="Which station is near Siam and has bikes?" required>
      <button id="submit" type="submit">Ask</button>
    </form>
    <div class="examples">
      <button class="example" type="button">Which station is near Siam?</button>
      <button class="example" type="button">Find a covered station near CentralWorld</button>
      <button class="example" type="button">Where can I get a bike at Asok?</button>
      <button class="example" type="button">Are there bikes at Phrom Phong?</button>
    </div>
    <div id="result" class="hint">Your answer will appear here.</div>
  </section></main>
  <script>
    const form = document.querySelector("#form");
    const input = document.querySelector("#question");
    const button = document.querySelector("#submit");
    const result = document.querySelector("#result");
    document.querySelectorAll(".example").forEach((example) => {
      example.addEventListener("click", () => { input.value = example.textContent; input.focus(); });
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      button.disabled = true;
      result.className = "hint";
      result.textContent = "กำลังค้นหา...";
      try {
        const response = await fetch("/ask", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({question: input.value})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Request failed");
        result.className = data.supported ? "" : "error";
        result.textContent = data.answer + (data.station_ids.length
          ? "\\n\\nStations: " + data.station_ids.join(", ") : "");
      } catch (error) {
        result.className = "error";
        result.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>"""


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class Answer(BaseModel):
    answer: str
    station_ids: list[str] = Field(max_length=3)
    supported: bool


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    area: str | None = None
    covered_only: bool = False
    min_bikes: int = Field(default=0, ge=0, le=100)
    limit: int = Field(default=3, ge=1, le=5)


def parse_answer(content: str | None) -> Answer:
    if not content:
        raise RuntimeError("The model returned an empty answer")
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("The model returned invalid answer JSON")
        try:
            payload = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("The model returned invalid answer JSON") from exc
    try:
        return Answer.model_validate(payload)
    except ValueError as exc:
        raise RuntimeError("The model returned invalid answer fields") from exc


def answer_from_results(results: list[dict[str, Any]]) -> Answer:
    if not results:
        return Answer(answer="No matching bike stations were found.", station_ids=[], supported=False)
    lines = [
        f"{station['name']} ({station['area']}): {station['bikes']} bikes, "
        f"{station['docks']} open docks"
        for station in results
    ]
    return Answer(
        answer="Matching stations:\n" + "\n".join(lines),
        station_ids=[station["id"] for station in results],
        supported=True,
    )


TOOLS = [{
    "type": "function",
    "function": {
        "name": "search_stations",
        "description": "Search the local bike station dataset.",
        "parameters": SearchArgs.model_json_schema(),
    },
}]


def ask_agent(question: str) -> Answer:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"),
                    base_url=os.environ.get("OPENAI_BASE_URL") or None)
    messages: list[dict[str, Any]] = [{
        "role": "system",
        "content": "Answer only from tool results. If no result supports the question, set supported false. "
                   "Return JSON with answer, station_ids, and supported.",
    }, {"role": "user", "content": question}]
    fallback_results = search_stations(question)
    last_results: list[dict[str, Any]] = []
    for _ in range(3):
        response = client.chat.completions.create(
            model="gemma-4-E4B-it", messages=messages, tools=TOOLS, temperature=0
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            if not (message.content or "").strip():
                return answer_from_results(last_results or fallback_results)
            return parse_answer(message.content)
        for call in message.tool_calls:
            if call.function.name != "search_stations":
                raise RuntimeError("The model requested an unsupported tool")
            try:
                args = SearchArgs.model_validate_json(call.function.arguments)
            except ValueError as exc:
                raise RuntimeError("The model supplied invalid tool arguments") from exc
            result = search_stations(**args.model_dump())
            last_results = result
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    raise RuntimeError("The agent exceeded its tool-call limit")


@app.post("/ask", response_model=Answer)
def ask(question: Question) -> Answer:
    try:
        return ask_agent(question.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return PAGE
