import os
import logging
import hashlib
import uuid
import time
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VectorDB")

# Centralized collection name for all legal precedents
COLLECTION_NAME = "legal_documents"

# Qdrant server connection URL (configured to run on server port 6335)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6335")

# Global lazy-initialized clients to prevent loading models during module imports
_qdrant_client = None
VECTOR_DB_INITIALIZED = False

def get_qdrant_client():
    global _qdrant_client, VECTOR_DB_INITIALIZED
    if _qdrant_client is None:
        try:
            logger.info(f"Initializing Qdrant client at URL: {QDRANT_URL}")
            
            # Connect to external Qdrant server (running on port 6335)
            _qdrant_client = QdrantClient(url=QDRANT_URL)
            
            # Create centralized legal_documents collection if it doesn't exist yet
            try:
                collection_info = _qdrant_client.get_collection(COLLECTION_NAME)
                
                # Retrieve vector dimension and distance metrics
                existing_size = collection_info.config.params.vectors.size
                existing_distance = collection_info.config.params.vectors.distance
                
                # Check distance compatibility
                distance_str = str(existing_distance).lower()
                is_cosine = "cosine" in distance_str
                
                # Dynamically fetch test embedding size
                test_emb = get_ollama_embedding("dimension_test_query")
                detected_dim = len(test_emb) if test_emb is not None else 768
                
                if existing_size == detected_dim and is_cosine:
                    logger.info(f"Existing Qdrant collection '{COLLECTION_NAME}' verified successfully (size={existing_size}, distance={existing_distance}). Reusing safely.")
                else:
                    logger.warning(
                        f"Existing collection '{COLLECTION_NAME}' layout mismatch. "
                        f"Expected size={detected_dim}, cosine distance. "
                        f"Found size={existing_size}, distance={existing_distance}. "
                        "Recreation bypassed to protect existing records. Please manually resolve."
                    )
            except Exception:
                logger.info(f"Collection '{COLLECTION_NAME}' not found. Creating a new one...")
                
                # Measure embedding dimension dynamically before creating
                test_emb = get_ollama_embedding("dimension_test_query")
                if test_emb is not None and len(test_emb) > 0:
                    detected_dim = len(test_emb)
                    logger.info(f"Ollama nomic-embed-text active. Dynamically detected embedding dimension: {detected_dim}")
                else:
                    detected_dim = 768
                    logger.warning(f"Ollama connection offline or embedding failed during startup. Defaulting collection dimension to: {detected_dim}")
                
                _qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=detected_dim, distance=Distance.COSINE)
                )
                logger.info(f"Collection '{COLLECTION_NAME}' created successfully with size={detected_dim}!")
            
            VECTOR_DB_INITIALIZED = True
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client at {QDRANT_URL}: {str(e)}")
            _qdrant_client = None
            VECTOR_DB_INITIALIZED = False
    return _qdrant_client

def get_ollama_embedding(text: str) -> list:
    """
    Fetches a 768-dimension vector embedding from local Ollama server
    using the 'nomic-embed-text' model.
    Returns None if embedding fails. Never returns a zero vector.
    """
    import urllib.request
    import json
    # Use config endpoint or default to local Ollama port
    from config.llm import LLM_API_ENDPOINT
    base_url = LLM_API_ENDPOINT if LLM_API_ENDPOINT else "http://localhost:11434"
    url = f"{base_url.rstrip('/')}/api/embeddings"
    payload = {
        "model": "nomic-embed-text",
        "prompt": text
    }
    try:
        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20.0) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            vector = res_json.get("embedding")
            if not vector or not isinstance(vector, list):
                raise ValueError("Embedding response is empty or invalid.")
            return vector
    except Exception as e:
        logger.error(f"Failed to fetch Ollama embedding: {str(e)}")
        return None

def get_embedding_model():
    """Backwards compatibility helper."""
    return True

# ======================================================
# CHUNKING & INDEXING PIPELINE
# ======================================================

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list:
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

def extract_paragraphs_with_page_info(text_lines: list) -> list:
    """
    Groups OCR lines into paragraph blocks and tracks their starting page numbers.
    Returns list of dict: [{"page": int, "text": str}]
    """
    import re
    from backend.parser_heuristics import clean_noisy_text
    
    current_page = 1
    page_paragraphs = []
    
    cleaned_items = []
    
    boilerplate_patterns = [
        r'^\s*presented\s+on\s*[:\-]',
        r'^\s*presented\s+by\s*[:\-]',
        r'^\s*registry\s+notice',
        r'^\s*in\s+the\s+court\s+of\b',
        r'^\s*adjudication\s+sheet\b',
        r'^\s*advocates?\s+for\b',
        r'^\s*date\s+of\s+stamping\b',
        r'^\s*stamps?\b',
        r'^\s*office\s+use\s+only\b',
        r'^\s*certified\s+copy\b',
        r'^\s*read\s+by\s*:',
        r'^\s*compared\s+by\s*:',
        r'^\s*typed\s+by\s*:'
    ]
    
    for line in text_lines:
        # Detect page separator
        page_match = re.match(r'^---\s*PAGE\s+(\d+)\s*---', line, re.IGNORECASE)
        if page_match:
            current_page = int(page_match.group(1))
            continue
            
        cleaned = clean_noisy_text(line)
        if not cleaned:
            continue
            
        # Ignore obvious procedural boilerplate lines
        if any(re.search(pat, cleaned.lower()) for pat in boilerplate_patterns):
            continue
            
        cleaned_items.append({"page": current_page, "text": cleaned})
        
    # Paragraph reconstruction while retaining page info
    merged_blocks = []
    current_block = []
    block_start_page = 1
    
    for item in cleaned_items:
        line = item["text"]
        p_num = item["page"]
        
        if not current_block:
            current_block = [line]
            block_start_page = p_num
            continue
            
        # Continuation heuristic
        last_line = current_block[-1]
        ends_with_terminal = last_line[-1] in ['.', '?', '!', ':']
        starts_with_heading = line.isupper() and len(line) > 5
        starts_with_bullet = bool(re.match(r'^\s*(?:\d+|[a-zA-Z])[\.\)\-\]]', line))
        
        if not ends_with_terminal and not starts_with_heading and not starts_with_bullet:
            if last_line.endswith('-'):
                current_block[-1] = last_line[:-1] + line
            else:
                current_block.append(line)
        else:
            merged_blocks.append({
                "page": block_start_page,
                "text": "\n".join(current_block) if "\n" in "\n".join(current_block) else " ".join(current_block)
            })
            current_block = [line]
            block_start_page = p_num
            
    if current_block:
        merged_blocks.append({
            "page": block_start_page,
            "text": "\n".join(current_block) if "\n" in "\n".join(current_block) else " ".join(current_block)
        })
        
    return merged_blocks

def chunk_paragraphs_with_page_info(page_paragraphs: list, chunk_size: int = 1000, overlap: int = 200) -> list:
    """
    Intelligently chunks paragraphs into 1000-char blocks while retaining starting page numbers.
    Returns list of dict: [{"page": int, "text": str}]
    """
    chunks_with_page = []
    
    current_chunk_text = []
    current_chunk_len = 0
    current_chunk_page = None
    
    for item in page_paragraphs:
        para_text = item["text"]
        para_page = item["page"]
        
        if current_chunk_page is None:
            current_chunk_page = para_page
            
        if current_chunk_len + len(para_text) <= chunk_size:
            current_chunk_text.append(para_text)
            current_chunk_len += len(para_text) + 2 # +2 for newline
        else:
            if current_chunk_text:
                chunks_with_page.append({
                    "page": current_chunk_page,
                    "text": "\n\n".join(current_chunk_text)
                })
            # Start new chunk with current paragraph
            current_chunk_text = [para_text]
            current_chunk_len = len(para_text)
            current_chunk_page = para_page
            
    if current_chunk_text:
        chunks_with_page.append({
            "page": current_chunk_page,
            "text": "\n\n".join(current_chunk_text)
        })
        
    return chunks_with_page

def index_document(filename: str, text_lines: list, suggestions: dict) -> bool:
    """
    Chunks document text, generates vector embeddings using Ollama nomic-embed-text, 
    and inserts them into Qdrant collection with rich metadata.
    Prevents duplicate uploads by matching file hashes.
    """
    client = get_qdrant_client()
    
    if client is None:
        logger.warning("Vector DB is offline. Skipping indexing.")
        return False
        
    # Calculate file MD5 hash of raw OCR text for duplicate protection
    full_raw_text = "\n".join(text_lines)
    file_hash = hashlib.md5(full_raw_text.encode("utf-8")).hexdigest()
    
    # Check for duplicate indexing
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        scroll_res, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(must=[
                FieldCondition(key="file_hash", match=MatchValue(value=file_hash))
            ]),
            limit=1
        )
        if scroll_res:
            logger.info(f"Duplicate Upload Protection: Document '{filename}' with hash '{file_hash}' is already indexed. Skipping indexing.")
            return True
    except Exception as e:
        logger.warning(f"Error checking duplicate indexing in Qdrant: {str(e)}")

    # Pre-merge OCR text lines into clean coherent paragraphs while tracking page numbers
    page_paragraphs = extract_paragraphs_with_page_info(text_lines)
    chunks_with_page = chunk_paragraphs_with_page_info(page_paragraphs, chunk_size=1000, overlap=200)
    
    if not chunks_with_page:
        logger.warning(f"No text extracted to index for {filename}")
        return False

    try:
        logger.info(f"Generating Ollama nomic-embed-text embeddings for {len(chunks_with_page)} chunks of: {filename}")
        
        points = []
        for idx, chunk_item in enumerate(chunks_with_page):
            chunk = chunk_item["text"]
            p_num = chunk_item["page"]
            
            vector = get_ollama_embedding(chunk)
            if vector is None:
                logger.error(f"Embedding generation failed for chunk {idx} of '{filename}'. Skipping this document indexing.")
                return False
                
            # MD5 hex of filename + chunk_index, converted to UUID string for stable point ID across restarts
            unique_str = f"{filename}_{idx}"
            point_id = str(uuid.UUID(hex=hashlib.md5(unique_str.encode("utf-8")).hexdigest()))
            
            # Rich metadata payload
            payload = {
                "filename": filename,
                "chunk_id": idx,
                "chunk_index": idx,
                "page_number": p_num,
                "file_hash": file_hash,
                "text": chunk,
                "case_type": suggestions.get("case_type", "injury"),
                "claimant": suggestions.get("name") or suggestions.get("claimant") or "",
                "respondent": suggestions.get("respondent", "Insurance Company / Respondent"),
                "document_type": suggestions.get("document_type", "Judgment"),
                "upload_date": suggestions.get("upload_date") or time.strftime("%d-%m-%Y"),
                # For backwards compatibility with evaluation models
                "name": suggestions.get("name", ""),
                "father_name": suggestions.get("father_name", ""),
                "age": suggestions.get("age", ""),
                "monthly_income": suggestions.get("monthly_income", ""),
                "disability": suggestions.get("disability", ""),
                "dependents": suggestions.get("dependents", ""),
                "marital_status": suggestions.get("marital_status", "married"),
                "award_amount": suggestions.get("award_amount", "")
            }
            
            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            ))
            
        # Upsert batch into Qdrant
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        logger.info(f"Indexed {len(chunks_with_page)} points for document '{filename}' in Qdrant successfully!")
        return True
    except Exception as e:
        logger.error(f"Error during Qdrant indexing: {str(e)}")
        return False

# ======================================================
# SEMANTIC QUERY SEARCH
# ======================================================

def semantic_search(query: str, limit: int = 5, case_type_filter: str = None, filename_filter: str = None) -> list:
    """
    Performs semantic vector search across all indexed PDFs.
    Optionally filters by case type ('injury' or 'death') and/or filename.
    """
    client = get_qdrant_client()
    
    if client is None:
        logger.warning("Vector DB is offline. Returning empty search results.")
        return []
        
    # Embed query text using Ollama
    query_vector = get_ollama_embedding(query)
    if query_vector is None:
        logger.warning(f"Failed to generate embedding for search query: '{query}'. Returning empty results.")
        return []
        
    try:
        # Build filter conditions
        must_conditions = []
        
        if case_type_filter:
            from qdrant_client.models import FieldCondition, MatchValue
            must_conditions.append(
                FieldCondition(
                    key="case_type",
                    match=MatchValue(value=case_type_filter)
                )
            )
            
        if filename_filter:
            from qdrant_client.models import FieldCondition, MatchValue
            must_conditions.append(
                FieldCondition(
                    key="filename",
                    match=MatchValue(value=filename_filter)
                )
            )
            
        search_filter = None
        if must_conditions:
            from qdrant_client.models import Filter
            search_filter = Filter(must=must_conditions)
            
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
                    "claimant": res.payload.get("claimant", ""),
                    "respondent": res.payload.get("respondent", ""),
                    "document_type": res.payload.get("document_type", ""),
                    "upload_date": res.payload.get("upload_date", ""),
                    "name": res.payload.get("name", ""),
                    "age": res.payload.get("age", ""),
                    "monthly_income": res.payload.get("monthly_income", ""),
                    "disability": res.payload.get("disability", ""),
                    "award_amount": res.payload.get("award_amount", ""),
                    "page_number": res.payload.get("page_number", 1),
                    "chunk_index": res.payload.get("chunk_index", 0),
                    "file_hash": res.payload.get("file_hash", "")
                }
            })
            
        return formatted_results
    except Exception as e:
        logger.error(f"Error during semantic vector search: {str(e)}")
        return []

def semantic_search_rag(query: str, limit: int = 5, filename_filter: str = None) -> list:
    """
    Retrieves relevant text chunks from the vector database.
    If filename_filter exists: search only that PDF
    Else: search entire library
    """
    logger.info(f"RAG search query='{query}', limit={limit}, filename_filter='{filename_filter}'")
    return semantic_search(query, limit=limit, filename_filter=filename_filter)
