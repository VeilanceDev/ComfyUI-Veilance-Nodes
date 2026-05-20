from __future__ import annotations

import unittest

from tests.helpers import import_repo_module


math_expression = import_repo_module("node_packages.math_expression.math_expression")


class MathExpressionTests(unittest.TestCase):
    def test_evaluates_variables_functions_and_int_output(self):
        node = math_expression.MathExpression()

        value, value_int = node.evaluate(
            "clamp(x * 2 + sqrt(y), 0, 10)",
            x=3.0,
            y=16.0,
            z=0.0,
            w=0.0,
            int_mode="round",
        )

        self.assertEqual(value, 10.0)
        self.assertEqual(value_int, 10)

    def test_rejects_unsupported_syntax(self):
        node = math_expression.MathExpression()

        with self.assertRaisesRegex(RuntimeError, "Unsupported syntax"):
            node.evaluate(
                "[x]",
                x=1.0,
                y=0.0,
                z=0.0,
                w=0.0,
                int_mode="round",
            )

    def test_linked_inputs_override_widget_values(self):
        node = math_expression.MathExpression()

        value, value_int = node.evaluate(
            "a + b",
            x=1.0,
            y=2.0,
            z=0.0,
            w=0.0,
            int_mode="truncate",
            x_in="5.5",
            y_in=2,
        )

        self.assertEqual(value, 7.5)
        self.assertEqual(value_int, 7)


if __name__ == "__main__":
    unittest.main()
