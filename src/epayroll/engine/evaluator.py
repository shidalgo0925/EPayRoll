from __future__ import annotations

import ast
import operator
from decimal import Decimal
from typing import Any, Callable


class FormulaError(Exception):
    pass


_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Gt: operator.gt,
    ast.Lt: operator.lt,
    ast.GtE: operator.ge,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    raise FormulaError(f"Tipo no soportado: {type(value)}")


def _num(value: Any) -> Decimal | bool | int | float:
    if isinstance(value, bool):
        return value
    if isinstance(value, (Decimal, int, float)):
        return _to_decimal(value)
    return value


class SafeEvaluator:
    """Evalúa expresiones configurables sin eval() directo."""

    def __init__(
        self,
        variables: dict[str, Any],
        functions: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        self.variables = variables
        self.functions = functions or {}

    def eval_condition(self, expression: str) -> bool:
        return bool(self._eval(expression))

    def eval_amount(self, expression: str) -> Decimal:
        result = self._eval(expression)
        if isinstance(result, bool):
            return Decimal("0")
        return _to_decimal(result)

    def _eval(self, expression: str) -> Any:
        try:
            tree = ast.parse(expression.strip(), mode="eval")
        except SyntaxError as e:
            raise FormulaError(f"Sintaxis inválida: {expression}") from e
        return self._visit(tree.body)

    def _visit(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in self.variables:
                raise FormulaError(f"Variable desconocida: {node.id}")
            return self.variables[node.id]
        if isinstance(node, ast.UnaryOp):
            op = _OPERATORS.get(type(node.op))
            if not op:
                raise FormulaError(f"Operador unario no permitido")
            val = self._visit(node.operand)
            if isinstance(val, Decimal):
                return _to_decimal(op(val))
            return op(val)
        if isinstance(node, ast.BinOp):
            op = _OPERATORS.get(type(node.op))
            if not op:
                raise FormulaError(f"Operador no permitido")
            left, right = self._visit(node.left), self._visit(node.right)
            if isinstance(left, bool) or isinstance(right, bool):
                raise FormulaError("Operación aritmética con booleano")
            return op(_to_decimal(left), _to_decimal(right))
        if isinstance(node, ast.Compare):
            left = self._visit(node.left)
            for op_node, comparator in zip(node.ops, node.comparators):
                right = self._visit(comparator)
                cmp_op = _OPERATORS.get(type(op_node))
                if not cmp_op:
                    raise FormulaError("Comparación no permitida")
                if not cmp_op(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            values = [self._visit(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            return any(values)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise FormulaError("Solo funciones registradas")
            fn = self.functions.get(node.func.id)
            if not fn:
                raise FormulaError(f"Función no permitida: {node.func.id}")
            args = [self._visit(a) for a in node.args]
            return fn(*args)
        raise FormulaError(f"Expresión no permitida: {type(node).__name__}")
