"""Recipe and nutrition retrieval using LangChain and ChromaDB."""

from __future__ import annotations

import os
import hashlib
from pathlib import Path
from threading import Lock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = PROJECT_ROOT / ".chroma"
_vector_store = None
_initialization_lock = Lock()


def _source_signature(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        if path.exists():
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _build_vector_store():
    """Build the local vector store on first retrieval, not at API import time."""
    global _vector_store
    if _vector_store is not None:
        return _vector_store
    with _initialization_lock:
        if _vector_store is not None:
            return _vector_store
        from langchain_community.document_loaders import PyPDFLoader, TextLoader
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        recipes_path = DATA_DIR / "recipes.txt"
        pdf_path = DATA_DIR / "usda_nutrition.pdf"
        source_paths = [recipes_path, pdf_path]
        documents = []
        if recipes_path.exists():
            documents.extend(TextLoader(str(recipes_path), encoding="utf-8").load())
        if pdf_path.exists():
            documents.extend(PyPDFLoader(str(pdf_path)).load())
        if not documents:
            raise FileNotFoundError("No nutrition documents were found in data/")
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_documents(documents)
        embeddings = HuggingFaceEmbeddings(
            model_name=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        )
        source_signature = _source_signature(source_paths)
        signature_path = CHROMA_DIR / "source_signature.txt"
        _vector_store = Chroma(
            collection_name="nutrition_kb",
            persist_directory=str(CHROMA_DIR),
            embedding_function=embeddings,
        )
        stored_signature = (
            signature_path.read_text(encoding="utf-8").strip()
            if signature_path.exists()
            else ""
        )
        if _vector_store._collection.count() and stored_signature != source_signature:
            _vector_store.delete_collection()
            _vector_store = Chroma(
                collection_name="nutrition_kb",
                persist_directory=str(CHROMA_DIR),
                embedding_function=embeddings,
            )
        if _vector_store._collection.count() == 0:
            _vector_store.add_documents(chunks)
            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            signature_path.write_text(source_signature, encoding="utf-8")
    return _vector_store


def retrieve_context(query: str) -> str:
    """Return the two most relevant nutrition or recipe chunks."""
    if os.getenv("ENABLE_RAG", "true").lower() in {"0", "false", "no", "off"}:
        return "RAG retrieval is disabled for this deployment; use the supplied structured data."
    store = _build_vector_store()
    documents = store.similarity_search(query, k=2)
    return "\n\n---\n\n".join(document.page_content for document in documents)
