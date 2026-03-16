"""Single completion from Anthropic, OpenAI, or Gemini (first available key). With optional tool use."""

from agent import config


def complete(system: str, user: str) -> str:
    """Send system + user to the first available LLM; return reply text."""
    if config.ANTHROPIC_API_KEY:
        return _complete_anthropic(system, user)
    if config.OPENAI_API_KEY:
        return _complete_openai(system, user)
    if config.GEMINI_API_KEY:
        return _complete_gemini(system, user)
    raise RuntimeError(
        "No LLM API key set. Set one of ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY in .env"
    )


def complete_with_tools(
    system: str,
    user: str,
    tool_definitions: list[dict],
    run_tool: callable,
    max_rounds: int = 10,
) -> str:
    """Call LLM with tools; run tool calls and re-call until final text. Uses Anthropic or OpenAI only (Gemini falls back to no tools)."""
    if config.ANTHROPIC_API_KEY:
        return _complete_with_tools_anthropic(system, user, tool_definitions, run_tool, max_rounds)
    if config.OPENAI_API_KEY:
        return _complete_with_tools_openai(system, user, tool_definitions, run_tool, max_rounds)
    if config.GEMINI_API_KEY:
        return _complete_gemini(system, user)
    raise RuntimeError(
        "No LLM API key set. Set one of ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY in .env"
    )


def _complete_anthropic(system: str, user: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def _complete_openai(system: str, user: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return r.choices[0].message.content or ""


def _complete_gemini(system: str, user: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    # Legacy SDK: no separate system; fold into prompt
    prompt = f"{system}\n\n---\n\nUser: {user}"
    response = model.generate_content(prompt)
    return response.text or ""


def _complete_with_tools_anthropic(
    system: str, user: str, tool_definitions: list[dict], run_tool: callable, max_rounds: int
) -> str:
    from anthropic import Anthropic
    tool_names = [t.get("name", "") for t in tool_definitions]
    print(f"[alder] Tools sent to LLM ({len(tool_names)}): {tool_names}", flush=True)
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    messages: list[dict] = [{"role": "user", "content": user}]
    for _ in range(max_rounds):
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=tool_definitions,
        )
        text_parts = []
        tool_results = []
        for block in msg.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                try:
                    result = run_tool(block.name, block.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})
                except Exception as e:
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True, "content": str(e)})
        if not tool_results:
            return "\n".join(text_parts) if text_parts else ""
        messages.append({"role": "assistant", "content": msg.content})
        messages.append({"role": "user", "content": tool_results})
    return "\n".join(text_parts) if text_parts else "(max tool rounds reached)"


def _complete_with_tools_openai(
    system: str, user: str, tool_definitions: list[dict], run_tool: callable, max_rounds: int
) -> str:
    import json
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    openai_tools = [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in tool_definitions
    ]
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    for _ in range(max_rounds):
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1024,
            messages=messages,
            tools=openai_tools,
        )
        choice = r.choices[0]
        msg = choice.message
        if not getattr(msg, "tool_calls", None):
            return (msg.content or "").strip()
        assistant_msg: dict = {"role": "assistant", "content": msg.content or None, "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]}
        messages.append(assistant_msg)
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
            try:
                result = run_tool(tc.function.name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
            except Exception as e:
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": f"Error: {e}"})
    return "(max tool rounds reached)"
