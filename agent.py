import ast
import operator
from datetime import datetime

import ollama

MODEL = "llama3.1:8b"


# ---------- Инструменты: обычные функции Python ----------

def get_current_time() -> str:
    """Возвращает текущую дату и время."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Разрешаем только арифметику. Использовать eval() напрямую нельзя:
# через него можно выполнить любой вредоносный код.
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _evaluate(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](_evaluate(node.operand))
    raise ValueError("Недопустимое выражение")


def calculate(expression: str) -> str:
    """Считает арифметическое выражение, например '2 + 2 * 10'."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_evaluate(tree.body))
    except Exception as error:
        return f"Ошибка: {error}"


# ---------- Описание инструментов для модели ----------
# Модель не видит наш код. Она видит только это описание
# и по нему решает, какой инструмент вызвать.

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Возвращает текущую дату и время",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Считает арифметическое выражение",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Выражение, например '15 * 7 + 3'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
    "calculate": calculate,
}


# ---------- Агентный цикл ----------

def run_agent(user_message: str, messages: list) -> str:
    messages.append({"role": "user", "content": user_message})

    for _ in range(5):  # защита от бесконечного цикла
        response = ollama.chat(model=MODEL, messages=messages, tools=TOOLS)
        message = response.message
        messages.append(message)

        # Если модель не просит инструмент, значит, ответ готов
        if not message.tool_calls:
            return message.content

        # Иначе выполняем каждый запрошенный инструмент
        for call in message.tool_calls:
            name = call.function.name
            args = call.function.arguments
            print(f"  [инструмент] {name}({args})")

            result = TOOL_FUNCTIONS[name](**args)
            messages.append({"role": "tool", "tool_name": name, "content": result})

    return "Агент не смог завершить задачу за 5 шагов."


if __name__ == "__main__":
    history = [
        {
            "role": "system",
            "content": "Ты полезный ассистент. Используй инструменты, когда нужно.",
        }
    ]
    print("Агент запущен. Для выхода напишите 'выход'.")
    while True:
        question = input("\nВы: ")
        if question.strip().lower() in ("выход", "exit"):
            break
        print("Агент:", run_agent(question, history))