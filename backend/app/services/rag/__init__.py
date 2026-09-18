"""RAG query stack — chunk, embed, retrieve, answer with citations.

The consumer of the shared ingestion/validation backbone: page text lives in
`document_pages`, facts in `extracted_facts` (with conflicts flagged for human
review), and the query engine here reads the same validated store and cites
every claim back to a source document + page number.
"""

from app.services.rag.chunker import (
    DEFAULT_CHUNK_SIZE_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    chunk_pages,
    chunk_text,
)
from app.services.rag.embedder import embed_and_store_chunks
from app.services.rag.query_engine import (
    NO_EVIDENCE_MESSAGE,
    SIMILARITY_THRESHOLD,
    answer_question,
)
from app.services.rag.retriever import best_vector_similarity, retrieve

__all__ = [
    "DEFAULT_CHUNK_SIZE_TOKENS",
    "DEFAULT_OVERLAP_TOKENS",
    "NO_EVIDENCE_MESSAGE",
    "SIMILARITY_THRESHOLD",
    "answer_question",
    "best_vector_similarity",
    "chunk_pages",
    "chunk_text",
    "embed_and_store_chunks",
    "retrieve",
]