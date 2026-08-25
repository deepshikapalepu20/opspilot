from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from opspilot.rag.loader import load_documents


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"

VECTOR_DIR = Path(
    __import__("os").environ.get(
        "OPSPILOT_VECTOR_DIR",
        str(DATA_DIR / "vector_store"),
    )
)


# ============================================================
# EMBEDDING MODEL
# ============================================================

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

embedder = SentenceTransformer(
    EMBEDDING_MODEL
)


# ============================================================
# CHROMADB
# ============================================================

chroma_client = chromadb.PersistentClient(
    path=str(VECTOR_DIR)
)

collection = chroma_client.get_or_create_collection(
    name="opspilot_knowledge"
)


# ============================================================
# TEXT CHUNKING
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = 180,
    overlap: int = 40,
) -> list[str]:
    """
    Split a document into overlapping word-based chunks.

    The overlap helps preserve context between chunks.
    """

    words = text.split()

    if not words:
        return []

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero."
        )

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be >= 0 and smaller than chunk_size."
        )

    chunks = []

    step = chunk_size - overlap

    for start in range(
        0,
        len(words),
        step,
    ):
        chunk = " ".join(
            words[
                start:start + chunk_size
            ]
        ).strip()

        if chunk:
            chunks.append(chunk)

        if start + chunk_size >= len(words):
            break

    return chunks


# ============================================================
# PREPARE KNOWLEDGE DOCUMENTS
# ============================================================

def prepare_documents():
    """
    Load documents from the current RAG knowledge directory
    and convert them into chunks suitable for ChromaDB.
    """

    source_documents = load_documents()

    all_chunks = []
    all_ids = []
    all_metadata = []

    for document in source_documents:

        document_id = document["id"]
        source = document["source"]
        category = document["category"]

        chunks = chunk_text(
            document["content"]
        )

        # ----------------------------------------------------
        # Try to determine the service from the document.
        # ----------------------------------------------------

        service = None

        if category == "runbooks":
            service = Path(source).stem

        elif "checkout-api" in document["content"].lower():
            service = "checkout-api"

        for index, chunk in enumerate(chunks):

            chunk_id = (
                f"{document_id.replace('/', '-')}"
                f"-chunk-{index}"
            )

            metadata = {
                "source": source,
                "category": category,
                "document_id": document_id,
                "chunk_index": index,
            }

            # Chroma metadata cannot contain None.
            if service:
                metadata["service"] = service

            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metadata.append(metadata)

    return (
        all_chunks,
        all_ids,
        all_metadata,
    )


# ============================================================
# BUILD VECTOR INDEX
# ============================================================

def build_index():

    print("=" * 60)
    print("OPSPILOT RAG INGESTION")
    print("=" * 60)

    print(
        f"Vector store: {VECTOR_DIR}"
    )

    print(
        f"Embedding model: {EMBEDDING_MODEL}"
    )

    # --------------------------------------------------------
    # Load and chunk all knowledge documents
    # --------------------------------------------------------

    documents, ids, metadata = (
        prepare_documents()
    )

    if not documents:
        raise RuntimeError(
            "No knowledge chunks were found."
        )

    print(
        f"Documents/chunks prepared: {len(documents)}"
    )

    # --------------------------------------------------------
    # Generate embeddings
    # --------------------------------------------------------

    print(
        "Generating embeddings..."
    )

    embeddings = embedder.encode(
        documents,
        show_progress_bar=True,
    ).tolist()

    # --------------------------------------------------------
    # Store in ChromaDB
    # --------------------------------------------------------

    collection.upsert(
        documents=documents,
        ids=ids,
        metadatas=metadata,
        embeddings=embeddings,
    )

    print()
    print(
        f"Indexed {len(documents)} chunks."
    )

    print(
        f"Collection: {collection.name}"
    )

    print(
        "RAG ingestion completed successfully."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    build_index()