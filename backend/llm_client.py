# backend/llm_client.py
import json
import logging
import urllib.request
import urllib.error
import re

from config.llm import LLM_PROVIDER, LLM_MODEL_NAME, LLM_API_KEY, LLM_API_ENDPOINT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMClient")

def validate_ollama_setup() -> dict:
    """
    Validates local Ollama endpoint connection and standard model availability (qwen2.5:14b & nomic-embed-text)
    Returns connection and availability stats.
    """
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
                logger.warning(f"Ollama model '{LLM_MODEL_NAME}' is missing! Please pull it: 'ollama pull {LLM_MODEL_NAME}'")
            if not stats["embedding_model_available"]:
                logger.warning("Ollama embedding model 'nomic-embed-text' is missing! Please pull it: 'ollama pull nomic-embed-text'")
    except Exception as e:
        logger.error(f"Ollama startup connection failed at {base_url}: {str(e)}")
        
    return stats

def generate_response(prompt: str, system_instruction: str = None) -> str:
    """
    General completion helper that formats payload and makes HTTP request 
    to the configured LLM provider (Gemini, Ollama, OpenAI, or Custom API).
    """
    logger.info(f"Generating LLM response using provider '{LLM_PROVIDER}', model '{LLM_MODEL_NAME}'")
    
    # Prepend system instruction to prompt for universal compatibility
    final_prompt = prompt
    if system_instruction:
        final_prompt = f"System Instruction:\n{system_instruction}\n\nUser Question:\n{prompt}"
        
    try:
        if LLM_PROVIDER == "gemini":
            # Google Gemini REST Endpoint
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL_NAME}:generateContent?key={LLM_API_KEY}"
            headers = {"Content-Type": "application/json"}
            
            # Formulate Gemini Payload
            payload = {
                "contents": [{
                    "parts": [{
                        "text": final_prompt
                    }]
                }]
            }
            # Add native systemInstruction if v1beta supports it natively in headers/payload
            if system_instruction:
                payload["systemInstruction"] = {
                    "parts": [{
                        "text": system_instruction
                    }]
                }
                # Remove systemInstruction prefix from final_prompt to avoid redundancy
                payload["contents"][0]["parts"][0]["text"] = prompt
                
            req_body = json.dumps(payload).encode("utf-8")
            
        elif LLM_PROVIDER == "ollama":
            # For Ollama, handle native /api/chat or OpenAI-compatible depending on path
            if "v1" in LLM_API_ENDPOINT:
                url = f"{LLM_API_ENDPOINT.rstrip('/')}/chat/completions"
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                payload = {
                    "model": LLM_MODEL_NAME,
                    "messages": messages,
                    "temperature": 0.2
                }
            else:
                url = f"{LLM_API_ENDPOINT.rstrip('/')}/api/chat"
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                payload = {
                    "model": LLM_MODEL_NAME,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.2
                    }
                }
            headers = {"Content-Type": "application/json"}
            req_body = json.dumps(payload).encode("utf-8")
            
        else:
            # OpenAI / Custom API Compatible Endpoint
            url = f"{LLM_API_ENDPOINT.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json"
            }
            if LLM_API_KEY:
                headers["Authorization"] = f"Bearer {LLM_API_KEY}"
                
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": LLM_MODEL_NAME,
                "messages": messages,
                "temperature": 0.2
            }
            req_body = json.dumps(payload).encode("utf-8")
            
        # Send REST API request
        req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30.0) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            
            # Parse response depending on provider schema
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
                # Support native Ollama /api/chat response structure
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

def ai_data_recovery(raw_ocr_text: str) -> dict:
    """
    Invokes the LLM to parse raw OCR'd text and extract key legal claims fields.
    Acts as a premium data recovery layer when heuristics are incomplete.
    """
    system_instruction = (
        "You are an expert legal data extraction engine specializing in Motor Accident Claims Tribunal (MACT) judgments.\n"
        "Your task is to analyze the provided raw OCR text and extract key compensation parameters.\n"
        "Return ONLY a clean, valid JSON object containing exactly the following keys (use null if the field is not present or cannot be determined):\n"
        "- claimant_name (string or null)\n"
        "- respondent_name (string or null)\n"
        "- deceased_name (string or null)\n"
        "- father_name (string or null)\n"
        "- age (integer or null)\n"
        "- occupation (string or null)\n"
        "- monthly_income (float or null)\n"
        "- disability_percentage (float or null)\n"
        "- multiplier (integer or null)\n"
        "- future_prospects (float or null)\n"
        "- accident_date (string or null, formatted as DD-MM-YYYY)\n"
        "- award_amount (float or null)\n"
        "- interest_rate (float or null)\n"
        "Do NOT write any preamble, explanation, markdown fences, or comments. Return only the JSON object."
    )
    
    # We pass a truncated text block to prevent context window overhead on large files
    truncated_text = raw_ocr_text[:15000]
    prompt = f"Analyze this court judgment extract and recover the fields:\n\n{truncated_text}"
    
    response = generate_response(prompt, system_instruction)
    
    try:
        # Extract JSON block using regex if LLM surrounds it with markdown tags
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            data = json.loads(response)
            
        # Add aliases for seamless mapping into different parsed field structures
        if "claimant_name" in data and data["claimant_name"]:
            data["name"] = data["claimant_name"]
            data["injured_name"] = data["claimant_name"]
        elif "deceased_name" in data and data["deceased_name"]:
            data["name"] = data["deceased_name"]
            data["injured_name"] = data["deceased_name"]
            
        if "disability_percentage" in data and data["disability_percentage"] is not None:
            data["disability"] = data["disability_percentage"]
            
        if "future_prospects" in data and data["future_prospects"] is not None:
            data["future_prospect"] = data["future_prospects"]
            
        if "accident_date" in data and data["accident_date"]:
            data["date_of_accident"] = data["accident_date"]
            
        if "award_amount" in data and data["award_amount"] is not None:
            data["total_compensation"] = data["award_amount"]
            
        logger.info(f"AI Data Recovery successful: {list(data.keys())}")
        return data
    except Exception as e:
        logger.error(f"Failed to parse AI Data Recovery JSON: {str(e)}. Raw response: {response}")
        return {}

