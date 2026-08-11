"""
Rico RAG System - Private Knowledge Base
"""
import os
from pathlib import Path
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

class RicoRAG:
    def __init__(self, persist_dir="~/rico_knowledge"):
        self.persist_dir = os.path.expanduser(persist_dir)
        self.vectorstore = None
        self.embedding_model = None
        self._init_embeddings()
        self._load_or_create_db()

    def _init_embeddings(self):
        """Initialize local HuggingFace embedding model."""
        print("Loading embedding model...")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

    def _load_or_create_db(self):
        """Load or create persistent vector database."""
        os.makedirs(self.persist_dir, exist_ok=True)
        self.vectorstore = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embedding_model
        )

    def index_folder(self, folder_path):
        """Index all supported documents in a folder."""
        folder_path = os.path.expanduser(folder_path)
        if not os.path.exists(folder_path):
            return f"Folder not found: {folder_path}"

        all_docs = []
        supported_extensions = {'.txt', '.pdf', '.md', '.py', '.js', '.html', '.css', '.json'}

        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', '__pycache__')]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext not in supported_extensions:
                    continue
                
                file_path = os.path.join(root, file)
                try:
                    loader = PyPDFLoader(file_path) if ext == '.pdf' else TextLoader(file_path, encoding='utf-8')
                    docs = loader.load()
                    
                    for doc in docs:
                        doc.metadata['source'] = file_path
                        doc.metadata['filename'] = file
                    all_docs.extend(docs)
                except Exception as e:
                    print(f"Could not load {file}: {e}")

        if not all_docs:
            return "No supported documents found in folder."

        # Chunk documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        chunks = text_splitter.split_documents(all_docs)

        # Store in Chroma (Auto-persisted in newer versions)
        self.vectorstore.add_documents(chunks)
        return f"Successfully indexed {len(all_docs)} documents ({len(chunks)} chunks) from {folder_path}"

    def search(self, query, k=5):
        """Search raw vectorstore for matching documents."""
        if not self.vectorstore:
            return []
        return self.vectorstore.similarity_search(query, k=k)

    def query(self, query, k=3):
        """Search and return human-readable results."""
        results = self.search(query, k)
        if not results:
            return "No relevant information found in your knowledge base."

        formatted = []
        for i, doc in enumerate(results, 1):
            filename = doc.metadata.get('filename', 'Unknown')
            content = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            formatted.append(f"[{i}] From {filename}:\n{content}\n")

        return "\n".join(formatted)

    def get_stats(self):
        """Get knowledge base statistics."""
        if not self.vectorstore:
            return "Knowledge base is uninitialized."
        try:
            count = self.vectorstore._collection.count()
            return f"Knowledge Base Stats: {count} chunks indexed at {self.persist_dir}"
        except Exception:
            return "Knowledge base active."
