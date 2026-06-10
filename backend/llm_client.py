# backend/llm_client.py
# import json
# import logging
# import urllib.request
# import urllib.error
# import re
# 
# from config.llm import LLM_PROVIDER, LLM_MODEL_NAME, LLM_API_KEY, LLM_API_ENDPOINT
# 
# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("LLMClient")
# 
# def validate_ollama_setup() -> dict:
#     """
#     Validates local Ollama endpoint connection and standard model availability (qwen2.5:14b & nomic-embed-text)
#     Returns connection and availability stats.
#     """
#     import urllib.request
#     import json
# 
#     base_url = LLM_API_ENDPOINT if LLM_API_ENDPOINT else "http://localhost:11434"
#     url = f"{base_url.rstrip('/')}/api/tags"
# 
#     stats = {
#         "connected": False,
#         "llm_model_available": False,
#         "embedding_model_available": False,
#         "models_found": []
#     }
# 
#     logger.info(f"Validating Ollama connection at {base_url}...")
#     try:
#         req = urllib.request.Request(url, method="GET")
#         with urllib.request.urlopen(req, timeout=5.0) as response:
#             res_json = json.loads(response.read().decode("utf-8"))
#             stats["connected"] = True
# 
#             # Parse models list
#             models = res_json.get("models", [])
#             for m in models:
#                 name = m.get("name", "")
#                 stats["models_found"].append(name)
# 
#             # Verify LLM Model and Embedding Model availability
#             for model_name in stats["models_found"]:
#                 if "qwen2.5:14b" in model_name or LLM_MODEL_NAME in model_name:
#                     stats["llm_model_available"] = True
#                 if "nomic-embed-text" in model_name:
#                     stats["embedding_model_available"] = True
# 
#             logger.info(f"Ollama server is ONLINE at {base_url}. Models found: {stats['models_found']}")
# 
#             if not stats["llm_model_available"]:
#                 logger.warning(f"Ollama model '{LLM_MODEL_NAME}' is missing! Please pull it: 'ollama pull {LLM_MODEL_NAME}'")
#             if not stats["embedding_model_available"]:
#                 logger.warning("Ollama embedding model 'nomic-embed-text' is missing! Please pull it: 'ollama pull nomic-embed-text'")
#     except Exception as e:
#         logger.error(f"Ollama startup connection failed at {base_url}: {str(e)}")
# 
#     return stats
# 
# def generate_response(prompt: str, system_instruction: str = None) -> str:
#     """
#     General completion helper that formats payload and makes HTTP request 
#     to the configured LLM provider (Gemini, Ollama, OpenAI, or Custom API).
#     """
#     logger.info(f"Generating LLM response using provider '{LLM_PROVIDER}', model '{LLM_MODEL_NAME}'")
# 
#     # Prepend system instruction to prompt for universal compatibility
#     final_prompt = prompt
#     if system_instruction:
#         final_prompt = f"System Instruction:\n{system_instruction}\n\nUser Question:\n{prompt}"
# 
#     try:
#         if LLM_PROVIDER == "gemini":
#             # Google Gemini REST Endpoint
#             url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL_NAME}:generateContent?key={LLM_API_KEY}"
#             headers = {"Content-Type": "application/json"}
# 
#             # Formulate Gemini Payload
#             payload = {
#                 "contents": [{
#                     "parts": [{
#                         "text": final_prompt
#                     }]
#                 }]
#             }
#             # Add native systemInstruction if v1beta supports it natively in headers/payload
#             if system_instruction:
#                 payload["systemInstruction"] = {
#                     "parts": [{
#                         "text": system_instruction
#                     }]
#                 }
#                 # Remove systemInstruction prefix from final_prompt to avoid redundancy
#                 payload["contents"][0]["parts"][0]["text"] = prompt
# 
#             req_body = json.dumps(payload).encode("utf-8")
# 
#         elif LLM_PROVIDER == "ollama":
#             # For Ollama, handle native /api/chat or OpenAI-compatible depending on path
#             if "v1" in LLM_API_ENDPOINT:
#                 url = f"{LLM_API_ENDPOINT.rstrip('/')}/chat/completions"
#                 messages = []
#                 if system_instruction:
#                     messages.append({"role": "system", "content": system_instruction})
#                 messages.append({"role": "user", "content": prompt})
#                 payload = {
#                     "model": LLM_MODEL_NAME,
#                     "messages": messages,
#                     "temperature": 0.2
#                 }
#             else:
#                 url = f"{LLM_API_ENDPOINT.rstrip('/')}/api/chat"
#                 messages = []
#                 if system_instruction:
#                     messages.append({"role": "system", "content": system_instruction})
#                 messages.append({"role": "user", "content": prompt})
#                 payload = {
#                     "model": LLM_MODEL_NAME,
#                     "messages": messages,
#                     "stream": False,
#                     "options": {
#                         "temperature": 0.2
#                     }
#                 }
#             headers = {"Content-Type": "application/json"}
#             req_body = json.dumps(payload).encode("utf-8")
# 
#         else:
#             # OpenAI / Custom API Compatible Endpoint
#             url = f"{LLM_API_ENDPOINT.rstrip('/')}/chat/completions"
#             headers = {
#                 "Content-Type": "application/json"
#             }
#             if LLM_API_KEY:
#                 headers["Authorization"] = f"Bearer {LLM_API_KEY}"
# 
#             messages = []
#             if system_instruction:
#                 messages.append({"role": "system", "content": system_instruction})
#             messages.append({"role": "user", "content": prompt})
# 
#             payload = {
#                 "model": LLM_MODEL_NAME,
#                 "messages": messages,
#                 "temperature": 0.2
#             }
#             req_body = json.dumps(payload).encode("utf-8")
# 
#         # Send REST API request
#         req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
#         with urllib.request.urlopen(req, timeout=30.0) as response:
#             res_body = response.read().decode("utf-8")
#             res_json = json.loads(res_body)
# 
#             # Parse response depending on provider schema
#             if LLM_PROVIDER == "gemini":
#                 candidates = res_json.get("candidates", [])
#                 if candidates:
#                     parts = candidates[0].get("content", {}).get("parts", [])
#                     if parts:
#                         return parts[0].get("text", "").strip()
#                 return ""
#             else:
#                 choices = res_json.get("choices", [])
#                 if choices:
#                     return choices[0].get("message", {}).get("content", "").strip()
#                 # Support native Ollama /api/chat response structure
#                 if "message" in res_json and "content" in res_json["message"]:
#                     return res_json["message"]["content"].strip()
#                 return ""
# 
#     except urllib.error.HTTPError as he:
#         err_msg = he.read().decode("utf-8") if he.fp else str(he)
#         logger.error(f"LLM API HTTP Error ({he.code}): {err_msg}")
#         return f"Error connecting to LLM server: {he.reason}"
#     except Exception as e:
#         logger.error(f"Failed to generate LLM response: {str(e)}")
#         return f"Error communicating with LLM client: {str(e)}"
# 
# def classify_case_type_by_ocr_text(ocr_text: str) -> str:
#     """
#     Scans the OCR text for explicit case type keywords.
#     Prioritizes strong OCR evidence for Injury or Death over LLM guess.
#     """
#     text_lower = ocr_text.lower()
# 
#     injury_keywords = [
#         "injury", "disability", "permanent disability", "partial disability", 
#         "bodily injury", "enhancement", "claimant injury"
#     ]
# 
#     death_keywords = [
#         "death", "deceased", "fatal", "died", "legal heirs", "widow", "death claim"
#     ]
# 
#     injury_count = 0
#     for kw in injury_keywords:
#         injury_count += text_lower.count(kw)
# 
#     death_count = 0
#     for kw in death_keywords:
#         death_count += text_lower.count(kw)
# 
#     logger.info(f"OCR case type keyword count: Injury = {injury_count}, Death = {death_count}")
# 
#     if injury_count > death_count and injury_count >= 1:
#         return "injury"
#     elif death_count > injury_count and death_count >= 1:
#         return "death"
#     elif injury_count == death_count and injury_count >= 1:
#         # Tie-breaker using high-weight keywords
#         injury_weight = 0
#         for kw in ["permanent disability", "partial disability", "bodily injury", "claimant injury"]:
#             injury_weight += text_lower.count(kw) * 2
# 
#         death_weight = 0
#         for kw in ["deceased", "legal heirs", "death claim", "widow"]:
#             death_weight += text_lower.count(kw) * 2
# 
#         if injury_weight > death_weight:
#             return "injury"
#         elif death_weight > injury_weight:
#             return "death"
# 
#     return None
# 
# def extract_smart_context_for_llm(raw_ocr_text: str) -> str:
#     """
#     Constructs a highly-concentrated extract of the OCR text for the LLM.
#     Includes the front pages (metadata) and any sections/pages containing 
#     key compensation keywords to ensure no numbers or parameters are lost.
#     """
#     if len(raw_ocr_text) <= 30000:
#         return raw_ocr_text
# 
#     # 1. Keep the first 12,000 characters (cause titles, claimant metadata, dates)
#     front_context = raw_ocr_text[:12000]
# 
#     # 2. Extract paragraphs/lines from the rest of the text that contain high-value terms
#     remainder_text = raw_ocr_text[12000:]
#     lines = remainder_text.split("\n")
# 
#     high_value_keywords = [
#         "compensation", "multiplier", "dependency", "consortium", 
#         "funeral", "monthly income", "disability", "earning", "quantum", 
#         "award", "rs.", "rupees", "attender", "medical", "pain"
#     ]
# 
#     selected_chunks = []
#     i = 0
#     n = len(lines)
#     while i < n:
#         line_lower = lines[i].lower()
#         if any(kw in line_lower for kw in high_value_keywords):
#             # Capture a small window around the hit
#             start = max(0, i - 1)
#             end = min(n, i + 3)
#             chunk = "\n".join(lines[start:end])
#             selected_chunks.append(chunk)
#             i = end # Skip past the captured window to avoid overlaps
#         else:
#             i += 1
# 
#     # Combine selected chunks, limiting them to a reasonable size (e.g. 25,000 characters)
#     selected_text = "\n\n... [Section Extract] ...\n\n".join(selected_chunks)
#     if len(selected_text) > 25000:
#         selected_text = selected_text[:25000] + "\n\n... [Truncated due to size] ..."
# 
#     # Also grab the absolute end of the PDF (often contains final award totals/orders)
#     end_context = raw_ocr_text[-8000:]
# 
#     smart_text = (
#         f"{front_context}\n\n"
#         f"=== RELEVANT QUANTUM & COMPENSATION EXTRACTS ===\n\n"
#         f"{selected_text}\n\n"
#         f"=== FINAL JUDGMENT AWARD SECTIONS ===\n\n"
#         f"{end_context}"
#     )
# 
#     return smart_text
# 
# def ai_data_recovery(raw_ocr_text: str) -> dict:
#     """
#     Invokes the LLM to parse raw OCR'd text and extract key legal claims fields.
#     Acts as a premium data recovery layer when heuristics are incomplete.
#     """
#     system_instruction = (
#         "You are an expert legal data extraction engine specializing in Motor Accident Claims Tribunal (MACT) judgments.\n"
#         "Your task is to analyze the provided raw OCR text and extract key compensation parameters.\n"
#         "Return ONLY a clean, valid JSON object where every key maps to a sub-object containing 'value' and 'confidence' (float from 0.0 to 1.0 representing your model confidence in the extraction). Use null for 'value' and 0.0 for 'confidence' if the field is not present or cannot be determined.\n\n"
#         "Strictly extract these exact fields:\n"
#         "Common Fields:\n"
#         "- case_type (string: 'injury' or 'death')\n"
#         "- claimant_name (string)\n"
#         "- father_name (string)\n"
#         "- spouse_name (string)\n"
#         "- dob (string, formatted as DD-MM-YYYY)\n"
#         "- age (integer)\n"
#         "- occupation (string)\n"
#         "- monthly_income (float)\n"
#         "- dependents (integer)\n"
#         "- marital_status (string: 'married' or 'single')\n"
#         "- accident_date (string, formatted as DD-MM-YYYY)\n"
#         "- accident_place (string)\n\n"
#         "Injury Heads:\n"
#         "- medical_expenses (float)\n"
#         "- future_medical_expenses (float)\n"
#         "- pain_and_suffering (float)\n"
#         "- transportation (float)\n"
#         "- special_diet (float)\n"
#         "- attender_charges (float)\n"
#         "- loss_of_income (float)\n"
#         "- disability_percentage (float)\n\n"
#         "Death Heads:\n"
#         "- loss_of_consortium (float)\n"
#         "- funeral_expenses (float)\n"
#         "- loss_of_estate (float)\n\n"
#         "Example Output Format:\n"
#         "{\n"
#         "  \"case_type\": {\"value\": \"injury\", \"confidence\": 0.95},\n"
#         "  \"claimant_name\": {\"value\": \"John Doe\", \"confidence\": 0.98},\n"
#         "  \"medical_expenses\": {\"value\": 50000, \"confidence\": 0.93},\n"
#         "  \"pain_and_suffering\": {\"value\": 25000, \"confidence\": 0.81}\n"
#         "}\n\n"
#         "Do NOT write any preamble, explanation, markdown fences, or comments. Return only the JSON object."
#     )
# 
#     # We pass a highly-concentrated extract of the OCR text to ensure no parameters or numbers are lost
#     smart_text = extract_smart_context_for_llm(raw_ocr_text)
#     prompt = f"Analyze this court judgment extract and recover the fields:\n\n{smart_text}"
# 
#     response = generate_response(prompt, system_instruction)
# 
#     try:
#         # Extract JSON block using regex if LLM surrounds it with markdown tags
#         json_match = re.search(r"\{.*\}", response, re.DOTALL)
#         if json_match:
#             raw_data = json.loads(json_match.group(0))
#         else:
#             raw_data = json.loads(response)
# 
#         data = {}
#         confidence_scores = {}
# 
#         for key, field_obj in raw_data.items():
#             if isinstance(field_obj, dict) and "value" in field_obj:
#                 val = field_obj.get("value")
#                 conf = field_obj.get("confidence", 1.0)
#             else:
#                 val = field_obj
#                 conf = 1.0 if val is not None else 0.0
# 
#             data[key] = val
#             confidence_scores[key] = {"confidence": conf}
# 
#         # Case type lock and deterministic precedence logic (Part 2)
#         ocr_evidence_case = classify_case_type_by_ocr_text(raw_ocr_text)
#         if ocr_evidence_case:
#             case_type_val = ocr_evidence_case
#             case_type_conf = 1.0
#             ocr_evidence_str = ocr_evidence_case.upper()
#             logger.info(f"Deterministic OCR Case Type Match overrides LLM: {case_type_val.upper()}")
#         else:
#             llm_case_obj = raw_data.get("case_type", {})
#             if isinstance(llm_case_obj, dict):
#                 case_type_val = llm_case_obj.get("value")
#                 case_type_conf = llm_case_obj.get("confidence", 0.0)
#             else:
#                 case_type_val = llm_case_obj
#                 case_type_conf = 1.0 if case_type_val else 0.0
# 
#             if not case_type_val or case_type_val not in ["injury", "death"]:
#                 case_type_val = "death"
#                 case_type_conf = 0.5
#             ocr_evidence_str = "UNCLEAR"
# 
#         data["case_type"] = case_type_val
#         confidence_scores["case_type"] = {"confidence": case_type_conf}
# 
#         # Backward-compatible aliases for format_suggestions_for_calculator mapping
#         if "claimant_name" in data and data["claimant_name"]:
#             data["name"] = data["claimant_name"]
#             data["injured_name"] = data["claimant_name"]
#             data["deceased_name"] = data["claimant_name"]
#             confidence_scores["name"] = confidence_scores["claimant_name"]
#             confidence_scores["injured_name"] = confidence_scores["claimant_name"]
#             confidence_scores["deceased_name"] = confidence_scores["claimant_name"]
# 
#         if "accident_date" in data and data["accident_date"]:
#             data["date_of_accident"] = data["accident_date"]
#             confidence_scores["date_of_accident"] = confidence_scores["accident_date"]
# 
#         if "dob" in data and data["dob"]:
#             data["date_of_birth"] = data["dob"]
#             confidence_scores["date_of_birth"] = confidence_scores["dob"]
# 
#         if "accident_place" in data and data["accident_place"]:
#             data["place_of_accident"] = data["accident_place"]
#             confidence_scores["place_of_accident"] = confidence_scores["accident_place"]
# 
#         if "disability_percentage" in data and data["disability_percentage"] is not None:
#             data["disability"] = data["disability_percentage"]
#             confidence_scores["disability"] = confidence_scores["disability_percentage"]
# 
#         if "loss_of_consortium" in data and data["loss_of_consortium"] is not None:
#             data["consortium"] = data["loss_of_consortium"]
#             confidence_scores["consortium"] = confidence_scores["loss_of_consortium"]
# 
#         data["confidence_scores"] = confidence_scores
#         data["ocr_evidence_case"] = ocr_evidence_str
# 
#         logger.info(f"AI Data Recovery successful with structured confidences: {list(data.keys())}")
#         return data
#     except Exception as e:
#         logger.error(f"Failed to parse AI Data Recovery JSON: {str(e)}. Raw response: {response}")
#         raise e
# 



# backend/llm_client.py
# backend/llm_client.py
import json
import logging
import urllib.request
import urllib.error
import re

from config.llm import LLM_PROVIDER, LLM_MODEL_NAME, LLM_API_KEY, LLM_API_ENDPOINT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMClient")


def validate_ollama_setup() -> dict:
    import urllib.request
    import json
    base_url = LLM_API_ENDPOINT if LLM_API_ENDPOINT else "http://localhost:11434"
    url = f"{base_url.rstrip('/')}/api/tags"
    stats = {
        "connected": False,
        "llm_model_available": False,
        "embedding_model_available": False,
        "models_found": []
    }
    logger.info(f"Validating Ollama connection at {base_url}...")
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5.0) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            stats["connected"] = True
            
            # Parse models list
            models = res_json.get("models", [])
            for m in models:
                name = m.get("name", "")
                stats["models_found"].append(name)
                
            # Verify LLM Model and Embedding Model availability
            for model_name in stats["models_found"]:
                if "qwen2.5:14b" in model_name or LLM_MODEL_NAME in model_name:
                    stats["llm_model_available"] = True
                if "nomic-embed-text" in model_name:
                    stats["embedding_model_available"] = True
                    
            logger.info(f"Ollama server is ONLINE at {base_url}. Models found: {stats['models_found']}")
            if not stats["llm_model_available"]:
                logger.warning(f"Ollama model '{LLM_MODEL_NAME}' is missing!")
            if not stats["embedding_model_available"]:
                logger.warning("Ollama embedding model 'nomic-embed-text' is missing!")
    except Exception as e:
        logger.error(f"Ollama startup connection failed at {base_url}: {str(e)}")
    return stats

def generate_response(prompt: str, system_instruction: str = None) -> str:
    logger.info(f"Generating LLM response using provider '{LLM_PROVIDER}', model '{LLM_MODEL_NAME}'")
    final_prompt = prompt
    if system_instruction:
        final_prompt = f"System Instruction:\n{system_instruction}\n\nUser Question:\n{prompt}"
    try:
        if LLM_PROVIDER == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL_NAME}:generateContent?key={LLM_API_KEY}"
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": final_prompt}]}]}
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
                payload["contents"][0]["parts"][0]["text"] = prompt
            req_body = json.dumps(payload).encode("utf-8")
        elif LLM_PROVIDER == "ollama":
            if "v1" in LLM_API_ENDPOINT:
                url = f"{LLM_API_ENDPOINT.rstrip('/')}/chat/completions"
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                payload = {"model": LLM_MODEL_NAME, "messages": messages, "temperature": 0.2}
            else:
                url = f"{LLM_API_ENDPOINT.rstrip('/')}/api/chat"
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                payload = {"model": LLM_MODEL_NAME, "messages": messages, "stream": False, "options": {"temperature": 0.2}}
            headers = {"Content-Type": "application/json"}
            req_body = json.dumps(payload).encode("utf-8")
        else:
            url = f"{LLM_API_ENDPOINT.rstrip('/')}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if LLM_API_KEY:
                headers["Authorization"] = f"Bearer {LLM_API_KEY}"
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            payload = {"model": LLM_MODEL_NAME, "messages": messages, "temperature": 0.2}
            req_body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=300.0) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            if LLM_PROVIDER == "gemini":
                candidates = res_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                return ""
            else:
                choices = res_json.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
                if "message" in res_json and "content" in res_json["message"]:
                    return res_json["message"]["content"].strip()
                return ""
    except urllib.error.HTTPError as he:
        err_msg = he.read().decode("utf-8") if he.fp else str(he)
        logger.error(f"LLM API HTTP Error ({he.code}): {err_msg}")
        return f"Error connecting to LLM server: {he.reason}"
    except Exception as e:
        logger.error(f"Failed to generate LLM response: {str(e)}")
        return f"Error communicating with LLM client: {str(e)}"

def classify_case_type_by_ocr_text(ocr_text: str) -> str:
    text_lower = ocr_text.lower()
    injury_keywords = ["injury", "disability", "permanent disability", "partial disability", "bodily injury", "enhancement", "claimant injury"]
    death_keywords = ["death", "deceased", "fatal", "died", "legal heirs", "widow", "death claim"]
    injury_count = sum(text_lower.count(kw) for kw in injury_keywords)
    death_count = sum(text_lower.count(kw) for kw in death_keywords)
    logger.info(f"OCR case type keyword count: Injury = {injury_count}, Death = {death_count}")
    if injury_count > death_count and injury_count >= 1:
        return "injury"
    elif death_count > injury_count and death_count >= 1:
        return "death"
    elif injury_count == death_count and injury_count >= 1:
        injury_weight = sum(text_lower.count(kw) * 2 for kw in ["permanent disability", "partial disability", "bodily injury", "claimant injury"])
        death_weight = sum(text_lower.count(kw) * 2 for kw in ["deceased", "legal heirs", "death claim", "widow"])
        if injury_weight > death_weight:
            return "injury"
        elif death_weight > injury_weight:
            return "death"
    return None

def extract_smart_context_for_llm(raw_ocr_text: str) -> str:
    if len(raw_ocr_text) <= 30000:
        return raw_ocr_text
    front_context = raw_ocr_text[:12000]
    remainder_text = raw_ocr_text[12000:]
    lines = remainder_text.split("\n")
    high_value_keywords = [
        "compensation", "multiplier", "dependency", "consortium",
        "funeral", "monthly income", "disability", "earning", "quantum",
        "award", "rs.", "rupees", "attender", "medical", "pain",
        "future prospect", "interest", "loss of", "notional", "deduction"
    ]
    selected_chunks = []
    i = 0
    n = len(lines)
    while i < n:
        line_lower = lines[i].lower()
        if any(kw in line_lower for kw in high_value_keywords):
            start = max(0, i - 1)
            end = min(n, i + 3)
            chunk = "\n".join(lines[start:end])
            selected_chunks.append(chunk)
            i = end
        else:
            i += 1
    selected_text = "\n\n... [Section Extract] ...\n\n".join(selected_chunks)
    if len(selected_text) > 25000:
        selected_text = selected_text[:25000] + "\n\n... [Truncated] ..."
    end_context = raw_ocr_text[-8000:]
    return (
        f"{front_context}\n\n"
        f"=== RELEVANT QUANTUM & COMPENSATION EXTRACTS ===\n\n"
        f"{selected_text}\n\n"
        f"=== FINAL JUDGMENT AWARD SECTIONS ===\n\n"
        f"{end_context}"
    )

def ai_data_recovery(raw_ocr_text: str) -> dict:
    """
    Invokes the LLM to parse raw OCR text and extract ALL legal claims fields
    for both injury and death cases.
    """
    system_instruction = (
        "You are an expert legal data extraction engine specializing in Indian Motor Accident Claims Tribunal (MACT) judgments.\n"
        "Analyze the provided raw OCR text and extract ALL compensation parameters for both injury and death cases.\n"
        "Return ONLY a clean valid JSON object. Every key maps to {\"value\": ..., \"confidence\": 0.0-1.0}.\n"
        "Use null for value and 0.0 for confidence if a field is not found.\n"
        "Do NOT write preamble, explanation, markdown fences, or comments. Return only the JSON.\n\n"

        "Extract ALL of these fields:\n\n"

        "IDENTITY FIELDS:\n"
        "- case_type: 'injury' or 'death'\n"
        "- claimant_name: full name of claimant/petitioner\n"
        "- father_name: father or husband name\n"
        "- spouse_name: spouse name if mentioned\n"
        "- dob: date of birth as DD-MM-YYYY\n"
        "- age: integer age at time of accident\n"
        "- occupation: job/profession of claimant or deceased\n"
        "- monthly_income: monthly income as float (convert annual to monthly if needed; use notional if stated)\n"
        "- dependents: number of dependents as integer\n"
        "- marital_status: 'married', 'unmarried', or 'widowed'\n"
        "- accident_date: DD-MM-YYYY\n"
        "- accident_place: full location string\n"
        "- vehicle_number: vehicle registration number\n"
        "- insurance_company: name of insurance company\n"
        "- fir_number: FIR/complaint number\n"
        "- case_number: court case/petition number\n"
        "- court_name: name of the tribunal/court\n"
        "- judge_name: name of the judge\n"
        "- decision_date: date of judgment as DD-MM-YYYY\n\n"

        "INJURY CASE HEADS (fill for injury cases):\n"
        "- disability_percentage: float e.g. 35.0 (look for '35% disability', 'permanent disability 40%')\n"
        "- medical_expenses: float (bills paid for treatment)\n"
        "- future_medical_expenses: float\n"
        "- pain_and_suffering: float (also called 'pain and agony')\n"
        "- transportation: float (conveyance/transport charges)\n"
        "- special_diet: float\n"
        "- attender_charges: float (attendant/nursing charges)\n"
        "- loss_of_income: float (loss of earnings during treatment)\n"
        "- loss_of_amenities: float (loss of amenities of life)\n\n"

        "DEATH CASE HEADS (fill for death cases):\n"
        "- loss_of_dependency: float (main head — monthly income x multiplier x dependency ratio)\n"
        "- loss_of_consortium: float (spouse consortium, usually 40000-100000)\n"
        "- loss_of_estate: float (loss of estate of deceased)\n"
        "- funeral_expenses: float (funeral/obsequies expenses)\n"
        "- loss_of_love_affection: float (parental/filial consortium)\n\n"

        "CALCULATION PARAMETERS:\n"
        "- future_prospect: float percentage e.g. 25.0 or 40.0 (future prospects addition)\n"
        "- multiplier: integer from Sarla Verma table (based on age)\n"
        "- dependency_ratio: float e.g. 0.5 or 0.667 (deduction for personal expenses)\n"
        "- interest_rate: float e.g. 7.5 (rate of interest awarded)\n"
        "- total_compensation: float (total award amount)\n"
        "- award_amount: float (final amount awarded by court)\n\n"

        "RULES:\n"
        "1. monetary values as plain floats with no Rs/commas/symbols\n"
        "2. For monthly_income: if annual given divide by 12; if notional stated use that value\n"
        "3. disability_percentage: extract number from phrases like '40% permanent disability'\n"
        "4. multiplier: look for 'multiplier of 17' or Sarla Verma table references\n"
        "5. future_prospect: look for '25% future prospects' or '40% addition'\n"
        "6. For death cases always try to fill loss_of_dependency, funeral_expenses, loss_of_consortium\n"
        "7. confidence 0.95+ only when exact number found in text; 0.7-0.94 for inferred values\n"
    )

    smart_text = extract_smart_context_for_llm(raw_ocr_text)
    prompt = f"Analyze this MACT court judgment and extract all fields:\n\n{smart_text}"

    response = generate_response(prompt, system_instruction)

    try:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            raw_data = json.loads(json_match.group(0))
        else:
            raw_data = json.loads(response)

        data = {}
        confidence_scores = {}

        for key, field_obj in raw_data.items():
            if isinstance(field_obj, dict) and "value" in field_obj:
                val = field_obj.get("value")
                conf = field_obj.get("confidence", 1.0)
            else:
                val = field_obj
                conf = 1.0 if val is not None else 0.0
            data[key] = val
            confidence_scores[key] = {"confidence": conf}

        # ── Case type deterministic override ──────────────────────────────
        ocr_evidence_case = classify_case_type_by_ocr_text(raw_ocr_text)
        if ocr_evidence_case:
            case_type_val = ocr_evidence_case
            case_type_conf = 1.0
            ocr_evidence_str = ocr_evidence_case.upper()
            logger.info(f"Deterministic OCR Case Type overrides LLM: {case_type_val.upper()}")
        else:
            llm_case_obj = raw_data.get("case_type", {})
            if isinstance(llm_case_obj, dict):
                case_type_val = llm_case_obj.get("value")
                case_type_conf = llm_case_obj.get("confidence", 0.0)
            else:
                case_type_val = llm_case_obj
                case_type_conf = 1.0 if case_type_val else 0.0
            if not case_type_val or case_type_val not in ["injury", "death"]:
                case_type_val = "death"
                case_type_conf = 0.5
            ocr_evidence_str = "UNCLEAR"

        data["case_type"] = case_type_val
        confidence_scores["case_type"] = {"confidence": case_type_conf}

        # ── Aliases for calculator field name compatibility ────────────────
        aliases = [
            # (source_key, alias_key)
            ("claimant_name",        "name"),
            ("claimant_name",        "injured_name"),
            ("claimant_name",        "deceased_name"),
            ("accident_date",        "date_of_accident"),
            ("dob",                  "date_of_birth"),
            ("accident_place",       "place_of_accident"),
            ("disability_percentage","disability"),
            ("loss_of_consortium",   "consortium"),
            ("loss_of_dependency",   "dependency"),
            ("funeral_expenses",     "funeral"),
            ("loss_of_estate",       "estate"),
            ("loss_of_love_affection","love_affection"),
            ("loss_of_amenities",    "amenities"),
            ("future_prospect",      "future_prospects"),
            ("total_compensation",   "total_award"),
            ("award_amount",         "award"),
        ]
        for src, alias in aliases:
            if src in data and data[src] is not None:
                data[alias] = data[src]
                confidence_scores[alias] = confidence_scores.get(src, {"confidence": 0.8})

        data["confidence_scores"] = confidence_scores
        data["ocr_evidence_case"] = ocr_evidence_str

        logger.info(f"AI Data Recovery successful with structured confidences: {list(data.keys())}")
        return data

    except Exception as e:
        logger.error(f"Failed to parse AI Data Recovery JSON: {str(e)}. Raw response: {response}")
        raise e

