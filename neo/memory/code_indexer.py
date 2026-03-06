"""Code indexer for parsing files and creating vector embeddings."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from neo.memory.project import ProjectMemory
from neo.memory.vector import CodeChunk, VectorStore

logger = logging.getLogger(__name__)


class CodeIndexer:
    """Indexes code files for semantic search."""

    # Language detection
    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
    }

    # Maximum chunk size in characters
    MAX_CHUNK_SIZE = 2000
    OVERLAP_SIZE = 200

    def __init__(self, project_path: Path):
        """Initialize code indexer.

        Args:
            project_path: Path to the project
        """
        self.project_path = Path(project_path).resolve()
        self.vector_store = VectorStore(self.project_path)
        self.project_memory = ProjectMemory(self.project_path)

    def detect_language(self, file_path: Path) -> str:
        """Detect language from file extension.

        Args:
            file_path: Path to file

        Returns:
            Language identifier
        """
        ext = file_path.suffix.lower()
        return self.LANGUAGE_MAP.get(ext, "text")

    def index_file(self, file_path: Path) -> list[CodeChunk]:
        """Index a single file.

        Args:
            file_path: Path to file

        Returns:
            List of code chunks
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return []

        language = self.detect_language(file_path)
        relative_path = str(file_path.relative_to(self.project_path))

        # Parse based on language
        if language == "python":
            chunks = self._parse_python(content, relative_path)
        elif language in ("javascript", "typescript"):
            chunks = self._parse_javascript(content, relative_path, language)
        else:
            # Generic chunking for other languages
            chunks = self._chunk_generic(content, relative_path, language)

        # Add to vector store
        if chunks:
            self.vector_store.add_chunks(chunks)
            logger.debug(f"Indexed {len(chunks)} chunks from {file_path}")

        return chunks

    def _parse_python(self, content: str, file_path: str) -> list[CodeChunk]:
        """Parse Python code into chunks.

        Args:
            content: File content
            file_path: Relative file path

        Returns:
            List of code chunks
        """
        chunks = []
        lines = content.split("\n")

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return self._chunk_generic(content, file_path, "python")

        # Get module-level docstring
        module_docstring = ast.get_docstring(tree)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Function chunk
                start_line = node.lineno
                end_line = node.end_lineno or start_line
                func_lines = lines[start_line - 1:end_line]
                func_content = "\n".join(func_lines)

                docstring = ast.get_docstring(node)

                chunk = CodeChunk(
                    id=f"{file_path}:{node.name}",
                    content=func_content,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    language="python",
                    chunk_type="function",
                    metadata={
                        "name": node.name,
                        "docstring": docstring or "",
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                    },
                )
                chunks.append(chunk)

            elif isinstance(node, ast.ClassDef):
                # Class chunk
                start_line = node.lineno
                end_line = node.end_lineno or start_line
                class_lines = lines[start_line - 1:end_line]
                class_content = "\n".join(class_lines)

                docstring = ast.get_docstring(node)
                method_names = [
                    n.name for n in node.body
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                ]

                chunk = CodeChunk(
                    id=f"{file_path}:{node.name}",
                    content=class_content,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    language="python",
                    chunk_type="class",
                    metadata={
                        "name": node.name,
                        "docstring": docstring or "",
                        "methods": method_names,
                    },
                )
                chunks.append(chunk)

        # If no structured chunks, fall back to generic
        if not chunks:
            return self._chunk_generic(content, file_path, "python")

        return chunks

    def _parse_javascript(
        self, content: str, file_path: str, language: str
    ) -> list[CodeChunk]:
        """Parse JavaScript/TypeScript code into chunks.

        Args:
            content: File content
            file_path: Relative file path
            language: Language identifier

        Returns:
            List of code chunks
        """
        chunks = []
        lines = content.split("\n")

        # Pattern matching for JS/TS functions and classes
        patterns = [
            # Function declarations
            (r"^(async\s+)?function\s+(\w+)", "function"),
            # Arrow functions with const/let
            (r"^(export\s+)?(const|let)\s+(\w+)\s*=\s*(async\s*)?\(", "function"),
            # Class declarations
            (r"^(export\s+)?class\s+(\w+)", "class"),
            # Method definitions
            (r"^(async\s+)?(\w+)\s*\([^)]*\)\s*{", "method"),
        ]

        for i, line in enumerate(lines):
            for pattern, chunk_type in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    # Find end of definition (naive approach)
                    start_line = i + 1
                    brace_count = 1
                    end_line = start_line

                    for j in range(i + 1, len(lines)):
                        brace_count += lines[j].count("{")
                        brace_count -= lines[j].count("}")
                        if brace_count == 0:
                            end_line = j + 1
                            break

                    chunk_lines = lines[start_line - 1:end_line]
                    chunk_content = "\n".join(chunk_lines)

                    # Extract name from match
                    name_groups = [g for g in match.groups() if g and not g.startswith("async")]
                    name = name_groups[-1] if name_groups else "unknown"

                    chunk = CodeChunk(
                        id=f"{file_path}:{name}:{start_line}",
                        content=chunk_content,
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        language=language,
                        chunk_type=chunk_type,
                        metadata={"name": name},
                    )
                    chunks.append(chunk)

        # If no structured chunks, fall back to generic
        if not chunks:
            return self._chunk_generic(content, file_path, language)

        return chunks

    def _chunk_generic(
        self, content: str, file_path: str, language: str
    ) -> list[CodeChunk]:
        """Generic chunking by size for unsupported languages.

        Args:
            content: File content
            file_path: Relative file path
            language: Language identifier

        Returns:
            List of code chunks
        """
        chunks = []
        lines = content.split("\n")

        # Simple chunking by lines
        chunk_size = 50  # lines per chunk
        overlap = 5

        start = 0
        while start < len(lines):
            end = min(start + chunk_size, len(lines))
            chunk_lines = lines[start:end]
            chunk_content = "\n".join(chunk_lines)

            chunk = CodeChunk(
                id=f"{file_path}:{start + 1}",
                content=chunk_content,
                file_path=file_path,
                start_line=start + 1,
                end_line=end,
                language=language,
                chunk_type="module",
                metadata={},
            )
            chunks.append(chunk)

            start += chunk_size - overlap

        return chunks

    def index_project(self, force: bool = False) -> dict[str, Any]:
        """Index the entire project.

        Args:
            force: Force re-index even if already indexed

        Returns:
            Indexing statistics
        """
        logger.info(f"Indexing project: {self.project_path}")

        if force:
            self.vector_store.clear()

        # Get supported extensions
        extensions = self.project_memory.get_language_extensions()
        if not extensions:
            # Default to common extensions
            extensions = [".py", ".js", ".ts", ".go", ".rs", ".java"]

        # Find all files to index
        files_to_index = []
        for ext in extensions:
            files_to_index.extend(self.project_path.rglob(f"*{ext}"))

        # Filter out excluded directories
        excluded = {
            "node_modules", "__pycache__", "venv", ".git",
            "dist", "build", ".pytest_cache", ".mypy_cache",
        }

        files_to_index = [
            f for f in files_to_index
            if not any(part in excluded for part in f.parts)
        ]

        # Index files
        total_chunks = 0
        indexed_files = 0

        for file_path in files_to_index:
            chunks = self.index_file(file_path)
            if chunks:
                total_chunks += len(chunks)
                indexed_files += 1

        stats = {
            "files_indexed": indexed_files,
            "chunks_created": total_chunks,
            "vector_count": self.vector_store.count(),
        }

        logger.info(f"Indexed {indexed_files} files with {total_chunks} chunks")
        return stats

    def search(
        self, query: str, n_results: int = 10, file_filter: str | None = None
    ) -> list[CodeChunk]:
        """Search for code chunks.

        Args:
            query: Search query
            n_results: Number of results
            file_filter: Optional file path filter

        Returns:
            List of matching chunks
        """
        where = None
        if file_filter:
            where = {"file_path": {"$contains": file_filter}}

        return self.vector_store.search(query, n_results, where)

    def get_related_code(self, file_path: str, n_results: int = 5) -> list[CodeChunk]:
        """Get code related to a file.

        Args:
            file_path: File to find related code for
            n_results: Number of results

        Returns:
            List of related code chunks
        """
        # Read the file
        full_path = self.project_path / file_path
        if not full_path.exists():
            return []

        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception:
            return []

        # Use file content as query
        # Truncate to reasonable size
        query = content[:1000]
        return self.search(query, n_results, file_filter=file_path)

    def refresh_file(self, file_path: Path) -> None:
        """Refresh index for a file.

        Args:
            file_path: Path to file
        """
        relative_path = str(file_path.relative_to(self.project_path))
        self.vector_store.delete_file(relative_path)
        self.index_file(file_path)
