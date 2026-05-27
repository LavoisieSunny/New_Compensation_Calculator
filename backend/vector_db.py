import os
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VectorDB")

# Centralized collection name for all legal precedents
COLLECTION_NAME = "legal_documents"

# Global lazy-initialized clients to prevent loading models during module imports
_qdrant_client = None
_embedding_model = None
VECTOR_DB_INITIALIZED = False

def get_qdrant_client():
    global _qdrant_client, VECTOR_DB_INITIALIZED
    if _qdrant_client is None:
        try:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qdrant_db")
            logger.info(f"Initializing Local-Disk Qdrant client at: {db_path}")
            
            # Start Qdrant in-process (local disk mode - SQLite-backed)
            _qdrant_client = QdrantClient(path=db_path)
            
            # Create centralized legal_documents collection if it doesn't exist yet
            # BGE-small-en-v1.5 has 384 dimensions and works best with Cosine distance
            try:
                _qdrant_client.get_collection(COLLECTION_NAME)
                logger.info(f"Existing Qdrant collection '{COLLECTION_NAME}' loaded successfully!")
            except Exception:
                logger.info(f"Collection '{COLLECTION_NAME}' not found. Creating a new one...")
                _qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
                logger.info(f"Collection '{COLLECTION_NAME}' created successfully!")
            
            VECTOR_DB_INITIALIZED = True
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {str(e)}")
            _qdrant_client = None
            VECTOR_DB_INITIALIZED = False
    return _qdrant_client

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            logger.info("Initializing FastEmbed TextEmbedding model (downloads 100MB model on first run)...")
            from fastembed import TextEmbedding
            # BAAI/bge-small-en-v1.5 is default: 384 dims, fast, CPU optimized, PyTorch-free!
            _embedding_model = TextEmbedding()
            logger.info("FastEmbed model loaded successfully!")
        except Exception as e:
            logger.error(f"Failed to initialize FastEmbed: {str(e)}")
            _embedding_model = None
    return _embedding_model

# ======================================================
# CHUNKING & INDEXING PIPELINE
# ======================================================

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list:
    """
    Intelligently chunks legal document text for optimal semantic retrieval.
    Guarantees that chunks:
    1. Do not slice raw characters or cut words in half.
    2. Prefer splitting on paragraph (\n\n) or sentence (. ! ?) boundaries.
    3. Keep complete legal facts and context intact.
    """
    import re
    # Normalize newlines
    text = text.replace("\r\n", "\n")
    
    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    # If there are no double newlines, fallback to single newlines
    if len(paragraphs) <= 1:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        
    chunks = []
    current_chunk = []
    current_length = 0
    
    for p in paragraphs:
        # If a single paragraph is larger than chunk_size, split it into sentences
        if len(p) > chunk_size:
            # Simple sentence splitting regex
            sentences = re.split(r'(?<=[.!?])\s+', p)
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                if current_length + len(s) <= chunk_size:
                    current_chunk.append(s)
                    current_length += len(s) + 1 # +1 for space
                else:
                    if current_chunk:
                        chunks.append(" ".join(current_chunk))
                    current_chunk = [s]
                    current_length = len(s)
        else:
            if current_length + len(p) <= chunk_size:
                current_chunk.append(p)
                current_length += len(p) + 2 # +2 for \n\n
            else:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk) if "\n\n" in text else "\n".join(current_chunk))
                current_chunk = [p]
                current_length = len(p)
                
    if current_chunk:
        chunks.append("\n\n".join(current_chunk) if "\n\n" in text else "\n".join(current_chunk))
        
    # If chunks are still empty or somehow sparse, fallback to a safe word-boundary window
    if not chunks:
        words = text.split()
        current_words = []
        current_len = 0
        for w in words:
            if current_len + len(w) <= chunk_size:
                current_words.append(w)
                current_len += len(w) + 1
            else:
                if current_words:
                    chunks.append(" ".join(current_words))
                # Add overlap of ~20 words if possible
                overlap_words = current_words[-20:] if len(current_words) > 20 else []
                current_words = overlap_words + [w]
                current_len = sum(len(x) + 1 for x in current_words)
        if current_words:
            chunks.append(" ".join(current_words))
            
    return chunks

def index_document(filename: str, text_lines: list, suggestions: dict) -> bool:
    """
    Chunks document text, generates vector embeddings, and inserts 
    them into Qdrant collection with rich metadata.
    """
    client = get_qdrant_client()
    model = get_embedding_model()
    
    if client is None or model is None:
        logger.warning("Vector DB or Embedding model is offline. Skipping indexing.")
        return False
        
    # Pre-merge OCR text lines into clean coherent paragraphs joined with double newlines
    from backend.parser_heuristics import merge_ocr_lines_to_paragraphs
    paragraphs = merge_ocr_lines_to_paragraphs(text_lines)
    full_text = "\n\n".join(paragraphs)
    chunks = chunk_text(full_text)
    
    if not chunks:
        logger.warning(f"No text extracted to index for {filename}")
        return False

    try:
        # Generate embeddings in batch for all chunks
        logger.info(f"Generating embeddings for {len(chunks)} chunks of document: {filename}")
        embeddings = list(model.embed(chunks))
        
        points = []
        for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            point_id = hash(f"{filename}_{idx}") & 0xFFFFFFFFFFFFFFFF  # 64-bit int ID
            
            # Metadata payload to assist filters and comparative math evaluation!
            payload = {
                "filename": filename,
                "chunk_id": idx,
                "text": chunk,
                "case_type": suggestions.get("case_type", "injury"),
                "name": suggestions.get("name", ""),
                "father_name": suggestions.get("father_name", ""),
                "date_of_birth": suggestions.get("date_of_birth", ""),
                "date_of_accident": suggestions.get("date_of_accident", ""),
                "age": suggestions.get("age", ""),
                "monthly_income": suggestions.get("monthly_income", ""),
                "disability": suggestions.get("disability", ""),
                "dependents": suggestions.get("dependents", ""),
                "marital_status": suggestions.get("marital_status", "married"),
                # Estimated award amount can be parsed from heuristics or fallback logic
                "award_amount": suggestions.get("award_amount", "")
            }
            
            # Convert numpy array to float list for Qdrant compatibility
            points.append(PointStruct(
                id=point_id,
                vector=list(vector),
                payload=payload
            ))
            
        # Upsert batch into Qdrant
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        logger.info(f"Indexed {len(chunks)} points for document '{filename}' in Qdrant successfully!")
        return True
    except Exception as e:
        logger.error(f"Error during Qdrant indexing: {str(e)}")
        return False

# ======================================================
# SEMANTIC QUERY SEARCH
# ======================================================

def semantic_search(query: str, limit: int = 5, case_type_filter: str = None) -> list:
    """
    Performs semantic vector search across all indexed PDFs.
    Optionally filters by case type ('injury' or 'death').
    """
    client = get_qdrant_client()
    model = get_embedding_model()
    
    if client is None or model is None:
        logger.warning("Vector DB or Embedding model is offline. Returning empty search results.")
        return []
        
    try:
        # Embed query text
        query_vector = list(next(model.embed([query])))
        
        # Build filter if case_type is specified
        search_filter = None
        if case_type_filter:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="case_type",
                        match=MatchValue(value=case_type_filter)
                    )
                ]
            )
            
        # Execute vector search
        search_results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=limit
        )
        
        # Format results
        formatted_results = []
        for res in search_results:
            formatted_results.append({
                "id": res.id,
                "score": round(res.score, 4),
                "text": res.payload.get("text", ""),
                "filename": res.payload.get("filename", ""),
                "metadata": {
                    "case_type": res.payload.get("case_type", ""),
                    "name": res.payload.get("name", ""),
                    "age": res.payload.get("age", ""),
                    "monthly_income": res.payload.get("monthly_income", ""),
                    "disability": res.payload.get("disability", ""),
                    "award_amount": res.payload.get("award_amount", "")
                }
            })
            
        return formatted_results
    except Exception as e:
        logger.error(f"Error during semantic vector search: {str(e)}")
        return []
