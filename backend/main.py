import os
import sys
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MainApp")

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.calculator import router as calculator_router, CompensationRequest
from backend.ocr import router as ocr_router
from backend.vector_db import semantic_search, get_qdrant_client, VECTOR_DB_INITIALIZED
from backend.evaluator import evaluate_compensation_precedents

app = FastAPI(
    title="Compensation Calculator & Centralized Qdrant Vector DB",
    description="Enterprise motor claims compensation dashboard with local Qdrant database indexing, batch PDF processing, and AI Legal Precedents Assistant.",
    version="2.0.0"
)

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing Compensation Calculator API startup sequence...")
    try:
        # Validate Ollama setup and model availability
        from backend.llm_client import validate_ollama_setup
        validate_ollama_setup()
        
        # Initialize Qdrant Client and collection safety dynamically
        get_qdrant_client()
    except Exception as e:
        logger.error(f"Startup check failed: {str(e)}")

    # Warm up PaddleOCR — isolated so failure never blocks Ollama/Qdrant
    try:
        logger.info("Warming up PaddleOCR singleton...")
        from backend.ocr import get_ocr_instance
        await asyncio.to_thread(get_ocr_instance)
        logger.info("PaddleOCR warm-up complete.")
    except Exception as e:
        logger.error(f"PaddleOCR warm-up failed (non-fatal): {str(e)}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# PYDANTIC SCHEMAS FOR CHAT & EVALUATIONS
# ======================================================

class ChatRequest(BaseModel):
    message: str
    case_type: str = "all"  # 'injury', 'death', or 'all'

class EvaluateRequest(BaseModel):
    params: dict
    calculated_amount: float

# ======================================================
# API ENDPOINTS
# ======================================================

app.include_router(calculator_router, prefix="/api/calculate", tags=["Calculation"])
app.include_router(ocr_router, prefix="/api/ocr", tags=["OCR"])

@app.get("/api/health")
async def health_check():
    """Returns server connection stats for Qdrant and Ollama embeddings!"""
    client = get_qdrant_client()
    from backend.vector_db import QDRANT_URL
    from config.llm import LLM_API_ENDPOINT, LLM_MODEL_NAME
    return {
        "status": "healthy",
        "message": "Compensation Calculator Server is running!",
        "qdrant_url": QDRANT_URL,
        "ollama_url": LLM_API_ENDPOINT,
        "embedding_model": "nomic-embed-text",
        "llm_model": LLM_MODEL_NAME,
        "vector_db": "online" if VECTOR_DB_INITIALIZED else "offline"
    }

@app.post("/api/search/chat")
async def legal_ai_chat(request: ChatRequest):
    """
    Receives user query, runs a semantic vector search across 
    100+ indexed PDF documents in Qdrant, and returns matching precedents 
    and summaries.
    """
    try:
        case_filter = None if request.case_type == "all" else request.case_type
        
        # 1. Perform semantic search
        logger_results = semantic_search(request.message, limit=3, case_type_filter=case_filter)
        
        if not logger_results:
            # Fallback chat response if Qdrant is empty
            return {
                "response": "Hello! I am your AI Legal Assistant. The Qdrant centralized database is connected and is awaiting PDF document uploads to learn from precedents.\n\nOnce you drop legal petitions, judgments, or prayers in the **PDF Library**, they will be automatically indexed, and I can semantically answer specific profile questions (e.g. searching by age, income, and disability) and retrieve precedents!",
                "precedents": []
            }
            
        # 2. Compile matches into a highly professional response
        response_text = f"Based on your query **\"{request.message}\"**, I searched the centralized Qdrant vector database and retrieved the most relevant precedent cases:\n\n"
        
        for idx, match in enumerate(logger_results):
            meta = match["metadata"]
            name = meta.get("name", "Unnamed Claimant")
            filename = match["filename"]
            score = match["score"]
            award_amount = meta.get("award_amount", "")
            
            response_text += f"{idx+1}. **{name}** (Precedent file: *{filename}*, Semantic Match: {score*100:.1f}%)\n"
            response_text += f"   - *Case Parameters:* Age {meta.get('age', 'N/A')} | Income Rs. {meta.get('monthly_income', 'N/A')}/pm"
            if meta.get("case_type") == "injury":
                response_text += f" | Disability {meta.get('disability', 'N/A')}%"
            if award_amount:
                response_text += f" | **Award Amount: Rs. {int(float(award_amount)):,}**"
            response_text += f"\n   - *Key Extract:* \"...{match['text'].strip()}...\"\n\n"
            
        response_text += "\nThese matching judgments can be applied immediately as defensible courtroom precedents. Let me know if you would like me to compile the formal claim brief or run a comparative mathematical benchmarking evaluation!"
        
        return {
            "response": response_text,
            "precedents": logger_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Legal chat error: {str(e)}")

@app.post("/api/search/evaluate")
async def evaluate_precedents(request: EvaluateRequest):
    """
    Benchmarks the math engine's calculated sum against semantic matched Qdrant precedents.
    """
    try:
        evaluation = evaluate_compensation_precedents(request.params, request.calculated_amount)
        return {
            "success": True,
            "evaluation": evaluation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparative evaluation failed: {str(e)}")

class PDFChatRequest(BaseModel):
    question: str = None
    message: str = None  # Backwards compatibility
    filename: str = None  # if provided, chats strictly with this PDF
    case_type: str = "all"  # 'injury', 'death', or 'all'
    
    # Validation context fields
    ocr_text: str = None
    parsed_fields: dict = None
    calculator_result: dict = None
    is_justify: bool = False

@app.post("/api/chat/pdf")
async def chat_with_pdf(request: PDFChatRequest):
    """
    RAG PDF Assistant: retrieves semantic chunks from Qdrant 
    (optionally filtered strictly by filename for a single PDF Q&A)
    and sends the constructed prompt to the configured LLM.
    """
    try:
        import json
        question_str = request.question or request.message
        if not question_str:
            raise HTTPException(status_code=400, detail="Missing 'question' or 'message' field.")
            
        case_filter = None if request.case_type == "all" else request.case_type
        
        # Determine filename filter
        filename_filter = request.filename
        if filename_filter == "all" or filename_filter == "":
            filename_filter = None

        # 1. Perform semantic vector search using the RAG helper
        from backend.vector_db import semantic_search_rag
        search_results = semantic_search_rag(
            query=question_str, 
            limit=5, 
            filename_filter=filename_filter
        )
        
        # 2. Construct context from retrieved points
        context_blocks = []
        precedents = []
        for idx, res in enumerate(search_results):
            text_block = res.get("text", "").strip()
            filename = res.get("filename", "unknown")
            context_blocks.append(f"[Context {idx+1} from {filename}]:\n{text_block}")
            
            precedents.append({
                "filename": filename,
                "score": res.get("score"),
                "text": text_block,
                "metadata": res.get("metadata", {})
            })
            
        retrieved_chunks = "\n\n".join(context_blocks)
        
        # 3. Incorporate Workstation Context (Phase 8 state integration)
        chunks_combined = retrieved_chunks
        workstation_blocks = []
        if request.ocr_text:
            workstation_blocks.append(f"[Current PDF Workstation OCR Text]:\n{request.ocr_text[:8000]}")
        if request.parsed_fields:
            workstation_blocks.append(f"[Current PDF Workstation Parsed Fields]:\n{json.dumps(request.parsed_fields, indent=2)}")
        if request.calculator_result:
            workstation_blocks.append(f"[Current Deterministic Calculator Math Output]:\n{json.dumps(request.calculator_result, indent=2)}")
        
        if workstation_blocks:
            chunks_combined = "\n\n".join(workstation_blocks) + "\n\n=== RETRIEVED PRECEDENTS ===\n\n" + chunks_combined
            
        # 4. Construct System Prompt & User Prompt strictly following grounding and safety boundaries

        # Justify Compensation mode
        # Build explicit case facts summary for justify mode
        case_facts_summary = ""
        if request.is_justify:
            pf = request.parsed_fields or {}
            cr = request.calculator_result or {}
            case_facts_summary = (
                f"\n=== EXACT CASE PARAMETERS FROM WORKSTATION ===\n"
                f"Claimant: {pf.get('name', 'Unknown')}\n"
                f"Age: {pf.get('age', 'Unknown')} years\n"
                f"Monthly Income used: Rs. {pf.get('monthly_income', 'Unknown')}\n"
                f"Disability: {pf.get('disability', pf.get('disability_percent', 'Unknown'))}%\n"
                f"Case Type: {pf.get('case_type', 'Unknown')}\n"
                f"Award Amount from PDF: Rs. {pf.get('award_amount', 'Unknown')}\n"
                f"Calculator Final Amount: Rs. {cr.get('final_amount', 'Unknown')}\n"
                f"Calculator Loss of Income: Rs. {cr.get('loss_of_income', cr.get('future_income_loss', 'Unknown'))}\n"
                f"Calculator Medical: Rs. {cr.get('medical_expenses', 'Unknown')}\n"
                f"Calculator Pain & Suffering: Rs. {cr.get('pain_and_suffering', 'Unknown')}\n"
                f"Multiplier used: {cr.get('multiplier', 'Unknown')}\n"
                f"===\n"
                f"CRITICAL: Use ONLY these exact figures. DO NOT invent or estimate any numbers.\n"
            )

        justify_block = ""
        if request.is_justify:
            question_str = (
                "Analyse this motor accident compensation case and provide a clear, brief, structured "
                "justification of whether the tribunal awarded compensation is adequate, excessive, or deficient. "
                "Base your analysis on: (1) facts of the accident and injuries, "
                "(2) grounds of appeal raised by the appellant, (3) prayer/relief claimed versus awarded, "
                "(4) each compensation head awarded versus calculator estimate, "
                "(5) any legal provisions or precedents cited in the document."
            )
            justify_block = (
                "\n=== JUSTIFY COMPENSATION - DEEP REASONING INSTRUCTIONS ===\n"
                "The user wants to understand WHY the compensation is under/over/adequate - not just THAT it is.\n\n"
                "For EACH compensation head you MUST answer:\n"
                "  (a) What amount was awarded?\n"
                "  (b) What was the SPECIFIC REASON the tribunal fixed it at that amount?\n"
                "  (e.g. income capped at minimum wage because no salary slip produced,\n"
                "  disability calculated limb-specific not whole-body,\n"
                "  multiplier fixed by age group per Sarla Verma,\n"
                "  medical bills partially rejected because duplicate receipts)\n"
                "  (c) Is it adequate/low/high compared to the calculator estimate and why?\n\n"
                "CRITICAL RULES:\n"
                "- DO NOT say the amount is low without explaining the tribunal's specific reason.\n"
                "- DO NOT compare against original claimed amount - compare only against calculator estimate.\n"
                "- Identify WHO filed the appeal - insurance company or claimant - and frame verdict accordingly.\n"
                "- Reference actual facts: income figures, disability %, multiplier used, evidence accepted/rejected.\n\n"
                "FORMAT YOUR RESPONSE EXACTLY AS:\n\n"
                "**Who Filed the Appeal:** [Claimant seeking enhancement / Insurance company seeking reduction]\n\n"
                "**Overall Verdict:** [ADEQUATE / UNDER-COMPENSATED / OVER-COMPENSATED] - [one sentence]\n\n"
                "**Head-wise Analysis:**\n"
                "- Medical Expenses: Rs.[amount] -> [adequate/low/high]\n"
                "  Why: [specific reason - bills accepted/rejected, what evidence]\n"
                "- Loss of Income: Rs.[amount] -> [adequate/low/high]\n"
                "  Why: [income figure used, multiplier applied, disability % and why tribunal chose these]\n"
                "- Pain & Suffering: Rs.[amount] -> [adequate/low/high]\n"
                "  Why: [specific reason]\n"
                "- Transport/Diet/Attender: Rs.[amount] -> [adequate/low/high]\n"
                "  Why: [specific reason - receipts produced or not]\n\n"
                "**Root Causes of Under/Over Compensation:**\n"
                "[3-5 bullets, each one specific root cause with evidence or rule behind it]\n\n"
                "**Key Legal Provisions & Precedents Used:**\n"
                "[Actual sections, acts, case citations from the document]\n\n"
                "DO NOT invent facts. Only use what is in the document context.\n"
            )

        user_prompt = (
            "You are a Motor Accident Claims Tribunal legal assistant.\n\n"
            "=== STRICTOR GROUNDING INSTRUCTIONS ===\n"
            "1. Use ONLY the supplied context (Retrieved Precedents and active Workstation details).\n"
            "2. Do NOT invent or hallucinate legal facts, precedents, or claims metrics.\n"
            "3. If the context does not contain the answer, clearly state that the information is missing.\n\n"
            "=== NEW COMPENSATION DATA MODEL & PRIORITY RULES ===\n"
            "Maintain separate concepts for the following compensation values and NEVER merge, mix, or overwrite them:\n"
            "- awarded_compensation: Amount awarded by the Tribunal/Court (extracted from PDF). E.g. 'Amount Awarded Rs.' indicates this.\n"
            "- claimed_compensation: Amount originally claimed (extracted from PDF). E.g. 'Claim before Tribunal' indicates this.\n"
            "- enhancement_sought: Additional amount requested in appeal (extracted from PDF). E.g. 'Appeal valued at' or 'Enhancement sought' indicates this.\n"
            "- calculated_compensation: Amount computed by the deterministic calculator (supplied in the active workstation context under [Current Deterministic Calculator Math Output]).\n\n"
            "If the PDF contains a tribunal award, use awarded_compensation first. Do NOT replace it with calculated_compensation.\n"
            "The Tribunal award is a judicial fact, whereas the calculator output is a computed estimate. Never overwrite judicially awarded compensation with calculator output.\n\n"
            "=== FORBIDDEN BEHAVIORS ===\n"
            "- NEVER say: 'Calculated amount is the source of truth'.\n"
            "- NEVER say: 'The deterministic calculator output supplied in the context is the absolute single source of truth' or 'the mathematical engine remains the ultimate source of truth'.\n"
            "- NEVER say: 'Compensation amount is ₹X' (only one figure) when multiple compensation figures exist.\n"
            "- NEVER overwrite judicially awarded compensation with calculator output.\n\n"
            "=== CHATBOT RESPONSE RULES ===\n"
            "When the user asks 'What is the compensation amount?' or questions about compensation, or when multiple compensation figures exist, you MUST separate the figures. NEVER answer with only one figure. Instead, respond strictly using the following REQUIRED RESPONSE FORMAT:\n\n"
            "According to the PDF (Judicial Record)\n\n"
            "Awarded Compensation:\n"
            "₹[awarded_compensation]\n\n"
            "Claim Amount:\n"
            "₹[claimed_compensation]\n\n"
            "Enhancement Sought:\n"
            "₹[enhancement_sought]\n\n\n"
            "According to the Compensation Calculator\n\n"
            "Calculated Compensation:\n"
            "₹[calculated_compensation]\n\n\n"
            "Comparison\n\n"
            "Difference:\n"
            "₹[Difference between Calculated Compensation and Awarded Compensation, calculated as calculated_compensation minus awarded_compensation]\n\n"
            "The calculator result is based on the currently populated fields and serves as an analytical estimate. The judicially awarded compensation remains ₹[awarded_compensation] unless modified by a court order.\n\n"
            "=== MATHEMATICAL INTEGRITY RULES ===\n"
            "- Under no circumstances should you compute, recalculate, or override mathematical values, multipliers, or final compensation totals.\n"
            "- If the user asks you to recalculate compensation, apply different multiplier figures, or alter prospects, explicitly instruct them to update the workstation parameters in the left-hand panel.\n\n"
            f"{case_facts_summary}"
            f"{justify_block}"
            f"Context:\n{chunks_combined}\n\n"
            f"Question:\n{question_str}"
        )
        
        # 5. Generate LLM Response using configured provider (Ollama Qwen2.5:14b)
        from backend.llm_client import generate_response
        ai_response = generate_response(user_prompt)
        
        return {
            "response": ai_response,
            "precedents": precedents
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Chat failed: {str(e)}")

@app.get("/api/qdrant/points")
async def get_qdrant_points():
    """
    Returns collection stats and points from local Qdrant database 
    for visual rendering in the embedded dashboard.
    """
    try:
        from backend.vector_db import get_qdrant_client, COLLECTION_NAME
        client = get_qdrant_client()
        if client is None:
            return {
                "success": False,
                "message": "Qdrant database is currently offline or uninitialized.",
                "collection_name": COLLECTION_NAME,
                "points_count": 0,
                "points": []
            }
            
        try:
            info = client.get_collection(COLLECTION_NAME)
            points_count = info.points_count
            status = info.status
            distance = info.config.params.vectors.distance
            if hasattr(distance, 'value'):
                distance = distance.value
            vector_size = info.config.params.vectors.size
        except Exception as e:
            return {
                "success": True,
                "message": f"Collection not loaded: {str(e)}",
                "collection_name": COLLECTION_NAME,
                "points_count": 0,
                "status": "not_created",
                "points": []
            }

        # Scroll points to get payloads (up to 100 points)
        points_list = []
        if points_count > 0:
            points, _ = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                with_payload=True,
                with_vectors=False
            )
            for p in points:
                points_list.append({
                    "id": p.id,
                    "payload": p.payload
                })

        return {
            "success": True,
            "collection_name": COLLECTION_NAME,
            "points_count": points_count,
            "status": str(status),
            "distance": str(distance),
            "vector_size": vector_size,
            "points": points_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load database points: {str(e)}")

@app.delete("/api/qdrant/document/{filename:path}")
async def delete_qdrant_document(filename: str):
    """
    Deletes all points associated with a specific filename from the Qdrant database,
    and removes that file from the BATCH_QUEUE to update the dashboard UI.
    """
    try:
        # 1. Delete points from Qdrant
        from backend.vector_db import delete_document
        deleted = delete_document(filename)
        
        # 2. Remove from BATCH_QUEUE
        from backend.ocr import BATCH_QUEUE
        to_delete = []
        for file_id, item in BATCH_QUEUE.items():
            if item.get("filename") == filename:
                to_delete.append(file_id)
        
        for file_id in to_delete:
            BATCH_QUEUE.pop(file_id, None)
            
        return {
            "success": deleted,
            "filename": filename,
            "removed_from_queue": len(to_delete) > 0,
            "message": f"Successfully deleted document '{filename}' from Qdrant and queue."
        }
    except Exception as e:
        logger.error(f"Error in delete_qdrant_document endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


# ======================================================
# STATIC FILES SERVING (MAPPED TO THE TABBED SPA)
# ======================================================

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    print(f"Warning: Frontend directory '{frontend_dir}' not found.")
