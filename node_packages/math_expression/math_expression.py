from __future__ import annotations

import ast
import math
from typing import Any, Callable


def _clamp(value: float, minimum: float, maximum: float) -> float:
    low = min(minimum, maximum)
    high = max(minimum, maximum)
    return max(low, min(high, value))


ALLOWED_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

ALLOWED_FUNCTIONS: dict[str, Callable[..., float]] = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "clamp": _clamp,
    "floor": math.floor,
    "ceil": math.ceil,
    "trunc": math.trunc,
    "sqrt": math.sqrt,
    "pow": pow,
    "exp": math.exp,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "degrees": math.degrees,
    "radians": math.radians,
    "hypot": math.hypot,
    "fmod": math.fmod,
}

ALLOWED_BINARY_OPERATORS: dict[type[ast.AST], Callable[[float, float], float]] = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.FloorDiv: lambda left, right: left // right,
    ast.Mod: lambda left, right: left % right,
    ast.Pow: lambda left, right: left**right,
}

ALLOWED_UNARY_OPERATORS: dict[type[ast.AST], Callable[[float], float]] = {
    ast.UAdd: lambda value: value,
    ast.USub: lambda value: -value,
}


class _MathExpressionEvaluator(ast.NodeVisitor):
    def __init__(self, variables: dict[str, float]):
        self.variables = variables

    def visit_Expression(self, node: ast.Expression) -> float:
        return self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp) -> float:
        operator = ALLOWED_BINARY_OPERATORS.get(type(node.op))
        if operator is None:
            raise RuntimeError(f"Unsupported operator: {type(node.op).__name__}")
        return operator(self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        operator = ALLOWED_UNARY_OPERATORS.get(type(node.op))
        if operator is None:
            raise RuntimeError(f"Unsupported unary operator: {type(node.op).__name__}")
        return operator(self.visit(node.operand))

    def visit_Call(self, node: ast.Call) -> float:
        if not isinstance(node.func, ast.Name):
            raise RuntimeError("Only direct function calls are supported.")
        if node.keywords:
            raise RuntimeError("Keyword arguments are not supported in expressions.")

        function = ALLOWED_FUNCTIONS.get(node.func.id)
        if function is None:
            raise RuntimeError(f"Unsupported function: {node.func.id}")

        arguments = [self.visit(argument) for argument in node.args]
        return function(*arguments)

    def visit_Name(self, node: ast.Name) -> float:
        if node.id in self.variables:
            return self.variables[node.id]
        if node.id in ALLOWED_CONSTANTS:
            return ALLOWED_CONSTANTS[node.id]
        raise RuntimeError(f"Unknown name: {node.id}")

    def visit_Constant(self, node: ast.Constant) -> float:
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise RuntimeError("Only numeric constants are supported.")
        return float(node.value)

    def generic_visit(self, node: ast.AST) -> float:
        raise RuntimeError(f"Unsupported syntax: {type(node).__name__}")


class MathExpression:
    CATEGORY = "Veilance/Utils/Math"
    FUNCTION = "evaluate"
    RETURN_TYPES = ("FLOAT", "INT")
    RETURN_NAMES = ("value", "value_int")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "expression": ("STRING", {"default": "x + y"}),
                "x": ("FLOAT", {"default": 0.0, "step": 0.01}),
                "y": ("FLOAT", {"default": 0.0, "step": 0.01}),
                "z": ("FLOAT", {"default": 0.0, "step": 0.01}),
                "w": ("FLOAT", {"default": 0.0, "step": 0.01}),
                "int_mode": (
                    ["round", "truncate", "floor", "ceil"],
                    {"default": "round"},
                ),
            },
            "optional": {
                "x_in": ("*",),
                "y_in": ("*",),
                "z_in": ("*",),
                "w_in": ("*",),
            },
        }

    @staticmethod
    def _coerce_number(name: str, value: Any) -> float:
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise RuntimeError(f"Input '{name}' is empty.")
            try:
                return float(stripped)
            except ValueError as exc:
                raise RuntimeError(f"Input '{name}' must be numeric, got '{value}'.") from exc
        raise RuntimeError(f"Input '{name}' must be numeric, got {type(value).__name__}.")

    @classmethod
    def _build_variables(cls, x: Any, y: Any, z: Any, w: Any, **kwargs: Any) -> dict[str, float]:
        resolved = {
            "x": kwargs.get("x_in", x),
            "y": kwargs.get("y_in", y),
            "z": kwargs.get("z_in", z),
            "w": kwargs.get("w_in", w),
        }
        values = {name: cls._coerce_number(name, value) for name, value in resolved.items()}
        values.update(
            {
                "a": values["x"],
                "b": values["y"],
                "c": values["z"],
                "d": values["w"],
            }
        )
        return values

    @staticmethod
    def _to_int(value: float, int_mode: str) -> int:
        if int_mode == "truncate":
            return int(value)
        if int_mode == "floor":
            return math.floor(value)
        if int_mode == "ceil":
            return math.ceil(value)
        return int(round(value))

    def evaluate(
        self,
        expression: str,
        x: float,
        y: float,
        z: float,
        w: float,
        int_mode: str,
        **kwargs: Any,
    ):
        expression_text = str(expression or "").strip()
        if not expression_text:
            raise RuntimeError("Expression cannot be empty.")

        try:
            parsed = ast.parse(expression_text, mode="eval")
        except SyntaxError as exc:
            raise RuntimeError(f"Invalid expression syntax: {exc.msg}.") from exc

        variables = self._build_variables(x, y, z, w, **kwargs)
        evaluator = _MathExpressionEvaluator(variables)

        try:
            result = float(evaluator.visit(parsed))
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(f"Failed to evaluate expression: {exc}") from exc

        if not math.isfinite(result):
            raise RuntimeError("Expression result must be finite.")

        return (result, self._to_int(result, str(int_mode)))


NODE_CLASS_MAPPINGS = {
    "VeilanceMathExpression": MathExpression,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeilanceMathExpression": "Math Expression",
}
