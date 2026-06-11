# import logging
# from backend.vector_db import semantic_search
# from backend.calculator import CompensationRequest, calculate_death_compensation, calculate_injury_compensation

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("Evaluator")

# def calculate_award_for_precedent(pred_meta):
#     """
#     Helper to calculate what our math engine would award a precedent 
#     based on its historical parameters. Used if explicit award_amount 
#     was not parsed from the precedent text.
#     """
#     try:
#         case_type = pred_meta.get("case_type", "injury")
        
#         # Build mock/reconstructed request from metadata
#         req_data = {
#             "case_type": case_type,
#             "age": int(pred_meta.get("age")) if pred_meta.get("age") else 30,
#             "monthly_income": float(pred_meta.get("monthly_income")) if pred_meta.get("monthly_income") else 15000.0,
#             # Defaults
#             "dependents": int(pred_meta.get("dependents")) if pred_meta.get("dependents") else 3,
#             "marital_status": pred_meta.get("marital_status", "married") or "married",
#             "future_type": 2,
#             "consortium": 40000.0,
#             "funeral_expenses": 15000.0,
#             "loss_estate": 15000.0,
#             "disability": float(pred_meta.get("disability")) if pred_meta.get("disability") else 0.0,
#             "medical_expenses": 50000.0,  # standard mock clinical expenses
#             "future_medical_expenses": 10000.0,
#             "pain_and_suffering": 25000.0,
#             "transportation": 10000.0,
#             "special_diet": 10000.0,
#             "attender_charges": 15000.0,
#             "loss_of_income": 20000.0
#         }
        
#         # Run calculation using calculator engine
#         req_obj = CompensationRequest(**req_data)
#         if case_type == "death":
#             res = calculate_death_compensation(req_obj)
#         else:
#             res = calculate_injury_compensation(req_obj)
            
#         return res.get("final_amount", 0)
#     except Exception as e:
#         logger.error(f"Error calculating award for precedent fallback: {str(e)}")
#         return 0

# def evaluate_compensation_precedents(current_params: dict, current_calculated_amount: float) -> dict:
#     """
#     Compares the calculated award of the current case against historical 
#     judgments extracted from the Qdrant DB.
#     """
#     case_type = current_params.get("case_type", "injury")
#     age = current_params.get("age", 30)
#     income = current_params.get("monthly_income", 15000.0)
#     disability = current_params.get("disability", 0.0)
#     dependents = current_params.get("dependents", 0)
    
#     # 1. Construct semantic search query describing the current profile
#     if case_type == "death":
#         query = f"fatal death accident case deceased age {age} income Rs. {income} pm dependents {dependents} married"
#     else:
#         query = f"injury accident case injured age {age} income Rs. {income} pm disability {disability} percent permanent impairment"
        
#     logger.info(f"Querying Qdrant for precedents matching: '{query}'")
    
#     # 2. Search Qdrant for 4 closest semantic matching legal documents
#     matches = semantic_search(query, limit=4, case_type_filter=case_type)
    
#     precedents_list = []
#     precedent_awards = []
    
#     # Standard fallback mock precedents if no actual judgments have been indexed in Qdrant yet!
#     # Ensures the evaluation dashboard is gorgeous and fully functional from day one!
#     if not matches:
#         logger.info("No vectors found in Qdrant collection. Compiling robust simulated precedents matching profile.")
#         if case_type == "death":
#             mock_data = [
#                 {"name": "Late Ram Sharan", "age": age - 2, "monthly_income": income * 0.9, "dependents": dependents, "marital_status": "married", "similarity": 0.89, "filename": "mact_judgment_jabalpur_2023.pdf"},
#                 {"name": "Late Suresh Verma", "age": age + 3, "monthly_income": income * 1.1, "dependents": dependents + 1, "marital_status": "married", "similarity": 0.84, "filename": "highcourt_indore_fatal_2022.pdf"},
#                 {"name": "Late Ajay Prakash", "age": age, "monthly_income": income * 1.0, "dependents": max(1, dependents - 1), "marital_status": "single", "similarity": 0.81, "filename": "mact_case_gwaliar_102.pdf"}
#             ]
#         else:
#             mock_data = [
#                 {"name": "Karan Johar", "age": age - 4, "monthly_income": income * 0.85, "disability": disability * 0.9, "similarity": 0.91, "filename": "mact_injury_compensation_2024.pdf"},
#                 {"name": "Dinesh Kartick", "age": age + 5, "monthly_income": income * 1.05, "disability": disability * 1.1, "similarity": 0.87, "filename": "highcourt_appeal_injury_2023.pdf"},
#                 {"name": "Sanjay Dutt", "age": age, "monthly_income": income * 1.0, "disability": disability, "similarity": 0.83, "filename": "mact_jabalpur_judgment_405.pdf"}
#             ]
            
#         for mock in mock_data:
#             award = calculate_award_for_precedent(mock)
#             precedent_awards.append(award)
#             precedents_list.append({
#                 "filename": mock["filename"],
#                 "score": mock["similarity"],
#                 "name": mock["name"],
#                 "details": f"Age: {mock.get('age', age)} | Income: Rs. {int(mock['monthly_income'])}/pm" + 
#                            (f" | Disability: {mock['disability']}%" if case_type == "injury" else ""),
#                 "award_amount": award,
#                 "is_calculated_fallback": True
#             })
#     else:
#         # Use actual Qdrant matches!
#         for m in matches:
#             meta = m["metadata"]
            
#             # Use explicit award amount if parsed, otherwise calculate standard math based on parameters
#             award = float(meta.get("award_amount")) if meta.get("award_amount") else 0.0
#             is_calculated = False
#             if award <= 0:
#                 award = calculate_award_for_precedent(meta)
#                 is_calculated = True
                
#             precedent_awards.append(award)
            
#             precedents_list.append({
#                 "filename": m["filename"],
#                 "score": m["score"],
#                 "name": meta.get("name", "Unnamed Claimant"),
#                 "details": f"Age: {meta.get('age', age)} | Income: Rs. {int(float(meta['monthly_income'])) if meta.get('monthly_income') else int(income)}/pm" + 
#                            (f" | Disability: {meta['disability']}%" if case_type == "injury" else ""),
#                 "award_amount": int(award),
#                 "is_calculated_fallback": is_calculated
#             })

#     # 3. Perform comparative mathematical calculations
#     avg_precedent_award = sum(precedent_awards) / len(precedent_awards) if precedent_awards else current_calculated_amount
    
#     margin_percent = 0.0
#     if avg_precedent_award > 0:
#         margin_percent = ((current_calculated_amount - avg_precedent_award) / avg_precedent_award) * 100
        
#     # Classify alignment
#     if abs(margin_percent) <= 5.0:
#         alignment = "aligned"
#         recommendation = f"Your calculated compensation is extremely well-aligned with historical court precedents ({margin_percent:+.1f}% margin). This presents a highly defensible, objective claims position suitable for quick out-of-court settlements."
#     elif margin_percent > 5.0:
#         alignment = "high"
#         recommendation = f"Your calculated compensation is {margin_percent:.1f}% HIGHER than historical precedents. Insurance adjusters may seek to negotiate this down. We recommend double-checking discretionary claims like 'Pain and Suffering' or 'Special Diet' to ensure strict documentary proof is ready for court."
#     else:
#         alignment = "low"
#         recommendation = f"Your calculated compensation is {abs(margin_percent):.1f}% LOWER than historical precedents. You may be under-compensating the claimant. We suggest reviewing if active medical bills, helper/attender costs, or future medical requirements have been fully quantified."

#     # 4. Generate structured legal arguments for both sides
#     insurance_defense = f"Precedent judgments suggest that for a monthly income profile of Rs. {int(income)}, the average dependency/loss award is historically capped around {int(avg_precedent_award * 0.95)} to {int(avg_precedent_award)}. Adjustments should be made to align with {precedents_list[0]['filename']}."
#     claimant_argument = f"Historical court awards for claimant profiles similar to {current_params.get('name', 'the claimant')} (e.g. {precedents_list[0]['name']} in {precedents_list[0]['filename']}) show that tribunal awards consistently reach up to {format_currency(max(precedent_awards))}. The requested compensation is fully consistent with established legal valuation principles."

#     return {
#         "calculated_amount": int(current_calculated_amount),
#         "average_precedent_award": int(avg_precedent_award),
#         "margin_percent": round(margin_percent, 2),
#         "alignment": alignment,
#         "recommendation": recommendation,
#         "insurance_defense": insurance_defense,
#         "claimant_argument": claimant_argument,
#         "precedents": precedents_list
#     }

# def format_currency(amount):
#     return f"Rs. {int(amount):,}"



import logging
import random
from backend.vector_db import semantic_search, scroll_documents_by_case_type
from backend.calculator import CompensationRequest, calculate_death_compensation, calculate_injury_compensation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Evaluator")


def calculate_award_for_precedent(pred_meta):
    """
    Runs our math engine on a precedent's parsed parameters to reconstruct
    what the tribunal would have awarded, used when award_amount was not
    extracted from the PDF text.
    """
    try:
        case_type = pred_meta.get("case_type", "injury")

        req_data = {
            "case_type": case_type,
            "age": int(pred_meta.get("age")) if pred_meta.get("age") else 30,
            "monthly_income": float(pred_meta.get("monthly_income")) if pred_meta.get("monthly_income") else 15000.0,
            "dependents": int(pred_meta.get("dependents")) if pred_meta.get("dependents") else 3,
            "marital_status": pred_meta.get("marital_status", "married") or "married",
            "future_type": 2,
            "consortium": 40000.0,
            "funeral_expenses": 15000.0,
            "loss_estate": 15000.0,
            "disability": float(pred_meta.get("disability")) if pred_meta.get("disability") else 0.0,
            "medical_expenses": 50000.0,
            "future_medical_expenses": 10000.0,
            "pain_and_suffering": 25000.0,
            "transportation": 10000.0,
            "special_diet": 10000.0,
            "attender_charges": 15000.0,
            "loss_of_income": 20000.0
        }

        req_obj = CompensationRequest(**req_data)
        if case_type == "death":
            res = calculate_death_compensation(req_obj)
        else:
            res = calculate_injury_compensation(req_obj)

        return res.get("final_amount", 0)
    except Exception as e:
        logger.error(f"Error calculating award for precedent: {str(e)}")
        return 0


def _deduplicate_matches(matches: list) -> list:
    """
    When multiple chunks from the same PDF are returned (e.g., 3 chunks from
    judgment_123.pdf), keep only the single richest chunk per filename.
    Richness = has award_amount > 0, has age, has income.
    """
    seen = {}
    for m in matches:
        fname = m.get("filename", "")
        meta = m.get("metadata", {})

        award = 0.0
        try:
            award = float(meta.get("award_amount") or 0)
        except (ValueError, TypeError):
            award = 0.0

        richness = (
            (1 if award > 0 else 0) +
            (1 if meta.get("age") else 0) +
            (1 if meta.get("monthly_income") else 0) +
            m.get("score", 0)   # higher similarity score wins ties
        )

        if fname not in seen or richness > seen[fname]["_richness"]:
            entry = dict(m)
            entry["_richness"] = richness
            seen[fname] = entry

    result = []
    for entry in seen.values():
        entry.pop("_richness", None)
        result.append(entry)

    # Re-sort by original score descending
    result.sort(key=lambda x: x.get("score", 0), reverse=True)
    return result


def _pick_best_precedents(all_docs: list, current_params: dict, n: int = 5) -> list:
    """
    From a pool of scrolled documents (no embedding similarity score),
    pick the n most similar by simple heuristic: closest age + income proximity.
    """
    age = current_params.get("age", 30)
    income = current_params.get("monthly_income", 15000)
    disability = current_params.get("disability", 0)

    scored = []
    for doc in all_docs:
        meta = doc.get("metadata", {})
        try:
            doc_age = float(meta.get("age") or age)
        except (ValueError, TypeError):
            doc_age = age
        try:
            doc_income = float(meta.get("monthly_income") or income)
        except (ValueError, TypeError):
            doc_income = income
        try:
            doc_disability = float(meta.get("disability") or disability)
        except (ValueError, TypeError):
            doc_disability = disability

        # Normalised distance — lower is better
        age_diff = abs(doc_age - age) / max(age, 1)
        income_diff = abs(doc_income - income) / max(income, 1)
        disability_diff = abs(doc_disability - disability) / max(disability, 1) if disability else 0

        proximity = 1.0 - min(1.0, (age_diff * 0.4 + income_diff * 0.4 + disability_diff * 0.2))
        scored.append((proximity, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:n]]


def evaluate_compensation_precedents(current_params: dict, current_calculated_amount: float) -> dict:
    """
    Compares the current case's calculated award against real historical judgments
    from the Qdrant vector database.

    Strategy:
      1. Try semantic search via Ollama embeddings (best quality)
      2. If Ollama is offline / returns nothing, fall back to Qdrant scroll +
         proximity-based ranking (no embeddings needed)
      3. Only use dummy data if Qdrant itself is offline (clearly labelled)
    """
    case_type = current_params.get("case_type", "injury")
    age = current_params.get("age", 30)
    income = current_params.get("monthly_income", 15000.0)
    disability = current_params.get("disability", 0.0)
    dependents = current_params.get("dependents", 0)

    # ── 1. Semantic search via Ollama ──────────────────────────────────────────
    if case_type == "death":
        query = (f"fatal death accident case deceased age {age} "
                 f"income Rs. {income} pm dependents {dependents} married")
    else:
        query = (f"injury accident case injured age {age} income Rs. {income} pm "
                 f"disability {disability} percent permanent impairment")

    logger.info(f"Semantic search query: '{query}'")
    raw_matches = semantic_search(query, limit=12, case_type_filter=case_type)

    data_source = "semantic"
    if raw_matches:
        matches = _deduplicate_matches(raw_matches)[:5]
        logger.info(f"Semantic search returned {len(raw_matches)} chunks → {len(matches)} unique PDFs")
    else:
        # ── 2. Scroll fallback — no Ollama needed ──────────────────────────────
        logger.info("Semantic search returned nothing. Falling back to Qdrant scroll.")
        all_docs = scroll_documents_by_case_type(case_type=case_type, limit=300)
        if all_docs:
            matches = _pick_best_precedents(all_docs, current_params, n=5)
            data_source = "scroll"
            logger.info(f"Scroll fallback: selected {len(matches)} closest docs from {len(all_docs)} indexed")
        else:
            matches = []
            data_source = "none"

    # ── 3. Build precedents list from real matches ─────────────────────────────
    precedents_list = []
    precedent_awards = []

    if matches:
        for m in matches:
            meta = m["metadata"]

            award = 0.0
            try:
                award = float(meta.get("award_amount") or 0)
            except (ValueError, TypeError):
                award = 0.0

            is_calculated = False
            if award <= 0:
                award = calculate_award_for_precedent(meta)
                is_calculated = True

            if award <= 0:
                continue   # skip documents with completely unresolvable award

            precedent_awards.append(award)

            name = meta.get("name") or meta.get("claimant") or "Unnamed Claimant"
            try:
                doc_age = int(float(meta.get("age") or age))
            except (ValueError, TypeError):
                doc_age = age
            try:
                doc_income = int(float(meta.get("monthly_income") or income))
            except (ValueError, TypeError):
                doc_income = int(income)

            details = f"Age: {doc_age} | Income: Rs. {doc_income:,}/pm"
            if case_type == "injury" and meta.get("disability"):
                try:
                    details += f" | Disability: {float(meta['disability']):.0f}%"
                except (ValueError, TypeError):
                    pass

            score = m.get("score", 0.75)

            precedents_list.append({
                "filename": m["filename"],
                "score": round(score, 4),
                "name": name,
                "details": details,
                "award_amount": int(award),
                "is_calculated_fallback": is_calculated,
                "data_source": data_source
            })

    # ── 4. No real data at all ─────────────────────────────────────────────────
    if not precedents_list:
        logger.warning("No real precedent data available. Returning empty evaluation with clear message.")
        return {
            "calculated_amount": int(current_calculated_amount),
            "average_precedent_award": 0,
            "margin_percent": 0.0,
            "alignment": "no_data",
            "recommendation": (
                "No indexed PDF judgments found in the database for this case type. "
                "Please upload and index PDF judgments via the PDF Library tab to enable "
                "real precedent-based benchmarking."
            ),
            "insurance_defense": "Insufficient precedent data to generate arguments.",
            "claimant_argument": "Insufficient precedent data to generate arguments.",
            "precedents": [],
            "data_source": "none"
        }

    # ── 5. Comparative analysis ────────────────────────────────────────────────
    avg_precedent_award = sum(precedent_awards) / len(precedent_awards)

    margin_percent = 0.0
    if avg_precedent_award > 0:
        margin_percent = ((current_calculated_amount - avg_precedent_award) / avg_precedent_award) * 100

    if abs(margin_percent) <= 5.0:
        alignment = "aligned"
        recommendation = (
            f"Your calculated compensation is extremely well-aligned with historical court "
            f"precedents ({margin_percent:+.1f}% margin). This presents a highly defensible, "
            f"objective claims position suitable for quick out-of-court settlement."
        )
    elif margin_percent > 5.0:
        alignment = "high"
        recommendation = (
            f"Your calculated compensation is {margin_percent:.1f}% HIGHER than the average of "
            f"{len(precedent_awards)} comparable precedents. Insurance adjusters may seek to "
            f"negotiate this down. Ensure discretionary heads like 'Pain and Suffering' and "
            f"'Special Diet' are backed by documentary evidence."
        )
    else:
        alignment = "low"
        recommendation = (
            f"Your calculated compensation is {abs(margin_percent):.1f}% LOWER than the average "
            f"of {len(precedent_awards)} comparable precedents. The claimant may be under-compensated. "
            f"Review if medical bills, attender costs, or future medical requirements have been "
            f"fully quantified."
        )

    top = precedents_list[0]
    max_award = max(precedent_awards)
    insurance_defense = (
        f"Comparable tribunal awards in the database average "
        f"Rs. {int(avg_precedent_award * 0.95):,} – Rs. {int(avg_precedent_award):,} "
        f"for a monthly income of Rs. {int(income):,}. "
        f"See: {top['filename']}."
    )
    claimant_argument = (
        f"Historical awards for profiles similar to this claimant "
        f"(e.g. {top['name']} in {top['filename']}) reach up to "
        f"{format_currency(max_award)}. The requested compensation is consistent "
        f"with established judicial valuation principles."
    )

    return {
        "calculated_amount": int(current_calculated_amount),
        "average_precedent_award": int(avg_precedent_award),
        "margin_percent": round(margin_percent, 2),
        "alignment": alignment,
        "recommendation": recommendation,
        "insurance_defense": insurance_defense,
        "claimant_argument": claimant_argument,
        "precedents": precedents_list,
        "data_source": data_source
    }


def format_currency(amount):
    return f"Rs. {int(amount):,}"
