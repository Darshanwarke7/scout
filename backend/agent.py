"""The agent loop.

This is intentionally NOT a framework (no LangChain/LlamaIndex agent
class) — it's ~120 lines of explicit control flow so it's obvious what
the model can do and when. That's the thing worth showing in a demo:

    plan -> pick a tool -> run it -> feed the result back -> repeat
    until the model chooses to answer instead of calling a tool.

Each step is yielded as a dict event so the API layer can stream it to
the frontend live instead of showing a spinner for 30 seconds.

Runs on Groq's OpenAI-compatible chat completions API instead of the
Anthropic API, so the whole thing works with a free Groq API key.
"""
import os
import json
from typing import Iterator

from groq import Groq

from backend.tools import web_search, knowledge_base, calculator

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_STEPS = int(os.environ.get("MAX_AGENT_STEPS", "8"))

# Tool schemas are kept in Anthropic-style (name/description/input_schema)
# in the tool modules themselves — we just wrap them into OpenAI/Groq's
# function-calling shape here, so nothing in backend/tools/*.py needs to
# change.
_RAW_SCHEMAS = [web_search.SCHEMA, knowledge_base.SCHEMA, calculator.SCHEMA]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": s["name"],
            "description": s["description"],
            "parameters": s["input_schema"],
        },
    }
    for s in _RAW_SCHEMAS
]

TOOL_IMPL = {
    "web_search": lambda i: web_search.run(i["query"]),
    "search_knowledge_base": lambda i: knowledge_base.run(i["query"]),
    "calculate": lambda i: calculator.run(i["expression"]),
}

SYSTEM_PROMPT = """You are Scout, a careful research agent.

Given a research question, work step by step:
1. Decide what you still need to know.
2. Use search_knowledge_base for anything that might be in the user's
   uploaded documents, and web_search for current or general facts.
3. Use calculate for any arithmetic instead of doing it in your head.
4. Once you have enough to answer well, stop calling tools and write a
   final report in markdown with a short "Sources" section listing the
   URLs and/or document names you actually used.

Be concise in intermediate reasoning. Do not call more than one tool at
a time. If a tool returns nothing useful, say so and try a different
angle rather than repeating the same call."""


def _client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key "
            "(get a free one at https://console.groq.com/keys)."
        )
    return Groq(api_key=api_key)


def run_research(query: str) -> Iterator[dict]:
    """Runs the agent loop, yielding trace events as they happen.

    Event shapes:
      {"type": "reasoning", "text": "..."}
      {"type": "tool_call", "tool": "...", "input": {...}}
      {"type": "tool_result", "tool": "...", "output": ...}
      {"type": "final", "text": "..."}
      {"type": "error", "message": "..."}
    """
    client = _client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    for step in range(MAX_STEPS):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=1500,
                tools=TOOLS,
                messages=messages,
            )
        except Exception as exc:
            # Occasionally the model emits a malformed tool call (e.g. wraps
            # JSON in <function=...> tags) and Groq rejects it with a 400
            # "tool_use_failed" error before we ever see a normal response.
            # Rather than dying, retry once with tools turned off so the
            # model just answers in plain text.
            if "tool_use_failed" in str(exc) and step == 0:
                try:
                    response = client.chat.completions.create(
                        model=MODEL,
                        max_tokens=1500,
                        tool_choice="none",
                        messages=messages,
                    )
                except Exception as exc2:
                    yield {"type": "error", "message": str(exc2)}
                    return
            else:
                yield {"type": "error", "message": str(exc)}
                return

        choice = response.choices[0]
        msg = choice.message

        if msg.content and msg.content.strip():
            yield {"type": "reasoning", "text": msg.content}

        assistant_msg = {"role": "assistant", "content": msg.content or ""}

        if not msg.tool_calls:
            # Model chose to answer instead of calling another tool.
            messages.append(assistant_msg)
            yield {"type": "final", "text": msg.content or ""}
            return

        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
        messages.append(assistant_msg)

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            try:
                tool_input = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_input = {}

            yield {"type": "tool_call", "tool": name, "input": tool_input}

            impl = TOOL_IMPL.get(name)
            if impl is None:
                output = {"error": f"Unknown tool: {name}"}
            else:
                try:
                    output = impl(tool_input)
                except Exception as exc:
                    output = {"error": str(exc)}

            yield {"type": "tool_result", "tool": name, "output": output}

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(output),
                }
            )

    yield {
        "type": "final",
        "text": "Reached the step limit before finishing — try narrowing the question.",
    }
