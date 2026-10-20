import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import AsyncClient

MODEL = "llama3.1:8b"
MAX_STEPS = 5

SERVER = StdioServerParameters(
    command=sys.executable,  # тот же Python, что запускает агента (из .venv)
    args=[str(Path(__file__).parent / "mcp_servers" / "tools_server.py")],
)


def to_ollama_tool(tool) -> dict:
    """Переводит описание MCP-инструмента в формат, понятный Ollama."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


async def run_agent(user_message, messages, session, tools, client) -> str:
    messages.append({"role": "user", "content": user_message})

    for _ in range(MAX_STEPS):
        response = await client.chat(model=MODEL, messages=messages, tools=tools)
        message = response.message
        messages.append(message)

        if not message.tool_calls:
            return message.content

        for call in message.tool_calls:
            name = call.function.name
            args = dict(call.function.arguments)
            print(f"  [инструмент] {name}({args})")

            result = await session.call_tool(name, args)
            text = "\n".join(c.text for c in result.content if c.type == "text")
            if result.isError:
                text = f"Ошибка: {text}"

            messages.append({"role": "tool", "tool_name": name, "content": text})

    return f"Агент не смог завершить задачу за {MAX_STEPS} шагов."


async def main():
    client = AsyncClient()

    # Запускаем MCP-сервер как отдельный процесс и подключаемся к нему
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed = await session.list_tools()
            tools = [to_ollama_tool(t) for t in listed.tools]
            print("Инструменты с MCP-сервера:", [t.name for t in listed.tools])

            history = [
                {
                    "role": "system",
                    "content": "Ты полезный ассистент. Используй инструменты, когда нужно. "
                    "Отвечай по-русски.",
                }
            ]
            print("Агент запущен. Для выхода напишите 'выход'.")
            while True:
                question = await asyncio.to_thread(input, "\nВы: ")
                if question.strip().lower() in ("выход", "exit"):
                    break
                answer = await run_agent(question, history, session, tools, client)
                print("Агент:", answer)


if __name__ == "__main__":
    asyncio.run(main())