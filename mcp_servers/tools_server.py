import ast
import operator
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("basic-tools")

# Единственная папка, к которой у агента есть доступ
WORKSPACE = (Path(__file__).parent.parent / "workspace").resolve()
MAX_READ_CHARS = 10_000


def _safe_path(relative_path: str) -> Path:
    """Защита от выхода за пределы workspace (атака path traversal)."""
    path = (WORKSPACE / relative_path).resolve()
    if not path.is_relative_to(WORKSPACE):
        raise ValueError("Доступ за пределы workspace запрещён")
    return path


@mcp.tool()
def get_current_time() -> str:
    """Возвращает текущую дату и время."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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


@mcp.tool()
def calculate(expression: str) -> str:
    """Считает арифметическое выражение, например '15 * 7 + 3'."""
    tree = ast.parse(expression, mode="eval")
    return str(_evaluate(tree.body))


@mcp.tool()
def list_files() -> str:
    """Возвращает список файлов в папке workspace."""
    files = sorted(
        str(p.relative_to(WORKSPACE)) for p in WORKSPACE.rglob("*") if p.is_file()
    )
    return "\n".join(files) if files else "Папка пуста"


@mcp.tool()
def read_file(path: str) -> str:
    """Читает текстовый файл из workspace. Путь указывается относительно workspace."""
    file_path = _safe_path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Файл не найден: {path}")
    return file_path.read_text(encoding="utf-8")[:MAX_READ_CHARS]


if __name__ == "__main__":
    mcp.run()  # общается с клиентом через stdin/stdout