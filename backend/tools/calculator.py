"""A calculator tool that never calls eval().

Walks a restricted AST so the agent can safely do arithmetic that shows
up naturally in research (unit conversions, quick stats) without opening
up arbitrary code execution.
"""
import ast
import operator

SCHEMA = {
    "name": "calculate",
    "description": (
        "Evaluate a plain arithmetic expression, e.g. '(1200 - 950) / 950 * 100'. "
        "Supports +, -, *, /, **, %, and parentheses only."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "The expression to evaluate."},
        },
        "required": ["expression"],
    },
}

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("Expression contains unsupported operations.")


def run(expression: str) -> dict:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval(tree.body)
        return {"result": result}
    except Exception as exc:
        return {"error": f"Could not evaluate '{expression}': {exc}"}
