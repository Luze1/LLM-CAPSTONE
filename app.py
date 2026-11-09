import json
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from openai import OpenAI
from pydantic import BaseModel, Field

from retrieval import search_menu

load_dotenv()
app = FastAPI(title="Thai Table Menu Assistant")

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Thai Table</title>
<style>body{font-family:system-ui;background:#fff7ed;color:#422006;margin:0}main{max-width:720px;margin:8vh auto;padding:32px}.card{background:white;border-radius:20px;padding:28px;box-shadow:0 8px 30px #78350f20;display:flex;flex-direction:column;min-height:620px}h1{margin-top:0}p{color:#92400e}form{display:flex;gap:10px;margin:16px 0 0;order:4}input{flex:1;border:1px solid #fed7aa;border-radius:10px;padding:13px;font-size:16px}button{border:0;border-radius:10px;padding:0 20px;background:#c2410c;color:white;font-weight:700;cursor:pointer}button:disabled{opacity:.6;cursor:wait}.examples{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px;order:3}.example{padding:8px 12px;background:#ffedd5;color:#9a3412}.chat{border-top:1px solid #ffedd5;padding-top:16px;display:grid;gap:14px;flex:1;min-height:250px;max-height:460px;overflow:auto;order:2}.message{padding:12px 16px;border-radius:16px;white-space:pre-wrap;line-height:1.5}.user{background:#ffedd5;margin-left:15%}.assistant{background:#fff7ed;margin-right:15%}.error{color:#b42318}.chat-header{display:flex;justify-content:space-between;align-items:center;color:#92400e;font-size:14px;order:1}.clear{background:none;color:#c2410c;padding:4px 8px}</style>
</head><body><main><section class="card"><h1>Thai Table Menu Assistant</h1>
<p>Ask about dishes, ingredients, dietary choices, spice, or price.</p>
<div class="chat-header"><span>Conversation history</span><button class="clear" id="clear" type="button">Clear history</button></div>
<div id="chat" class="chat"><div id="empty">Your conversation will appear here.</div></div>
<div class="examples"><button class="example" type="button">Find a vegan curry</button><button class="example" type="button">What is spicy with chicken?</button><button class="example" type="button">Thai dessert with mango</button></div>
<form id="form"><input id="question" minlength="3" placeholder="Find a vegan curry under 200 baht" required><button id="submit">Ask</button></form></section></main>
<script>const f=document.querySelector("#form"),i=document.querySelector("#question"),b=document.querySelector("#submit"),c=document.querySelector("#chat"),empty=document.querySelector("#empty"),historyKey="thai-table-chat";let history=JSON.parse(localStorage.getItem(historyKey)||"[]");function addMessage(role,text){let m=document.createElement("div");m.className="message "+role;m.textContent=text;c.appendChild(m);empty?.remove();c.scrollTop=c.scrollHeight}history.forEach(m=>addMessage(m.role,m.text));document.querySelector("#clear").onclick=()=>{history=[];localStorage.removeItem(historyKey);c.replaceChildren(empty);};document.querySelectorAll(".example").forEach(e=>e.onclick=()=>{i.value=e.textContent;i.focus()});f.onsubmit=async e=>{e.preventDefault();let question=i.value.trim();if(!question)return;addMessage("user",question);history.push({role:"user",text:question});localStorage.setItem(historyKey,JSON.stringify(history));i.value="";b.disabled=true;addMessage("assistant","กำลังค้นหา...");let pending=c.lastElementChild;try{let x=await fetch("/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question})}),d=await x.json();if(!x.ok)throw Error(d.detail||"Request failed");let text=d.answer+(d.menu_ids.length?"\\n\\nMenu IDs: "+d.menu_ids.join(", "):"");pending.textContent=text;history.push({role:"assistant",text});localStorage.setItem(historyKey,JSON.stringify(history))}catch(e){pending.className="message assistant error";pending.textContent=e.message}finally{b.disabled=false;i.focus()}}</script>
</body></html>"""


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class Answer(BaseModel):
    answer: str
    menu_ids: list[str] = Field(max_length=3)
    supported: bool


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    category: str | None = None
    vegetarian_only: bool = False
    vegan_only: bool = False
    max_price: int | None = Field(default=None, ge=0, le=5000)
    limit: int = Field(default=3, ge=1, le=5)


def parse_answer(content: str | None) -> Answer:
    if not content:
        raise RuntimeError("The model returned an empty answer")
    text = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return Answer.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError("The model returned invalid answer JSON") from exc


def answer_from_results(results: list[dict[str, Any]]) -> Answer:
    if not results:
        return Answer(answer="No matching dishes were found.", menu_ids=[], supported=False)
    lines = [f"{item['name']} ({item['price']} baht): {item['description']}" for item in results]
    return Answer(answer="Matching dishes:\n" + "\n".join(lines), menu_ids=[item["id"] for item in results], supported=True)


TOOLS = [{"type": "function", "function": {"name": "search_menu", "description": "Search the local Thai Table menu.",
    "parameters": SearchArgs.model_json_schema()}}]


def ask_agent(question: str) -> Answer:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), base_url=os.environ.get("OPENAI_BASE_URL") or None)
    messages: list[dict[str, Any]] = [{"role": "system", "content": "Understand Thai and English questions. Answer in the same language as the user, using only tool results. If unsupported, set supported false. Return JSON with answer, menu_ids, and supported."}, {"role": "user", "content": question}]
    fallback = search_menu(question)
    last_results: list[dict[str, Any]] = []
    for _ in range(3):
        response = client.chat.completions.create(model="gemma-4-E4B-it", messages=messages, tools=TOOLS, temperature=0)
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            return parse_answer(message.content) if (message.content or "").strip() else answer_from_results(last_results or fallback)
        for call in message.tool_calls:
            if call.function.name != "search_menu":
                raise RuntimeError("The model requested an unsupported tool")
            try:
                args = SearchArgs.model_validate_json(call.function.arguments)
            except ValueError as exc:
                raise RuntimeError("The model supplied invalid tool arguments") from exc
            last_results = search_menu(**args.model_dump())
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(last_results)})
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
