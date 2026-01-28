"""
RAG (Retrieval-Augmented Generation) system for Sundai.

This module:
1. Fetches documents from Notion API
2. Chunks documents into smaller pieces
3. Generates embeddings and stores them in SQLite with sqlite-vec
4. Provides hybrid search (BM25 + semantic) for retrieval
"""
import json
import os
import sqlite3
import re
import struct
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
import sqlite_vec
from fastembed import TextEmbedding
from app.clients.notion import NotionClient
from app.utils.paths import data_path

# Suppress Hugging Face token warning
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

load_dotenv()

# Initialize SQLite database with FTS5 and sqlite-vec support
DATABASE_PATH = data_path("tutorial_rag.db")
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_database(db_path: Path) -> sqlite3.Connection:
    """Create database with embeddings table, FTS5 for BM25, and vec0 for vectors."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Load sqlite-vec extension
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    cursor = conn.cursor()

    # Metadata table (stores content and metadata, linked to vectors by rowid)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_id TEXT,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Vector table using sqlite-vec (384 dimensions for MiniLM-L6-v2)
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
            embedding float[384] distance_metric=cosine
        )
    """)

    # FTS5 virtual table for BM25 keyword search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS embeddings_fts USING fts5(
            content,
            source_type,
            source_id,
            content='embeddings_meta',
            content_rowid='id'
        )
    """)

    # Triggers to keep FTS5 in sync with embeddings_meta table
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS embeddings_ai AFTER INSERT ON embeddings_meta BEGIN
            INSERT INTO embeddings_fts(rowid, content, source_type, source_id)
            VALUES (new.id, new.content, new.source_type, new.source_id);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS embeddings_ad AFTER DELETE ON embeddings_meta BEGIN
            INSERT INTO embeddings_fts(embeddings_fts, rowid, content, source_type, source_id)
            VALUES ('delete', old.id, old.content, old.source_type, old.source_id);
        END
    """)

    conn.commit()
    return conn


# Initialize the database
db = init_database(DATABASE_PATH)

# Initialize the embedding model (downloads on first use)
embedding_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")


def generate_embedding(text: str) -> list[float]:
    """Generate a 384-dimensional embedding for the given text."""
    embeddings = list(embedding_model.embed([text]))
    return embeddings[0].tolist()


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts in a batch (more efficient)."""
    if not texts:
        return []
    embeddings = list(embedding_model.embed(texts))
    return [emb.tolist() for emb in embeddings]


def chunk_document(content: str, source_id: str) -> list[dict]:
    """
    Chunk a document by ## headers (works with Notion content which uses markdown-style headers).

    Each chunk includes:
    - The document title (# header) for context
    - The section content
    - Metadata about the source
    """
    # Extract document title
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    doc_title = title_match.group(1) if title_match else source_id

    # Split on ## headers
    sections = re.split(r'(?=^##\s+)', content, flags=re.MULTILINE)

    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Extract section title
        section_title_match = re.search(r'^##\s+(.+)$', section, re.MULTILINE)
        section_title = section_title_match.group(1) if section_title_match else "Introduction"

        # Build chunk with context
        chunk_content = f"[From: {source_id}]\n# {doc_title}\n\n{section}"

        chunks.append({
            "content": chunk_content,
            "metadata": {
                "source_id": source_id,
                "section_title": section_title,
            }
        })

    return chunks if chunks else [{"content": content, "metadata": {"source_id": source_id}}]


def serialize_embedding(embedding: list[float]) -> bytes:
    """Serialize embedding to binary format for sqlite-vec."""
    return struct.pack(f'{len(embedding)}f', *embedding)


def save_embedding(conn, source_type: str, content: str, embedding: list[float],
                   source_id: str = None, metadata: dict = None) -> int:
    """
    Save an embedding to the database.

    Inserts into:
    1. embeddings_meta - content and metadata (FTS5 updated via trigger)
    2. vec_embeddings - vector for similarity search (matched by rowid)
    """
    cursor = conn.cursor()

    # Insert metadata (FTS5 index updated automatically via trigger)
    cursor.execute(
        """
        INSERT INTO embeddings_meta (source_type, source_id, content, metadata, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            source_type,
            source_id,
            content,
            json.dumps(metadata) if metadata else None,
            datetime.now().isoformat(),
        ),
    )
    rowid = cursor.lastrowid

    # Insert vector with matching rowid
    cursor.execute(
        """
        INSERT INTO vec_embeddings (rowid, embedding)
        VALUES (?, ?)
        """,
        (rowid, serialize_embedding(embedding)),
    )

    conn.commit()
    return rowid


def embed_notion_page(conn, notion_page_url: str, source_type: str = "notion_page") -> int:
    """
    Fetch a Notion page, chunk it, generate embeddings, and save to database.
    
    Args:
        conn: Database connection
        notion_page_url: URL of the Notion page to fetch
        source_type: Type identifier for the source (default: "notion_page")
    
    Returns:
        Number of chunks saved
    """
    
    try:
        # Fetch content from Notion
        notion_client = NotionClient()
        content = notion_client.get_page_as_text(notion_page_url)
        
        if not content or not content.strip():
            return 0
        
        
        # Chunk the content
        chunks = chunk_document(content, notion_page_url)
        
        # Batch generate embeddings
        texts = [c["content"] for c in chunks]
        embeddings = generate_embeddings_batch(texts)
        
        # Save each chunk (to both embeddings_meta and vec_embeddings)
        for chunk, embedding in zip(chunks, embeddings):
            save_embedding(
                conn,
                source_type=source_type,
                content=chunk["content"],
                embedding=embedding,
                source_id=notion_page_url,
                metadata=chunk["metadata"],
            )
        
        return len(chunks)
        
    except Exception as e:
        import traceback
        return 0


def embed_notion_pages(conn, notion_page_urls: List[str], source_type: str = "notion_page") -> int:
    """
    Embed multiple Notion pages.
    
    Args:
        conn: Database connection
        notion_page_urls: List of Notion page URLs
        source_type: Type identifier for the source
    
    Returns:
        Total number of chunks saved
    """
    
    total_chunks = 0
    for url in notion_page_urls:
        chunks = embed_notion_page(conn, url, source_type)
        total_chunks += chunks
    
    
    return total_chunks


def bm25_search(conn, query: str, limit: int = 100) -> dict[int, float]:
    """
    Search using BM25 ranking via FTS5.

    Returns dict mapping embedding_id to raw BM25 score.
    Note: FTS5 BM25 scores are NEGATIVE (more negative = better match).
    """
    cursor = conn.cursor()

    # Escape special FTS5 characters
    safe_query = query.replace('"', '""')

    try:
        cursor.execute("""
            SELECT rowid, bm25(embeddings_fts) as score
            FROM embeddings_fts
            WHERE embeddings_fts MATCH ?
            LIMIT ?
        """, (safe_query, limit))

        return {row[0]: row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        # No matches or invalid query
        return {}


def semantic_search(conn, query_embedding: list[float], limit: int = 100) -> dict[int, float]:
    """
    Search using sqlite-vec's native cosine distance.

    Returns dict mapping rowid to cosine distance.
    Note: cosine distance is in [0, 2] where 0 = identical, 2 = opposite.
    """
    cursor = conn.cursor()

    # sqlite-vec requires 'k = ?' in the WHERE clause when using a parameterized limit
    cursor.execute("""
        SELECT rowid, distance
        FROM vec_embeddings
        WHERE embedding MATCH ?
          AND k = ?
        ORDER BY distance
    """, (serialize_embedding(query_embedding), limit))

    return {row[0]: row[1] for row in cursor.fetchall()}


def normalize_bm25_scores(bm25_scores: dict[int, float]) -> dict[int, float]:
    """
    Normalize BM25 scores to [0, 1] range.

    FTS5 BM25 scores are negative (more negative = better).
    We invert so that best match gets 1.0, worst gets 0.0.
    """
    if not bm25_scores:
        return {}

    scores = list(bm25_scores.values())
    min_score = min(scores)  # Most negative = best
    max_score = max(scores)  # Least negative = worst

    if min_score == max_score:
        return {id: 1.0 for id in bm25_scores}

    score_range = max_score - min_score
    return {
        id: (max_score - score) / score_range
        for id, score in bm25_scores.items()
    }


def normalize_distances(distances: dict[int, float]) -> dict[int, float]:
    """
    Normalize cosine distances to similarity scores in [0, 1].

    Cosine distance is in [0, 2] where 0 = identical.
    We convert to similarity: 1 - (distance / 2)
    Then normalize so best match gets 1.0.
    """
    if not distances:
        return {}

    # Convert distances to similarities
    similarities = {id: 1 - (dist / 2) for id, dist in distances.items()}

    # Normalize to [0, 1] range
    min_sim = min(similarities.values())
    max_sim = max(similarities.values())

    if min_sim == max_sim:
        return {id: 1.0 for id in similarities}

    sim_range = max_sim - min_sim
    return {
        id: (sim - min_sim) / sim_range
        for id, sim in similarities.items()
    }


def get_metadata_by_ids(conn, ids: list[int]) -> dict[int, dict]:
    """Retrieve metadata for given IDs from embeddings_meta table."""
    if not ids:
        return {}

    cursor = conn.cursor()
    placeholders = ",".join("?" * len(ids))
    cursor.execute(f"""
        SELECT id, source_type, source_id, content, metadata
        FROM embeddings_meta
        WHERE id IN ({placeholders})
    """, ids)

    results = {}
    for row in cursor.fetchall():
        results[row[0]] = {
            "source_type": row[1],
            "source_id": row[2],
            "content": row[3],
            "metadata": json.loads(row[4]) if row[4] else {},
        }
    return results


def hybrid_search(
    conn,
    query: str,
    query_embedding: list[float],
    keyword_weight: float = 0.5,
    semantic_weight: float = 0.5,
    top_k: int = 10,
) -> list[dict]:
    """
    Perform hybrid search combining BM25 and sqlite-vec cosine similarity.

    Formula: final_score = keyword_weight * bm25 + semantic_weight * cosine_sim

    Args:
        conn: Database connection
        query: Search query text
        query_embedding: Pre-computed embedding of the query
        keyword_weight: Weight for BM25 (0-1)
        semantic_weight: Weight for cosine similarity (0-1)
        top_k: Number of results to return

    Returns:
        List of results sorted by combined score (highest first)
    """
    # Step 1: Get BM25 scores from FTS5
    bm25_raw = bm25_search(conn, query)
    bm25_normalized = normalize_bm25_scores(bm25_raw)

    # Step 2: Get semantic distances from sqlite-vec
    semantic_raw = semantic_search(conn, query_embedding, limit=100)
    semantic_normalized = normalize_distances(semantic_raw)

    # Step 3: Get all unique IDs from both searches
    all_ids = set(bm25_normalized.keys()) | set(semantic_normalized.keys())

    if not all_ids:
        return []

    # Step 4: Get metadata for all candidates
    metadata = get_metadata_by_ids(conn, list(all_ids))

    # Step 5: Compute combined scores
    scored_results = []

    for id in all_ids:
        # BM25 score (0 if no keyword match)
        bm25_score = bm25_normalized.get(id, 0.0)

        # Semantic score (0 if not in top semantic results)
        semantic_score = semantic_normalized.get(id, 0.0)

        # Combined score
        final_score = (keyword_weight * bm25_score) + (semantic_weight * semantic_score)

        meta = metadata.get(id, {})
        scored_results.append({
            "id": id,
            "content": meta.get("content", ""),
            "source_type": meta.get("source_type", ""),
            "source_id": meta.get("source_id", ""),
            "metadata": meta.get("metadata", {}),
            "bm25_score": bm25_score,
            "semantic_score": semantic_score,
            "final_score": final_score,
        })

    # Sort by final score (descending)
    scored_results.sort(key=lambda x: x["final_score"], reverse=True)

    return scored_results[:top_k]


def format_context_for_prompt(results: list[dict], max_chars: int = 4000) -> str:
    """Format search results into context for the LLM prompt."""
    if not results:
        return "No relevant context found."

    context_parts = []
    chars_used = 0

    for i, result in enumerate(results, 1):
        header = f"[{i}. {result['source_type']}] (score: {result['final_score']:.2f})"
        content = result["content"]

        available = max_chars - chars_used - len(header) - 10
        if available <= 100:
            break

        if len(content) > available:
            content = content[:available - 3] + "..."

        entry = f"{header}\n{content}\n"
        context_parts.append(entry)
        chars_used += len(entry)

    return "\n".join(context_parts)


def retrieve_context(conn, query: str, top_k: int = 10) -> tuple[str, list[dict]]:
    """High-level function to retrieve and format context for RAG."""
    query_embedding = generate_embedding(query)
    results = hybrid_search(conn, query, query_embedding, top_k=top_k)
    formatted = format_context_for_prompt(results)
    return formatted, results


 
