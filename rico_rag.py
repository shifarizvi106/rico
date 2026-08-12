
import os
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, Set, Union, Callable
from dataclasses import dataclass, field

# LangChain imports — wrapped for graceful degradation
try:
    from langchain_community.document_loaders import TextLoader, PyPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.schema import Document
    LANGCHAIN_AVAILABLE = True
except ImportError:
    TextLoader = None  # type: ignore
    PyPDFLoader = None  # type: ignore
    RecursiveCharacterTextSplitter = None  # type: ignore
    Document = None  # type: ignore
    LANGCHAIN_AVAILABLE = False

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    HuggingFaceEmbeddings = None  # type: ignore
    EMBEDDINGS_AVAILABLE = False

try:
    from langchain_community.vectorstores import Chroma
    CHROMA_AVAILABLE = True
except ImportError:
    Chroma = None  # type: ignore
    CHROMA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class IndexResult:
    """Result of a document indexing operation."""
    success: bool
    documents_loaded: int = 0
    chunks_created: int = 0
    errors: List[str] = field(default_factory=list)
    message: str = ""


@dataclass
class SearchResult:
    """A single semantic search result."""
    content: str
    source: str
    filename: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeStats:
    """Statistics about the knowledge base."""
    total_chunks: int = 0
    persist_directory: str = ""
    embedding_model: str = ""
    is_ready: bool = False


# ---------------------------------------------------------------------------
# RicoRAG
# ---------------------------------------------------------------------------
class RicoRAG:
    """
    Retrieval-Augmented Generation system for Rico Assistant.

    Manages document ingestion, embedding generation, and semantic search
    over a persistent ChromaDB vector store.

    Args:
        persist_dir: Directory for ChromaDB persistence. Defaults to ~/rico_knowledge.
        embedding_model_name: HuggingFace model for embeddings.
        chunk_size: Target size for each text chunk.
        chunk_overlap: Overlap between consecutive chunks.
        device: Compute device for embeddings ('cpu', 'cuda', 'mps').

    Example:
        >>> rag = RicoRAG()
        >>> result = rag.index_folder("~/Documents/Notes")
        >>> print(result.message)
        >>> answer = rag.query("What are the key points?")
    """

    # Supported file extensions and their loader mappings
    SUPPORTED_EXTENSIONS: Dict[str, str] = {
        ".txt": "text",
        ".md": "text",
        ".pdf": "pdf",
        ".py": "text",
        ".js": "text",
        ".ts": "text",
        ".html": "text",
        ".htm": "text",
        ".css": "text",
        ".json": "text",
        ".xml": "text",
        ".yaml": "text",
        ".yml": "text",
        ".rst": "text",
        ".csv": "text",
    }

    # Directories to skip during recursive indexing
    SKIP_DIRS: Set[str] = {
        ".git", ".svn", ".hg", ".venv", "venv", "env",
        "__pycache__", ".pytest_cache", ".mypy_cache",
        "node_modules", ".idea", ".vscode", "dist", "build",
        ".rico_knowledge", "chroma_db", ".chroma",
    }

    def __init__(
        self,
        persist_dir: str = "~/rico_knowledge",
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        device: str = "cpu",
    ) -> None:
        """
        Initialise the RAG system.

        The embedding model is loaded lazily on first use to keep startup fast.
        """
        self.persist_dir: Path = Path(persist_dir).expanduser().resolve()
        self.embedding_model_name: str = embedding_model_name
        self.chunk_size: int = chunk_size
        self.chunk_overlap: int = chunk_overlap
        self.device: str = device

        # Lazy-loaded components
        self._embedding_model: Optional[Any] = None
        self._vectorstore: Optional[Any] = None
        self._text_splitter: Optional[Any] = None

        # Thread safety
        self._lock: threading.RLock = threading.RLock()
        self._indexing: bool = False

        # Validate dependencies
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is required for RAG. Install: pip install langchain langchain-community"
            )
        if not EMBEDDINGS_AVAILABLE:
            raise ImportError(
                "Embeddings module not available. Install: pip install sentence-transformers"
            )
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "ChromaDB not available. Install: pip install chromadb"
            )

        # Ensure persist directory exists
        self.persist_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Lazy Initialisation
    # -----------------------------------------------------------------------
    def _get_embeddings(self) -> Any:
        """
        Lazily initialise and return the embedding model.

        This keeps Rico's startup fast — the model is only loaded when
        the first indexing or query operation occurs.
        """
        if self._embedding_model is not None:
            return self._embedding_model

        with self._lock:
            # Double-check after acquiring lock
            if self._embedding_model is not None:
                return self._embedding_model

            print(f"[RAG] Loading embedding model: {self.embedding_model_name}...")
            try:
                self._embedding_model = HuggingFaceEmbeddings(
                    model_name=self.embedding_model_name,
                    model_kwargs={"device": self.device},
                    encode_kwargs={"normalize_embeddings": True},
                )
                print("[RAG] Embedding model loaded.")
            except Exception as exc:
                raise RuntimeError(f"Failed to load embedding model: {exc}") from exc

        return self._embedding_model

    def _get_vectorstore(self) -> Any:
        """
        Lazily initialise and return the ChromaDB vector store.

        Loads existing data from disk if available, otherwise creates
        a fresh collection.
        """
        if self._vectorstore is not None:
            return self._vectorstore

        with self._lock:
            if self._vectorstore is not None:
                return self._vectorstore

            print(f"[RAG] Initialising vector store at {self.persist_dir}...")
            try:
                self._vectorstore = Chroma(
                    persist_directory=str(self.persist_dir),
                    embedding_function=self._get_embeddings(),
                )
                print("[RAG] Vector store ready.")
            except Exception as exc:
                raise RuntimeError(f"Failed to initialise vector store: {exc}") from exc

        return self._vectorstore

    def _get_text_splitter(self) -> Any:
        """Lazily initialise the text splitter for chunking documents."""
        if self._text_splitter is not None:
            return self._text_splitter

        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""],
            length_function=len,
            is_separator_regex=False,
        )
        return self._text_splitter

    # -----------------------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------------------
    def _load_single_document(self, file_path: Path) -> List[Any]:
        """
        Load a single document file and return LangChain Document objects.

        Args:
            file_path: Path to the document.

        Returns:
            List of Document objects, or empty list on failure.
        """
        ext = file_path.suffix.lower()
        loader_type = self.SUPPORTED_EXTENSIONS.get(ext)

        if loader_type is None:
            return []

        try:
            if loader_type == "pdf":
                if PyPDFLoader is None:
                    print(f"[RAG] PyPDFLoader unavailable, skipping {file_path.name}")
                    return []
                loader = PyPDFLoader(str(file_path))
            else:
                if TextLoader is None:
                    return []
                # Try UTF-8 first, fallback to latin-1 for legacy files
                try:
                    loader = TextLoader(str(file_path), encoding="utf-8")
                except UnicodeDecodeError:
                    loader = TextLoader(str(file_path), encoding="latin-1")

            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = str(file_path)
                doc.metadata["filename"] = file_path.name
                doc.metadata["extension"] = ext
            return docs

        except Exception as exc:
            print(f"[RAG] Could not load {file_path}: {exc}")
            return []

    def _discover_documents(self, folder_path: Path) -> List[Path]:
        """
        Recursively discover all supported documents in a folder.

        Args:
            folder_path: Root directory to scan.

        Returns:
            List of file paths to supported documents.
        """
        if not folder_path.exists():
            return []

        files: List[Path] = []
        for item in folder_path.rglob("*"):
            if not item.is_file():
                continue
            # Skip hidden directories in path
            if any(part.startswith(".") or part in self.SKIP_DIRS for part in item.relative_to(folder_path).parts):
                continue
            if item.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                files.append(item)

        return sorted(files)

    # -----------------------------------------------------------------------
    # Indexing
    # -----------------------------------------------------------------------
    def index_folder(self, folder_path: Union[str, Path]) -> str:
        """
        Index all supported documents in a folder recursively.

        Documents are split into chunks, embedded, and stored in the
        persistent ChromaDB vector store.

        Args:
            folder_path: Path to the folder containing documents.

        Returns:
            Human-readable result message.
        """
        if self._indexing:
            return "Indexing already in progress. Please wait."

        with self._lock:
            self._indexing = True

        try:
            result = self._index_folder_impl(Path(folder_path).expanduser().resolve())
            return result.message
        finally:
            with self._lock:
                self._indexing = False

    def _index_folder_impl(self, folder_path: Path) -> IndexResult:
        """Internal implementation of folder indexing."""
        result = IndexResult(success=False)

        if not folder_path.exists():
            result.errors.append(f"Folder not found: {folder_path}")
            result.message = f"Folder not found: {folder_path}"
            return result

        # Discover files
        file_paths = self._discover_documents(folder_path)
        if not file_paths:
            result.message = "No supported documents found in folder."
            return result

        print(f"[RAG] Found {len(file_paths)} documents to index...")

        # Load documents
        all_docs: List[Any] = []
        for fp in file_paths:
            docs = self._load_single_document(fp)
            if docs:
                all_docs.extend(docs)
            else:
                result.errors.append(f"Failed to load: {fp.name}")

        result.documents_loaded = len(all_docs)

        if not all_docs:
            result.message = "No documents could be loaded. Check file permissions and formats."
            return result

        # Chunk documents
        print(f"[RAG] Splitting {len(all_docs)} documents into chunks...")
        splitter = self._get_text_splitter()
        try:
            chunks = splitter.split_documents(all_docs)
        except Exception as exc:
            result.errors.append(f"Chunking failed: {exc}")
            result.message = f"Failed to chunk documents: {exc}"
            return result

        result.chunks_created = len(chunks)

        if not chunks:
            result.message = "No chunks created. Documents may be empty."
            return result

        # Store in vector database (batch for memory efficiency)
        print(f"[RAG] Storing {len(chunks)} chunks in vector store...")
        vectorstore = self._get_vectorstore()
        batch_size = 100  # Process in batches to avoid memory spikes

        try:
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                vectorstore.add_documents(batch)
                print(f"[RAG] Stored batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1}")

            # Persist to disk (ChromaDB auto-persists, but explicit call ensures consistency)
            if hasattr(vectorstore, "persist"):
                vectorstore.persist()

            result.success = True
            result.message = (
                f"Successfully indexed {result.documents_loaded} documents "
                f"({result.chunks_created} chunks) from {folder_path}"
            )
            print(f"[RAG] {result.message}")

        except Exception as exc:
            result.errors.append(f"Vector store error: {exc}")
            result.message = f"Failed to store chunks: {exc}"

        return result

    def index_file(self, file_path: Union[str, Path]) -> str:
        """
        Index a single document file.

        Args:
            file_path: Path to the document.

        Returns:
            Human-readable result message.
        """
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"File not found: {path}"

        result = self._index_folder_impl(path.parent) if path.is_dir() else self._index_single_file(path)
        return result.message if isinstance(result, IndexResult) else result

    def _index_single_file(self, file_path: Path) -> IndexResult:
        """Index a single file."""
        result = IndexResult(success=False)
        docs = self._load_single_document(file_path)

        if not docs:
            result.message = f"Could not load {file_path.name}"
            return result

        splitter = self._get_text_splitter()
        chunks = splitter.split_documents(docs)
        result.chunks_created = len(chunks)

        if not chunks:
            result.message = "No content extracted from file."
            return result

        try:
            vectorstore = self._get_vectorstore()
            vectorstore.add_documents(chunks)
            if hasattr(vectorstore, "persist"):
                vectorstore.persist()
            result.success = True
            result.message = f"Indexed {file_path.name} ({len(chunks)} chunks)"
        except Exception as exc:
            result.errors.append(str(exc))
            result.message = f"Failed to index {file_path.name}: {exc}"

        return result

    # -----------------------------------------------------------------------
    # Search & Query
    # -----------------------------------------------------------------------
    def search(self, query: str, k: int = 5) -> List[SearchResult]:
        """
        Perform semantic search over the knowledge base.

        Args:
            query: Search query string.
            k: Number of results to return.

        Returns:
            List of SearchResult objects with content, source, and metadata.
        """
        if not query or not query.strip():
            return []

        if k < 1:
            k = 1
        if k > 50:
            k = 50  # Sanity cap

        try:
            vectorstore = self._get_vectorstore()
            docs = vectorstore.similarity_search(query, k=k)

            results: List[SearchResult] = []
            for doc in docs:
                results.append(
                    SearchResult(
                        content=doc.page_content,
                        source=doc.metadata.get("source", "Unknown"),
                        filename=doc.metadata.get("filename", "Unknown"),
                        metadata=dict(doc.metadata),
                    )
                )
            return results
        except Exception as exc:
            print(f"[RAG] Search error: {exc}")
            return []

    def query(self, query: str, k: int = 3) -> str:
        """
        Search the knowledge base and return a human-readable formatted result.

        Args:
            query: Natural language query.
            k: Number of results to include.

        Returns:
            Formatted string with search results, or a "not found" message.
        """
        results = self.search(query, k=k)
        if not results:
            return "No relevant information found in your knowledge base."

        lines: List[str] = []
        for i, res in enumerate(results, 1):
            content = res.content[:300] + "..." if len(res.content) > 300 else res.content
            lines.append(f"[{i}] From {res.filename}:\n{content}\n")

        return "\n".join(lines)

    def search_with_scores(self, query: str, k: int = 5) -> List[SearchResult]:
        """
        Perform semantic search and return results with similarity scores.

        Args:
            query: Search query string.
            k: Number of results.

        Returns:
            List of SearchResult objects including similarity scores.
        """
        if not query or not query.strip():
            return []

        k = max(1, min(k, 50))

        try:
            vectorstore = self._get_vectorstore()
            docs_with_scores = vectorstore.similarity_search_with_score(query, k=k)

            results: List[SearchResult] = []
            for doc, score in docs_with_scores:
                results.append(
                    SearchResult(
                        content=doc.page_content,
                        source=doc.metadata.get("source", "Unknown"),
                        filename=doc.metadata.get("filename", "Unknown"),
                        score=float(score),
                        metadata=dict(doc.metadata),
                    )
                )
            return results
        except Exception as exc:
            print(f"[RAG] Search with scores error: {exc}")
            return []

    # -----------------------------------------------------------------------
    # Statistics & Management
    # -----------------------------------------------------------------------
    def get_stats(self) -> str:
        """
        Get human-readable statistics about the knowledge base.

        Returns:
            Formatted string with chunk count, model info, and status.
        """
        stats = self._get_stats()
        if not stats.is_ready:
            return "Knowledge base is not initialised."
        return (
            f"Knowledge Base Stats:\n"
            f"  • Total chunks: {stats.total_chunks}\n"
            f"  • Embedding model: {stats.embedding_model}\n"
            f"  • Storage: {stats.persist_directory}\n"
            f"  • Status: Ready"
        )

    def _get_stats(self) -> KnowledgeStats:
        """Internal method to gather knowledge base statistics."""
        stats = KnowledgeStats(
            persist_directory=str(self.persist_dir),
            embedding_model=self.embedding_model_name,
        )

        try:
            vectorstore = self._get_vectorstore()
            # ChromaDB collection count
            if hasattr(vectorstore, "_collection") and hasattr(vectorstore._collection, "count"):
                stats.total_chunks = vectorstore._collection.count()
            elif hasattr(vectorstore, "_client"):
                # Alternative API for newer Chroma versions
                stats.total_chunks = len(vectorstore._client.list_collections())
            stats.is_ready = True
        except Exception as exc:
            print(f"[RAG] Stats error: {exc}")
            stats.is_ready = False

        return stats

    def clear(self) -> str:
        """
        Clear all indexed documents from the knowledge base.

        WARNING: This permanently deletes all embeddings.

        Returns:
            Confirmation message.
        """
        with self._lock:
            try:
                if self._vectorstore is not None:
                    if hasattr(self._vectorstore, "delete_collection"):
                        self._vectorstore.delete_collection()
                    self._vectorstore = None

                # Remove persist directory contents
                if self.persist_dir.exists():
                    import shutil
                    shutil.rmtree(self.persist_dir, ignore_errors=True)
                    self.persist_dir.mkdir(parents=True, exist_ok=True)

                return "Knowledge base cleared successfully."
            except Exception as exc:
                return f"Failed to clear knowledge base: {exc}"

    def is_ready(self) -> bool:
        """Check if the RAG system is fully initialised and ready."""
        try:
            return self._get_vectorstore() is not None
        except Exception:
            return False
