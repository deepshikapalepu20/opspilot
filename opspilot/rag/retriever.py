from opspilot.rag.ingest import (
    embedder,
    collection,
)

from opspilot.llm import call_local_json


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_RESULTS = 4

WEAK_SCORE_THRESHOLD = 0.60


# ============================================================
# QUERY REFORMULATION PROMPT
# ============================================================

REFORMULATE_PROMPT = """
The search query below returned weak or irrelevant
results from an incident-knowledge base.

Rewrite the query as a specific incident investigation
query.

Include:
- service
- symptoms
- infrastructure/application component
- operational failure mechanism

Original query:
{query}

Return ONLY JSON:

{{
    "reformulated_query": "..."
}}
"""


# ============================================================
# VECTOR SEARCH
# ============================================================

def _search(
    query: str,
    service: str | None = None,
    n: int = DEFAULT_RESULTS,
) -> dict:

    embedding = embedder.encode(
        [query]
    ).tolist()

    # --------------------------------------------------------
    # Important:
    #
    # We do NOT filter strictly by service.
    #
    # Generic troubleshooting documents such as:
    # database-pool.md
    #
    # may not have a service field but can still be highly
    # relevant to checkout-api.
    # --------------------------------------------------------

    result = collection.query(
        query_embeddings=embedding,
        n_results=n,
    )

    return result


# ============================================================
# CHECK RETRIEVAL QUALITY
# ============================================================

def _is_weak_retrieval(
    result: dict,
) -> bool:

    distances = result.get(
        "distances",
        [[]],
    )

    if not distances:
        return True

    distances = distances[0]

    if not distances:
        return True

    best_distance = min(
        distances
    )

    return (
        best_distance
        > WEAK_SCORE_THRESHOLD
    )


# ============================================================
# REFORMULATE QUERY
# ============================================================

def _reformulate_query(
    query: str,
) -> str | None:

    try:

        result = call_local_json(
            REFORMULATE_PROMPT.format(
                query=query
            )
        )

    except Exception as exc:

        print(
            "\n=== RAG QUERY REFORMULATION ERROR ==="
        )

        print(
            str(exc)
        )

        return None

    if not isinstance(
        result,
        dict,
    ):
        return None

    reformulated_query = result.get(
        "reformulated_query"
    )

    if not isinstance(
        reformulated_query,
        str,
    ):
        return None

    reformulated_query = (
        reformulated_query.strip()
    )

    if not reformulated_query:
        return None

    return reformulated_query


# ============================================================
# EXTRACT CHUNKS
# ============================================================

def _build_chunks(
    result: dict,
) -> list[dict]:

    documents = result.get(
        "documents",
        [[]],
    )

    metadatas = result.get(
        "metadatas",
        [[]],
    )

    distances = result.get(
        "distances",
        [[]],
    )

    documents = (
        documents[0]
        if documents
        else []
    )

    metadatas = (
        metadatas[0]
        if metadatas
        else []
    )

    distances = (
        distances[0]
        if distances
        else []
    )

    chunks = []

    for index, document in enumerate(
        documents
    ):

        metadata = (
            metadatas[index]
            if index < len(metadatas)
            else {}
        )

        distance = (
            distances[index]
            if index < len(distances)
            else None
        )

        chunks.append(
            {
                "text": document,
                "source": metadata,
                "distance": distance,
            }
        )

    return chunks


# ============================================================
# RETRIEVE KNOWLEDGE
# ============================================================

def retrieve(
    query: str,
    service: str | None = None,
) -> dict:

    if not isinstance(
        query,
        str,
    ):

        return {
            "query_used": "",
            "chunks": [],
            "count": 0,
            "error": "Query must be a string.",
        }

    query = query.strip()

    if not query:

        return {
            "query_used": "",
            "chunks": [],
            "count": 0,
            "error": "Query cannot be empty.",
        }

    print(
        "\n========================================"
    )

    print(
        "             RAG RETRIEVAL"
    )

    print(
        "========================================"
    )

    print(
        "Query:",
        query,
    )

    if service:
        print(
            "Service:",
            service,
        )

    # --------------------------------------------------------
    # First search
    # --------------------------------------------------------

    result = _search(
        query=query,
        service=service,
    )

    # --------------------------------------------------------
    # Reformulate only if weak
    # --------------------------------------------------------

    if _is_weak_retrieval(result):

        print(
            "\n=== WEAK RAG RETRIEVAL ==="
        )

        better_query = (
            _reformulate_query(
                query
            )
        )

        if better_query:

            print(
                "Reformulated query:",
                better_query,
            )

            retry_result = _search(
                query=better_query,
                service=service,
            )

            retry_chunks = (
                _build_chunks(
                    retry_result
                )
            )

            if retry_chunks:

                result = retry_result
                query = better_query

    # --------------------------------------------------------
    # Build final chunks
    # --------------------------------------------------------

    chunks = _build_chunks(
        result
    )

    print(
        "\n=== RETRIEVED KNOWLEDGE ==="
    )

    print(
        "Chunks:",
        len(chunks),
    )

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):

        print(
            f"\n--- Chunk {index} ---"
        )

        print(
            "Source:",
            chunk["source"],
        )

        print(
            "Distance:",
            chunk["distance"],
        )

        print(
            "Text:",
            chunk["text"],
        )

    return {
        "query_used": query,
        "chunks": chunks,
        "count": len(chunks),
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    result = retrieve(
        query=(
            "How do I investigate checkout API "
            "database connection pool exhaustion?"
        ),
        service="checkout-api",
    )

    print(
        "\n=== FINAL RAG RESULT ==="
    )

    print(result)