"""Context retriever for gathering relevant code context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neo.memory.code_indexer import CodeIndexer
from neo.memory.vector import CodeChunk

from neo.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Context:
    """Context for a query."""

    relevant_files: list[str]
    relevant_code: list[CodeChunk]
    symbols: list[dict[str, Any]]
    project_structure: str
    summary: str


class ContextRetriever:
    """Retrieves relevant context for queries."""

    def __init__(self, project_path: Path):
        """Initialize context retriever.

        Args:
            project_path: Path to the project
        """
        self.project_path = Path(project_path).resolve()
        self.indexer = CodeIndexer(self.project_path)

    def get_context_for_query(
        self,
        query: str,
        max_chunks: int = 5,
        max_files: int = 3,
    ) -> Context:
        """Get relevant context for a query.

        Args:
            query: User query
            max_chunks: Maximum code chunks to include
            max_files: Maximum files to include

        Returns:
            Context object
        """
        logger.debug(f"Getting context for query: {query[:50]}...")

        # Search for relevant code
        relevant_chunks = self.indexer.search(query, n_results=max_chunks * 2)

        # Deduplicate by file
        seen_files = set()
        unique_chunks = []
        for chunk in relevant_chunks:
            if chunk.file_path not in seen_files:
                seen_files.add(chunk.file_path)
                unique_chunks.append(chunk)

        # Limit chunks
        relevant_chunks = unique_chunks[:max_chunks]

        # Get file list
        relevant_files = list(seen_files)[:max_files]

        # Extract symbols from chunks
        symbols = self._extract_symbols(relevant_chunks)

        # Get project structure
        project_structure = self._get_project_structure()

        # Create summary
        summary = self._create_summary(query, relevant_chunks, relevant_files)

        return Context(
            relevant_files=relevant_files,
            relevant_code=relevant_chunks,
            symbols=symbols,
            project_structure=project_structure,
            summary=summary,
        )

    def get_context_for_edit(
        self,
        file_path: str,
        edit_description: str,
        max_related: int = 3,
    ) -> Context:
        """Get context for editing a file.

        Args:
            file_path: File being edited
            edit_description: Description of the edit
            max_related: Maximum related files to include

        Returns:
            Context object
        """
        logger.debug(f"Getting context for edit: {file_path}")

        # Get related code
        related_chunks = self.indexer.get_related_code(file_path, n_results=max_related * 2)

        # Filter out the file itself
        related_chunks = [c for c in related_chunks if c.file_path != file_path]

        # Deduplicate
        seen_files = {file_path}
        unique_chunks = []
        for chunk in related_chunks:
            if chunk.file_path not in seen_files:
                seen_files.add(chunk.file_path)
                unique_chunks.append(chunk)

        related_chunks = unique_chunks[:max_related]

        # Get symbols
        symbols = self._extract_symbols(related_chunks)

        return Context(
            relevant_files=list(seen_files),
            relevant_code=related_chunks,
            symbols=symbols,
            project_structure="",
            summary=f"Related code for editing {file_path}",
        )

    def _extract_symbols(
        self, chunks: list[CodeChunk]
    ) -> list[dict[str, Any]]:
        """Extract symbols from chunks.

        Args:
            chunks: Code chunks

        Returns:
            List of symbol dictionaries
        """
        symbols = []

        for chunk in chunks:
            symbol = {
                "name": chunk.metadata.get("name", "unknown"),
                "type": chunk.chunk_type,
                "file": chunk.file_path,
                "line": chunk.start_line,
            }

            # Add additional metadata
            if "docstring" in chunk.metadata:
                symbol["docstring"] = chunk.metadata["docstring"]
            if "methods" in chunk.metadata:
                symbol["methods"] = chunk.metadata["methods"]
            if "is_async" in chunk.metadata:
                symbol["is_async"] = chunk.metadata["is_async"]

            symbols.append(symbol)

        return symbols

    def _get_project_structure(self) -> str:
        """Get project structure overview.

        Returns:
            String representation of structure
        """
        lines = ["Project Structure:"]

        # Get top-level directories
        for item in sorted(self.project_path.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                # Count files in directory
                file_count = sum(1 for _ in item.rglob("*") if _.is_file())
                lines.append(f"  📁 {item.name}/ ({file_count} files)")

            elif item.is_file():
                lines.append(f"  📄 {item.name}")

        return "\n".join(lines)

    def _create_summary(
        self,
        query: str,
        chunks: list[CodeChunk],
        files: list[str],
    ) -> str:
        """Create a summary of the context.

        Args:
            query: User query
            chunks: Relevant chunks
            files: Relevant files

        Returns:
            Summary string
        """
        parts = [f"Query: {query}"]

        if files:
            parts.append(f"Relevant files: {', '.join(files)}")

        if chunks:
            parts.append("Relevant symbols:")
            for chunk in chunks[:5]:
                name = chunk.metadata.get("name", "unknown")
                parts.append(f"  - {name} ({chunk.chunk_type}) in {chunk.file_path}:{chunk.start_line}")

        return "\n".join(parts)

    def format_context_for_prompt(self, context: Context) -> str:
        """Format context for inclusion in LLM prompt.

        Args:
            context: Context object

        Returns:
            Formatted string
        """
        lines = [
            "## Project Context",
            "",
            context.project_structure,
            "",
            "## Relevant Files",
        ]

        for file_path in context.relevant_files:
            lines.append(f"- {file_path}")

        if context.symbols:
            lines.extend(["", "## Relevant Symbols"])
            for symbol in context.symbols[:10]:
                lines.append(f"- {symbol['name']} ({symbol['type']}) in {symbol['file']}:{symbol['line']}")

        if context.relevant_code:
            lines.extend(["", "## Relevant Code Snippets"])
            for chunk in context.relevant_code[:3]:
                lines.append(f"\n### {chunk.file_path}:{chunk.start_line}")
                lines.append(f"```{chunk.language}")
                lines.append(chunk.content[:500])  # Limit snippet size
                lines.append("```")

        return "\n".join(lines)

    def index_if_needed(self) -> bool:
        """Check if indexing is needed and index if so.

        Returns:
            True if indexing was performed
        """
        # Check if vector store is empty
        if self.indexer.vector_store.count() == 0:
            logger.info("Code index is empty, indexing project...")
            stats = self.indexer.index_project()
            logger.info(f"Indexing complete: {stats}")
            return True
        return False
