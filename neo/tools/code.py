"""Code analysis tools for Neo."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from neo.tools.base import BaseTool, ToolResult


class AnalyzeFileTool(BaseTool):
    """Analyze Python file structure."""

    name = "analyze_file"
    description = "Analyze a Python file structure."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to Python file"},
        },
        "required": ["file_path"],
    }

    async def execute(self, file_path: str) -> ToolResult:
        """Analyze Python file structure."""
        try:
            path = Path(file_path).expanduser().resolve()

            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {file_path}",
                )

            if not path.is_file():
                return ToolResult(
                    success=False,
                    error=f"Path is not a file: {file_path}",
                )

            # Read and parse file
            content = path.read_text(encoding="utf-8", errors="replace")

            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                return ToolResult(
                    success=False,
                    error=f"Syntax error in file: {e}",
                )

            # Extract structure
            imports = []
            classes = []
            functions = []

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = [alias.name for alias in node.names]
                    imports.append(f"from {module} import {', '.join(names)}")
                elif isinstance(node, ast.ClassDef):
                    classes.append(self._analyze_class(node))
                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    functions.append(self._analyze_function(node))

            # Build output
            output_lines = [f"File: {path.name}\n"]

            if imports:
                output_lines.append("Imports:")
                for imp in imports:
                    output_lines.append(f"  - {imp}")
                output_lines.append("")

            if classes:
                output_lines.append(f"Classes ({len(classes)}):")
                for cls in classes:
                    output_lines.append(f"  class {cls['name']}")
                    if cls['docstring']:
                        output_lines.append(f"    \"{cls['docstring'][:60]}...\"")
                    for method in cls['methods']:
                        output_lines.append(f"    - {method['name']}()")
                output_lines.append("")

            if functions:
                output_lines.append(f"Functions ({len(functions)}):")
                for func in functions:
                    output_lines.append(f"  - {func['name']}()")
                    if func['docstring']:
                        output_lines.append(f"    \"{func['docstring'][:60]}...\"")

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={
                    "file_path": str(path),
                    "imports": imports,
                    "classes": classes,
                    "functions": functions,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error analyzing file: {str(e)}",
            )

    def _analyze_class(self, node: ast.ClassDef) -> dict[str, Any]:
        """Analyze a class definition."""
        docstring = ast.get_docstring(node)

        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                methods.append(self._analyze_function(item))

        return {
            "name": node.name,
            "docstring": docstring,
            "line": node.lineno,
            "methods": methods,
        }

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
        """Analyze a function definition."""
        docstring = ast.get_docstring(node)

        # Get signature
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)

        # Handle defaults
        defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + node.args.defaults

        signature_parts = []
        for arg, default in zip(node.args.args, defaults, strict=False):
            part = arg.arg
            if default:
                part += f"={ast.unparse(default)}"
            signature_parts.append(part)

        signature = f"({', '.join(signature_parts)})"

        return {
            "name": node.name,
            "docstring": docstring,
            "line": node.lineno,
            "signature": signature,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
        }


class FindSymbolTool(BaseTool):
    """Find symbol definitions in Python files."""

    name = "find_symbol"
    description = "Find class/function definitions."
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Name to find"},
            "path": {"type": "string", "description": "Directory to search", "default": "."},
        },
        "required": ["symbol"],
    }

    async def execute(self, symbol: str, path: str = ".") -> ToolResult:
        """Find symbol definitions."""
        try:
            search_path = Path(path).expanduser().resolve()

            if not search_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Path not found: {path}",
                )

            # Search Python files
            python_files = list(search_path.rglob("*.py"))
            matches = []

            for file_path in python_files:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()

                    # Look for definition patterns
                    # Class definition
                    class_pattern = re.compile(rf"^class\s+{re.escape(symbol)}\s*[\(:]")
                    # Function definition
                    func_pattern = re.compile(rf"^(async\s+)?def\s+{re.escape(symbol)}\s*\(")

                    for i, line in enumerate(lines, 1):
                        if class_pattern.search(line) or func_pattern.search(line):
                            rel_path = file_path.relative_to(search_path)
                            matches.append({
                                "file": str(rel_path),
                                "line": i,
                                "content": line.strip(),
                            })

                except Exception:
                    continue

            if not matches:
                return ToolResult(
                    success=True,
                    output=f"Symbol '{symbol}' not found in {search_path}",
                    data={"symbol": symbol, "matches": []},
                )

            # Format output
            output_lines = [f"Found '{symbol}' in {len(matches)} location(s):\n"]
            for m in matches:
                output_lines.append(f"{m['file']}:{m['line']}")
                output_lines.append(f"  {m['content']}")
                output_lines.append("")

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={
                    "symbol": symbol,
                    "matches": matches,
                    "count": len(matches),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error finding symbol: {str(e)}",
            )
