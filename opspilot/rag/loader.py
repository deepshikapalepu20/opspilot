from pathlib import Path
from typing import List, Dict


# Directory containing the RAG knowledge base
KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"


def load_documents() -> List[Dict]:
    """
    Load all Markdown knowledge documents.

    Returns:
        A list of dictionaries containing:
        - id
        - source
        - category
        - content
    """

    documents = []

    if not KNOWLEDGE_DIR.exists():
        raise FileNotFoundError(
            f"Knowledge directory not found: {KNOWLEDGE_DIR}"
        )

    for file_path in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        try:
            content = file_path.read_text(
                encoding="utf-8"
            ).strip()
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Could not decode knowledge file: {file_path}"
            ) from exc

        if not content:
            continue

        relative_path = file_path.relative_to(KNOWLEDGE_DIR)

        category = relative_path.parts[0] if len(relative_path.parts) > 1 else "general"

        documents.append(
            {
                "id": str(relative_path).replace("\\", "/"),
                "source": file_path.name,
                "category": category,
                "path": str(file_path),
                "content": content,
            }
        )

    return documents


if __name__ == "__main__":
    docs = load_documents()

    print("=" * 60)
    print("OPSPILOT RAG DOCUMENT LOADER")
    print("=" * 60)
    print(f"Knowledge directory: {KNOWLEDGE_DIR}")
    print(f"Documents loaded: {len(docs)}")
    print()

    for doc in docs:
        print(f"ID       : {doc['id']}")
        print(f"Source   : {doc['source']}")
        print(f"Category : {doc['category']}")
        print(f"Characters: {len(doc['content'])}")
        print("-" * 60)