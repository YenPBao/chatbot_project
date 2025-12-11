"""
Ingest documents into Elasticsearch RAG index.

Usage (from project root):
  python src/scripts/ingest_to_es.py --source src/resources/documents --index docs

Supports .txt and .md files. If PyPDF2 is installed, will also try to extract text from .pdf files.

Chunks each document into fixed-size windows with overlap and indexes them using the
`es_rag_service.ESRAGService.index_documents` method which handles embeddings.
"""

import argparse
from pathlib import Path
from typing import List, Dict
import uuid
import logging

try:
    from PyPDF2 import PdfReader

    _HAS_PDF = True
except Exception:
    _HAS_PDF = False

from app.services.cache_service import get_es_rag
from app.core.config import settings

logger = logging.getLogger("ingest_to_es")


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf_file(path: Path) -> str:
    if not _HAS_PDF:
        raise RuntimeError("PyPDF2 not available to read PDF files")
    reader = PdfReader(str(path))
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            continue
    return "\n".join(pages)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    L = len(text)
    while start < L:
        end = min(start + chunk_size, L)
        chunk = text[start:end]
        chunks.append(chunk.strip())
        if end == L:
            break
        start = max(0, end - overlap)
    return chunks


async def ingest_folder(source: Path, index: str, chunk_size: int, overlap: int):
    es = get_es_rag()
    files = [p for p in source.rglob("*") if p.is_file()]
    logger.info("Found %d files in %s", len(files), source)
    batch: List[Dict] = []
    for f in files:
        ext = f.suffix.lower()
        try:
            if ext in {".txt", ".md"}:
                text = read_text_file(f)
            elif ext == ".pdf":
                if _HAS_PDF:
                    text = read_pdf_file(f)
                else:
                    logger.warning("Skipping PDF (PyPDF2 not installed): %s", f)
                    continue
            else:
                logger.info("Skipping unsupported file: %s", f)
                continue
        except Exception as e:
            logger.exception("Failed to read %s: %s", f, e)
            continue

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        for i, c in enumerate(chunks):
            doc_id = f"{f.stem}-{i}-{uuid.uuid4().hex[:8]}"
            metadata = {"source": str(f.name), "chunk_index": i}
            batch.append({"id": doc_id, "text": c, "metadata": metadata})

        # flush in batches
        if len(batch) >= 200:
            logger.info("Indexing batch of %d chunks", len(batch))
            await es.index_documents(batch)
            batch = []

    if batch:
        logger.info("Indexing final batch of %d chunks", len(batch))
        await es.index_documents(batch)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=False, default="src/resources/documents")
    parser.add_argument(
        "--index", required=False, default=getattr(settings, "elastic_index", "docs")
    )
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--overlap", type=int, default=200)
    args = parser.parse_args()

    src = Path(args.source)
    if not src.exists() or not src.is_dir():
        print("Source folder not found:", src)
        return

    import asyncio

    asyncio.run(ingest_folder(src, args.index, args.chunk_size, args.overlap))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
