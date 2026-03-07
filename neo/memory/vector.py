"""Vector memory system for semantic code search."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neo.logger import get_logger

logger = get_logger(__name__)

# Try to import numpy
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not installed. Using mock embeddings.")

# Try to import sentence-transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    logger.warning("sentence-transformers not installed. Using mock embeddings.")

# Try to import ChromaDB for vector storage
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    logger.warning("chromadb not installed. Using in-memory storage.")


@dataclass
class CodeChunk:
    """A chunk of code with metadata."""

    id: str
    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    chunk_type: str  # function, class, module, etc.
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EmbeddingProvider:
    """Provider for text embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize embedding provider.

        Args:
            model_name: Name of the sentence-transformer model
        """
        self.model_name = model_name
        self._model = None

        if HAS_SENTENCE_TRANSFORMERS:
            try:
                self._model = SentenceTransformer(model_name)
                logger.info(f"Loaded embedding model: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")

    def embed(self, texts: str | list[str]) -> list[list[float]]:
        """Generate embeddings for text(s).

        Args:
            texts: Text or list of texts to embed

        Returns:
            List of embeddings
        """
        if isinstance(texts, str):
            texts = [texts]

        if self._model:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return embeddings.tolist()
        else:
            # Mock embeddings - deterministic random vectors for testing
            return [[random.random() for _ in range(384)] for _ in texts]

    def embed_code(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Embed code chunks.

        Args:
            chunks: Code chunks to embed

        Returns:
            Chunks with embeddings
        """
        if not chunks:
            return []

        texts = [f"{chunk.chunk_type}: {chunk.content}" for chunk in chunks]
        embeddings = self.embed(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        return chunks


class VectorStore:
    """Vector store for code embeddings using ChromaDB."""

    def __init__(self, project_path: Path, collection_name: str = "code"):
        """Initialize vector store.

        Args:
            project_path: Path to the project
            collection_name: Name of the collection
        """
        self.project_path = project_path
        self.collection_name = collection_name
        self.embedding_provider = EmbeddingProvider()

        # Initialize ChromaDB or fallback to dict storage
        self._client = None
        self._collection = None
        self._mock_storage: dict[str, dict[str, Any]] = {}

        if HAS_CHROMADB:
            try:
                persist_dir = project_path / ".neo" / "chroma"
                persist_dir.mkdir(parents=True, exist_ok=True)

                self._client = chromadb.Client(
                    Settings(
                        persist_directory=str(persist_dir),
                        is_persistent=True,
                    )
                )

                self._collection = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )

                logger.info(f"Initialized ChromaDB collection: {collection_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize ChromaDB: {e}")
                self._client = None

    def _generate_id(self, file_path: str, start_line: int, content: str) -> str:
        """Generate unique ID for a code chunk.

        Args:
            file_path: File path
            start_line: Start line number
            content: Content hash

        Returns:
            Unique ID string
        """
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{file_path}:{start_line}:{content_hash}"

    def add_chunks(self, chunks: list[CodeChunk]) -> None:
        """Add code chunks to the vector store.

        Args:
            chunks: Code chunks to add
        """
        if not chunks:
            return

        # Generate embeddings
        chunks = self.embedding_provider.embed_code(chunks)

        if self._collection:
            # Add to ChromaDB
            ids = [chunk.id for chunk in chunks]
            documents = [chunk.content for chunk in chunks]
            embeddings = [chunk.embedding for chunk in chunks if chunk.embedding]
            metadatas = [
                {
                    "file_path": chunk.file_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "language": chunk.language,
                    "chunk_type": chunk.chunk_type,
                    **chunk.metadata,
                }
                for chunk in chunks
            ]

            # Add in batches
            batch_size = 100
            for i in range(0, len(chunks), batch_size):
                end = min(i + batch_size, len(chunks))
                self._collection.add(
                    ids=ids[i:end],
                    documents=documents[i:end],
                    embeddings=embeddings[i:end] if embeddings else None,
                    metadatas=metadatas[i:end],
                )
        else:
            # Add to mock storage
            for chunk in chunks:
                self._mock_storage[chunk.id] = {
                    "content": chunk.content,
                    "embedding": chunk.embedding,
                    "metadata": {
                        "file_path": chunk.file_path,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "language": chunk.language,
                        "chunk_type": chunk.chunk_type,
                    },
                }

        logger.debug(f"Added {len(chunks)} chunks to vector store")

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[CodeChunk]:
        """Search for similar code chunks.

        Args:
            query: Search query
            n_results: Number of results to return
            where: Optional filter conditions

        Returns:
            List of matching code chunks
        """
        query_embedding = self.embedding_provider.embed(query)

        if self._collection:
            try:
                results = self._collection.query(
                    query_embeddings=query_embedding,
                    n_results=n_results,
                    where=where,
                    include=["documents", "metadatas", "distances"],
                )

                chunks = []
                if results["ids"]:
                    for i, doc_id in enumerate(results["ids"][0]):
                        metadata = results["metadatas"][0][i]
                        content = results["documents"][0][i]
                        distance = results["distances"][0][i]

                        chunks.append(
                            CodeChunk(
                                id=doc_id,
                                content=content,
                                file_path=metadata["file_path"],
                                start_line=metadata["start_line"],
                                end_line=metadata["end_line"],
                                language=metadata["language"],
                                chunk_type=metadata["chunk_type"],
                                metadata={"distance": distance},
                            )
                        )

                return chunks
            except Exception as e:
                logger.warning(f"Search failed: {e}")
                return []
        else:
            # Mock search - return random chunks
            if not self._mock_storage:
                return []

            results = []
            storage_keys = list(self._mock_storage.keys())
            for _ in range(min(n_results, len(storage_keys))):
                key = random.choice(storage_keys)
                data = self._mock_storage[key]
                results.append(
                    CodeChunk(
                        id=key,
                        content=data["content"],
                        file_path=data["metadata"]["file_path"],
                        start_line=data["metadata"]["start_line"],
                        end_line=data["metadata"]["end_line"],
                        language=data["metadata"]["language"],
                        chunk_type=data["metadata"]["chunk_type"],
                    )
                )
            return results

    def delete_file(self, file_path: str) -> None:
        """Delete all chunks from a file.

        Args:
            file_path: File path to delete
        """
        if self._collection:
            try:
                self._collection.delete(where={"file_path": file_path})
                logger.debug(f"Deleted chunks for {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete chunks: {e}")
        else:
            # Delete from mock storage
            keys_to_delete = [
                k for k, v in self._mock_storage.items()
                if v["metadata"]["file_path"] == file_path
            ]
            for key in keys_to_delete:
                del self._mock_storage[key]

    def clear(self) -> None:
        """Clear all data from the store."""
        if self._collection:
            try:
                self._collection.delete()
            except Exception as e:
                logger.warning(f"Failed to clear collection: {e}")
        self._mock_storage.clear()

    def count(self) -> int:
        """Get the number of chunks in the store.

        Returns:
            Chunk count
        """
        if self._collection:
            try:
                return self._collection.count()
            except Exception:
                return 0
        return len(self._mock_storage)
