#!/usr/bin/env python3
"""Remove documentation overhead while preserving the contract's executable AST."""
import ast
from pathlib import Path


def build(source: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body.pop(0)
                if not node.body:
                    node.body.append(ast.Pass())
    result = source.splitlines()[0] + "\n" + ast.unparse(tree) + "\n"
    if ast.dump(ast.parse(result)) != ast.dump(tree):
        raise ValueError("Deployment artifact changed the executable AST")
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    source = (root / "contracts/retainer.py").read_text()
    result = build(source)
    (root / "contracts/retainer.deploy.py").write_text(result)
    print("Deployment artifact: %d -> %d bytes; executable AST verified"
          % (len(source.encode()), len(result.encode())))
