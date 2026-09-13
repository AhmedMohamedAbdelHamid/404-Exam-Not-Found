"""
embed_to_chroma.py — Day 3 deliverable (Person A), started Day 2.

Loads chunks_en.json / chunks_ar.json (produced by chunker.py) into
TWO separate ChromaDB collections, per schema.py's explicit note:

    "A's retrieval, embedding, and ChromaDB collections must be
    language-scoped (e.g. separate collections per language, or a
    language metadata filter), not a single merged index."

We use separate collections (chunks_en / chunks_ar) rather than one
merged collection + filter -- simpler to reason about, and makes it
structurally impossible for a student's retrieval to leak the other
language's chunks even if a metadata filter is forgotten somewhere
downstream.

EMBEDDING MODELS: different embedders per collection, chosen from what
we actually measured:
  - EN collection: ChromaDB's default (all-MiniLM-L6-v2, English-tuned).
    Tested clean topic separation (loops -> 12-3, functions -> 12-5,
    etc.) at low distances.
  - AR collection: paraphrase-multilingual-MiniLM-L12-v2. The default
    model collapsed on Arabic -- three unrelated Arabic queries ("for
    loop", "what is a variable", "function return value") all
    top-matched the SAME chunk (ar_ch12_12-2_p172), meaning it wasn't
    discriminating between topics at all. The multilingual model fixed
    the collapse (each query now returns different chunks) but is
    still not fully topic-accurate on its own (e.g. a "for loop" query
    doesn't reliably rank a 12-3/loops chunk first). Tracked as a known
    limitation below -- get_chunks() on Day 4 should filter by the
    `topic` metadata tag first (which IS reliable, from page structure)
    and treat the embedding as a secondary within-topic ranking signal
    for Arabic, not the primary retrieval mechanism.

Using different embedders per language is intentional, not an
oversight: each collection is queried independently (language is fixed
per student, never mixed per schema.py), so there's no requirement for
EN and AR vectors to share a coordinate space. Picking the best model
per language is strictly better than forcing one compromise model on
both.

Run: python3 embed_to_chroma.py
"""

import json
import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = "./chroma_db"
AR_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def load_chunks(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_collection(client, name: str, chunks: list[dict], embedding_fn):
    # get_or_create so re-running this script is idempotent during dev.
    # NOTE: EN and AR now intentionally use DIFFERENT embedding
    # functions (see module docstring). If you previously ran this
    # script with a different embedder on either collection, delete
    # ./chroma_db before re-running -- Chroma does not auto-migrate
    # embeddings when the embedding function changes on an existing
    # collection, and mixing vector spaces silently breaks retrieval.
    collection = client.get_or_create_collection(
        name=name, embedding_function=embedding_fn
    )

    ids = [c["chunk_id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "topic": c["topic"],
            "language": c["language"],
            "chunk_type": c["chunk_type"],
            "source_pages": json.dumps(c["source_pages"]),
        }
        for c in chunks
    ]

    # upsert avoids duplicate-id errors on re-run
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return collection


def sanity_query(collection, query: str, n: int = 3):
    results = collection.query(query_texts=[query], n_results=n)
    print(f"\nQuery: {query!r}")
    for doc_id, dist, meta in zip(
        results["ids"][0], results["distances"][0], results["metadatas"][0]
    ):
        print(f"  {doc_id:25s} dist={dist:.4f}  topic={meta['topic']}  type={meta['chunk_type']}")


def main():
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    en_embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    ar_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=AR_MODEL_NAME
    )

    en_chunks = load_chunks("chunks_en.json")
    ar_chunks = load_chunks("chunks_ar.json")

    en_collection = build_collection(client, "chunks_en", en_chunks, en_embedding_fn)
    ar_collection = build_collection(client, "chunks_ar", ar_chunks, ar_embedding_fn)

    print(f"chunks_en collection: {en_collection.count()} chunks embedded")
    print(f"chunks_ar collection: {ar_collection.count()} chunks embedded")

    # --- sanity queries: prove retrieval isn't broken, not a full eval ---
    print("\n" + "=" * 60)
    print("SANITY QUERIES (EN)")
    print("=" * 60)
    sanity_query(en_collection, "how does a for loop work in python")
    sanity_query(en_collection, "what is a variable")
    sanity_query(en_collection, "how do functions return values")

    print("\n" + "=" * 60)
    print("SANITY QUERIES (AR) -- previously all top-matched the same")
    print("chunk on the English-only default embedder; should now")
    print("differentiate by topic like the EN queries above")
    print("=" * 60)
    sanity_query(ar_collection, "حلقة for في بايثون")       # "for loop in python"
    sanity_query(ar_collection, "ما هو المتغير")             # "what is a variable"
    sanity_query(ar_collection, "الدالة والقيمة المرجعة")     # "function and return value"


if __name__ == "__main__":
    main()

