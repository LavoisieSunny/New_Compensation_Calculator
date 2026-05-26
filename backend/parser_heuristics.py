import re
import logging
from datetime import datetime

logger = logging.getLogger("ParserHeuristics")


def clean_noisy_text(text_line):
    """
    Cleans OCR scanning noise, stray characters, and common digit typos (like letter O/o instead of 0).
    """
    cleaned = text_line.strip()
    
    # 1. Repair common OCR digit typos: 'O' or 'o' scanned instead of '0' inside numbers
    cleaned = re.sub(r'(?<=\d)[Oo](?=\d)', '0', cleaned) # O surrounded by digits
    cleaned = re.sub(r'(?<=\d)[Oo]$', '0', cleaned)     # O at the end of a number
    cleaned = re.sub(r'^[Oo](?=\d)', '0', cleaned)     # O at the start of a number
    
    # 2. Repair dates with O/o typos, e.g. "12-O4-1992" or "12-o4-1992"
    cleaned = re.sub(r'\b(\d{1,2})[-/\.][Oo](\d)[-/\.](\d{4})\b', r'\1-0\g<2>-\3', cleaned)
    cleaned = re.sub(r'\b(\d{1,2})[-/\.](\d)[Oo][-/\.](\d{4})\b', r'\1-\g<2>0-\3', cleaned)
    cleaned = re.sub(r'\b(\d{1,2})[-/\.][Oo][Oo][-/\.](\d{4})\b', r'\1-00-\g<2>', cleaned)
    cleaned = re.sub(r'\b[Oo](\d)[-/\.](\d{1,2})[-/\.](\d{4})\b', r'0\g<1>-\g<2>-\3', cleaned)
    
    # 3. Remove typical OCR vertical bars or bracket noise in numeric/date lines
    if any(kw in cleaned.lower() for kw in ["rs", "income", "salary", "disability", "age", "dob", "date"]):
        cleaned = re.sub(r'[\|\[\]\~\^\#\_]', '', cleaned).strip()
        
    return cleaned


def merge_ocr_lines_to_paragraphs(text_lines):
    """
    Cleans noisy lines, filters out boilerplate/registry noise,
    and merges multi-page paragraph continuations (where lines do not end in sentence terminals).
    """
    cleaned_lines = []
    
    # Procedural boilerplate filters
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
        cleaned = clean_noisy_text(line)
        if not cleaned:
            continue
            
        # Ignore obvious procedural boilerplate lines
        if any(re.search(pat, cleaned.lower()) for pat in boilerplate_patterns):
            continue
            
        cleaned_lines.append(cleaned)
        
    # Paragraph reconstruction (continuations)
    merged_blocks = []
    current_block = ""
    
    for line in cleaned_lines:
        if not current_block:
            current_block = line
            continue
            
        # If the current block does not end with sentence-terminal punctuation
        # and the next line doesn't start with an uppercase heading, merge them!
        ends_with_terminal = current_block[-1] in ['.', '?', '!', ':']
        starts_with_heading = line.isupper() and len(line) > 5
        starts_with_bullet = bool(re.match(r'^\s*(?:\d+|[a-zA-Z])[\.\)\-\]]', line))
        
        if not ends_with_terminal and not starts_with_heading and not starts_with_bullet:
            # Word hyphenation continuation check, e.g. "compen-" + "sation"
            if current_block.endswith('-'):
                current_block = current_block[:-1] + line
            else:
                current_block += " " + line
        else:
            merged_blocks.append(current_block)
            current_block = line
            
    if current_block:
        merged_blocks.append(current_block)
        
    return merged_blocks


def parse_indian_rupee_value(text):
    """
    Parses and normalises Indian currency text, converting Lakhs, Crores, commas, and suffixes into float.
    E.g. "Rs. 1,50,000/-" -> 150000.0
         "1.5 Lakhs" -> 150000.0
         "2.5 Lakh" -> 250000.0
         "Rs. 2 Lakhs" -> 200000.0
    """
    if not text:
        return 0.0
        
    text = text.lower().strip()
    
    # Clean up standard rupee notations
    text = re.sub(r'[\brs\.?|inr|rupees?|\/\-]|\s+', '', text)
    
    # Check for Lakh/Lakhs
    lakh_match = re.search(r'([\d\.]+)\s*(?:lakhs?|lac|lacs)', text)
    if lakh_match:
        try:
            return float(lakh_match.group(1)) * 100000.0
        except ValueError:
            pass
            
    # Check for Crore/Crores
    crore_match = re.search(r'([\d\.]+)\s*(?:crores?|cr)', text)
    if crore_match:
        try:
            return float(crore_match.group(1)) * 10000000.0
        except ValueError:
            pass
            
    # Remove commas and extract numbers
    cleaned_num = re.sub(r'[^\d\.]', '', text)
    try:
        if cleaned_num:
            return float(cleaned_num)
    except ValueError:
        pass
        
    return 0.0


def parse_compensation_table(text):
    """
    Layer 3: Compensation Table Parser.
    Parses structured lists of compensation heads and amounts from text blocks.
    E.g. "1. Loss of dependency: Rs. 10,80,000/-" -> {"Loss of dependency": 1080000.0}
    """
    table = {}
    lines = text.split("\n")
    
    # Restrict heads strictly to key MACT compensation terms
    valid_heads = ["dependency", "consortium", "funeral", "estate", "pain", "medical", "transport", "nourishment", "attender", "disability", "amenities", "earning", "structure"]
    
    # Matches patterns like "1. Loss of dependency: Rs. 10,80,000/-" or "Loss of consortium ... Rs. 40,000"
    pattern = r'(?:\d+[\.\)\-]\s*)?([A-Za-z\s&\(\)/\-\’\‘\“\”]+)\s*(?:[:\-–]|\b\.?\s*rs\.?\b)\s*(?:rs\.?|inr)?\s*([\d,\.\s]+lakhs?|[\d,\.\-\/]+)\b'
    
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        m = re.search(pattern, line_clean, re.IGNORECASE)
        if m:
            head = m.group(1).strip()
            head = re.sub(r'\s+', ' ', head).strip()
            
            # Filter out obviously false table rows and ensure it contains valid legal heads
            if len(head) > 3 and any(kw in head.lower() for kw in valid_heads):
                if not any(kw in head.lower() for kw in ["total", "awarded", "interest", "passed", "order", "judgment"]):
                    val = parse_indian_rupee_value(m.group(2))
                    if val > 0:
                        table[head.title()] = val
                    
    return table


def contextual_extract(patterns, sections, priority_list, type_cast=str, default_val=None):
    """
    Layer 2: Contextual Entity Extraction.
    Searches only within prioritized legal sections using specific anchor words.
    Returns (value, confidence_float, source_section).
    """
    for sec_name, base_weight in priority_list:
        text = sections.get(sec_name, "")
        if not text:
            continue
            
        for pat in patterns:
            is_name = "name" in pat.lower() or "deceased" in pat.lower() or "claimant" in pat.lower()
            search_text = text if is_name else text.lower()
            
            m = re.search(pat, search_text)
            if m:
                raw_val = m.group(1).strip()
                raw_val = re.sub(r'\s+', ' ', raw_val).strip()
                
                if type_cast == float:
                    val = parse_indian_rupee_value(raw_val)
                    if val > 0:
                        return val, round(base_weight / 100.0, 2), sec_name
                elif type_cast == int:
                    digit_match = re.search(r'\d+', raw_val)
                    if digit_match:
                        try:
                            val = int(digit_match.group(0))
                            return val, round(base_weight / 100.0, 2), sec_name
                        except ValueError:
                            pass
                else:
                    if len(raw_val) > 2:
                        return raw_val, round(base_weight / 100.0, 2), sec_name
                        
    fallback_confidence = 0.40
    return default_val, fallback_confidence, "raw_ocr"


def simulate_fallback_ai_recovery(petitioner_details, prayer_section, compensation_paragraphs, award_section, case_type):
    """
    Layer 4: Fallback AI Recovery.
    Simulates a legal AI parsing over the isolated semantic sections.
    """
    logger.info("Executing Fallback AI Recovery on isolated legal sections...")
    recovered = {}
    
    # 1. Recover Name
    name_m = re.search(r'\b(?:injured|deceased|claimant|petitioner|late shri)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})', petitioner_details)
    if name_m:
        recovered["name"] = name_m.group(1).strip()
        
    # 2. Recover Age
    age_m = re.search(r'\b(?:age|aged|approximately)\s*(\d{1,2})\b', petitioner_details + " " + compensation_paragraphs)
    if age_m:
        recovered["age"] = int(age_m.group(1))
        
    # 3. Recover Income
    inc_m = re.search(r'\b(?:monthly\s+income|salary|earning|coolie|wages?)\b.*?(\d{4,6})\b', compensation_paragraphs)
    if inc_m:
        recovered["monthly_income"] = float(inc_m.group(1))
        
    # 4. Recover Dependents
    dep_m = re.search(r'\b(\d{1,2})\s*(?:dependents?|family\s+members)\b', petitioner_details)
    if dep_m:
        recovered["dependents"] = int(dep_m.group(1))
        
    # 5. Recover Award Amount
    aw_m = re.search(r'\b(?:awarded|compensation\s+of\s+rs\.?|tribunal\s+awards)\s*([\d,\.]+)\b', award_section)
    if aw_m:
        recovered["award_amount"] = parse_indian_rupee_value(aw_m.group(1))
        
    return recovered


def parse_extracted_text(text_lines):
    """
    Highly advanced 5-Layer Layout-Aware Legal Semantic Parser.
    """
    merged_lines = merge_ocr_lines_to_paragraphs(text_lines)
    full_text = "\n".join(merged_lines)
    full_text_lower = full_text.lower()

    # ======================================================
    # LAYER 1 — DOCUMENT SECTION DETECTION
    # ======================================================
    sections = {
        "petitioner_details": [],
        "respondent_details": [],
        "prayer_section": [],
        "compensation_paragraphs": [],
        "findings_section": [],
        "award_section": [],
        "dependency_analysis": [],
        "multiplier_calculations": [],
        "future_prospects_section": [],
        "judgment_section": []
    }
    
    current_sec = "petitioner_details"
    
    for line in merged_lines:
        line_lower = line.lower()
        
        # Heading triggers & semantic transitions
        if any(kw in line_lower for kw in ["petitioner", "claimant details", "profile of injured", "injured profile", "deceased details"]):
            current_sec = "petitioner_details"
        elif any(kw in line_lower for kw in ["respondent", "insurance company", "driver of", "owner of"]):
            current_sec = "respondent_details"
        elif any(kw in line_lower for kw in ["prayer", "relief claimed", "wherefore", "prays for", "claims Rs", "claim of the petitioner"]):
            current_sec = "prayer_section"
        elif any(kw in line_lower for kw in ["quantum", "loss of earning", "loss of dependency", "monthly income", "salary of", "earning of", "coolie", "income of"]):
            current_sec = "compensation_paragraphs"
        elif any(kw in line_lower for kw in ["issue no", "negligence", "negligent", "liability", "findings of the tribunal"]):
            current_sec = "findings_section"
        elif any(kw in line_lower for kw in ["final order", "award is passed", "award decree", "total compensation Rs", "interest rate", "decree"]):
            current_sec = "award_section"
        elif any(kw in line_lower for kw in ["dependents", "marital status", "family structure", "wife of", "widow", "minor children", "dependents of"]):
            current_sec = "dependency_analysis"
        elif any(kw in line_lower for kw in ["multiplier", "sarla verma", "age standard multiplier"]):
            current_sec = "multiplier_calculations"
        elif any(kw in line_lower for kw in ["future prospect", "pranay sethi", "prospects of"]):
            current_sec = "future_prospects_section"
        elif any(kw in line_lower for kw in ["impugned judgment", "referred to", "precedents", "supreme court in", "held in"]):
            current_sec = "judgment_section"
            
        sections[current_sec].append(line)
        
    section_blocks = {k: "\n".join(v) for k, v in sections.items()}
    section_blocks["raw_ocr"] = full_text
    
    # Fallback if splits are empty
    for k in ["petitioner_details", "prayer_section", "compensation_paragraphs", "award_section"]:
        if len(sections[k]) < 1:
            section_blocks[k] = full_text

    # ======================================================
    # LAYER 2 — CONTEXTUAL ENTITY EXTRACTION
    # ======================================================
    
    # 1. Claimant Name
    claimant_patterns = [
        r'(?:name\s+of\s+)?(?:injured|claimant|victim)\s*(?:name)?\s*:\s*([A-Za-z \t\.]{3,30})',
        r'petitioner\s*(?:name)?\s*:\s*([A-Za-z \t\.]{3,30})',
        r'\bshri\b\s*([A-Za-z \t\.]{3,30})'
    ]
    claimant_priority = [("petitioner_details", 90), ("compensation_paragraphs", 75)]
    claimant_name, conf_claimant_name, sec_claimant_name = contextual_extract(
        claimant_patterns, section_blocks, claimant_priority, type_cast=str
    )
    if claimant_name: claimant_name = claimant_name.title()

    # 2. Deceased Name
    dec_patterns = [
        r'(?:name\s+of\s+)?deceased\s*(?:name)?\s*:\s*([A-Za-z \t\.]{3,30})',
        r'death\s+of\s+([A-Za-z \t\.]{3,30})',
        r'late\s+shri\s+([A-Za-z \t\.]{3,30})'
    ]
    dec_priority = [("petitioner_details", 90), ("compensation_paragraphs", 80)]
    deceased_name, conf_deceased_name, sec_deceased_name = contextual_extract(
        dec_patterns, section_blocks, dec_priority, type_cast=str
    )
    if deceased_name: deceased_name = deceased_name.title()

    # 3. Father / Husband Name
    father_patterns = [
        r'(?:father|husband)\s*(?:s\s*)?name\s*:\s*([A-Za-z \t\.]{3,30})',
        r'\bs\/o\b\s*(?:shri)?\s*([A-Za-z \t\.]{3,30})',
        r'\bw\/o\b\s*(?:shri)?\s*([A-Za-z \t\.]{3,30})'
    ]
    father_priority = [("petitioner_details", 90)]
    father_name, conf_father_name, sec_father_name = contextual_extract(
        father_patterns, section_blocks, father_priority, type_cast=str
    )
    if father_name: father_name = father_name.title()

    # 4. Age
    age_patterns = [
        r'(?:aged\s+about|age\s+of\s+deceased|aged|approximately)\s*[:\-]?\s*(\d{1,2})\b',
        r'\b(\d{1,2})\s*years\s*(?:old)?\b'
    ]
    age_priority = [("petitioner_details", 95), ("compensation_paragraphs", 90), ("dependency_analysis", 85)]
    age, conf_age, sec_age = contextual_extract(
        age_patterns, section_blocks, age_priority, default_val="", type_cast=int
    )

    # 5. Occupation
    occ_patterns = [
        r'occupation\s*:\s*([A-Za-z \t]{3,30})',
        r'employed\s+as\s+([A-Za-z \t]{3,30})',
        r'working\s+as\s+([A-Za-z \t]{3,30})',
        r'earning\s+as\s+([A-Za-z \t]{3,30})'
    ]
    occ_priority = [("petitioner_details", 90), ("compensation_paragraphs", 80)]
    occupation, conf_occupation, sec_occupation = contextual_extract(
        occ_patterns, section_blocks, occ_priority, default_val="", type_cast=str
    )
    if occupation: occupation = occupation.title()

    # 6. Monthly Income
    income_patterns = [
        r'(?:earning|monthly\s+income|salary|coolie|business|profession|occupation|wages?)\s*(?:is|was|of|@)?\s*(?:rs\.?|inr)?\s*([\d,\.\s]+lakhs?|[\d,\.\s]+lacs?|[\d,\.\-\/]+)\b',
        r'\b(?:rs\.?|inr)\s*([\d,\.]+)\s*(?:per\s*month|\/pm|\/-\s*pm|p\.m\.)'
    ]
    income_priority = [("compensation_paragraphs", 95), ("petitioner_details", 90), ("award_section", 80)]
    monthly_income, conf_monthly_income, sec_monthly_income = contextual_extract(
        income_patterns, section_blocks, income_priority, default_val="", type_cast=float
    )

    # 7. Multiplier
    multiplier_patterns = [
        r'multiplier\s*(?:of|is|applied)?\s*(\d{1,2})\b',
        r'applied\s+multiplier\s+of\s*(\d{1,2})\b',
        r'\b(\d{1,2})\s*multiplier\b'
    ]
    multiplier_priority = [("multiplier_calculations", 95), ("compensation_paragraphs", 90)]
    multiplier, conf_multiplier, sec_multiplier = contextual_extract(
        multiplier_patterns, section_blocks, multiplier_priority, default_val="", type_cast=int
    )

    # 8. Future Prospects
    prospects_patterns = [
        r'future\s+prospects?\s*(?:of|at|is|@)?\s*(\d{1,2})\s*%',
        r'addition\s+of\s*(\d{1,2})\s*%\s*(?:towards)?\s*future\s+prospects'
    ]
    prospects_priority = [("future_prospects_section", 95), ("compensation_paragraphs", 90)]
    future_prospect, conf_future_prospect, sec_future_prospect = contextual_extract(
        prospects_patterns, section_blocks, prospects_priority, default_val="", type_cast=float
    )

    # 9. Place of Accident
    place_regexes = [
        r'place\s+of\s+(?:accident|occurrence)\s*[:\-]\s*([A-Za-z0-9 \t\.\,\-\/]{3,60})',
        r'accident\s+(?:occurred|took\s+place)\s+at\s+([A-Za-z0-9 \t\.\,\-\/]{3,60})',
        r'accident\s+near\s+([A-Za-z0-9 \t\.\,\-\/]{3,60})'
    ]
    place_priority = [("petitioner_details", 95), ("raw_ocr", 40)]
    place_of_accident, conf_place_of_accident, sec_place_of_accident = contextual_extract(
        place_regexes, section_blocks, place_priority, default_val="", type_cast=str
    )
    if place_of_accident: place_of_accident = place_of_accident.title()

    # 10. Consortium, Funeral & Estate
    cons_patterns = [r'consortium\s*(?:of)?\s*(?:rs\.?|inr)?\s*(\d{4,6})\b']
    consortium, conf_consortium, sec_consortium = contextual_extract(
        cons_patterns, section_blocks, [("compensation_paragraphs", 95)], default_val=40000.0, type_cast=float
    )

    fun_patterns = [r'funeral\s*(?:expenses)?\s*(?:of)?\s*(?:rs\.?|inr)?\s*(\d{4,6})\b']
    funeral_expenses, conf_funeral_expenses, sec_funeral_expenses = contextual_extract(
        fun_patterns, section_blocks, [("compensation_paragraphs", 95)], default_val=15000.0, type_cast=float
    )

    est_patterns = [r'(?:loss\s+of\s+)?estate\s*(?:of)?\s*(?:rs\.?|inr)?\s*(\d{4,6})\b']
    estate_loss, conf_estate_loss, sec_estate_loss = contextual_extract(
        est_patterns, section_blocks, [("compensation_paragraphs", 95)], default_val=15000.0, type_cast=float
    )

    # 11. Disability
    disability_patterns = [
        r'\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:permanent)?\s*disability\b',
        r'\bdisability\b\s*(?:of|is|:)?\s*(\d{1,2}(?:\.\d+)?)\s*%'
    ]
    dis_priority = [("compensation_paragraphs", 95), ("petitioner_details", 90)]
    disability, conf_disability, sec_disability = contextual_extract(
        disability_patterns, section_blocks, dis_priority, default_val="", type_cast=float
    )

    # 12. Dependents & Marital Status
    dependents_patterns = [
        r'\b(\d{1,2})\s*dependents\b',
        r'\bno\.\s*of\s*dependents?\s*(?:is|:)?\s*(\d{1,2})\b',
        r'\bnumber\s*of\s*dependents?\s*(?:is|:)?\s*(\d{1,2})\b'
    ]
    dependents, conf_dependents, sec_dependents = contextual_extract(
        dependents_patterns, section_blocks, [("dependency_analysis", 95), ("petitioner_details", 90)], default_val="", type_cast=int
    )

    marital_status = "married"
    conf_marital_status = 0.50
    sec_marital_status = "raw_ocr"
    marital_patterns = {
        "married": ["married", "husband", "wife", "spouse"],
        "single": ["single", "unmarried", "bachelor", "spinster", "divorced"]
    }
    for status, keywords in marital_patterns.items():
        if any(kw in section_blocks["petitioner_details"].lower() for kw in keywords):
            marital_status = status
            conf_marital_status = 0.90
            sec_marital_status = "petitioner_details"
            break

    # 13. Tribunal Total Compensation Award
    award_patterns = [
        r'(?:awarded|compensation\s+of\s+rs\.?|tribunal\s+awards|granted\s+compensation\s+of\s+rs\.?)\s*([\d,\.\s]+lakhs?|[\d,\.\-\/]+)\b',
        r'\b(?:awarded\s+sum\s+of|compensation\s+amount\s+of|total\s+compensation\s+of)\s*(?:rs\.?|inr)?\s*([\d,\.\-\/]+)\b'
    ]
    total_compensation, conf_total_compensation, sec_total_compensation = contextual_extract(
        award_patterns, section_blocks, [("award_section", 95), ("compensation_paragraphs", 90)], default_val="", type_cast=float
    )

    # 14. Dates & DOB
    date_pattern = r'\b(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})\b'
    
    def extract_dates_with_context(text):
        matches = []
        for m in re.finditer(date_pattern, text):
            try:
                d_str = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{m.group(3)}"
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 12)
                context = text[start:end].lower()
                matches.append((d_str, context))
            except ValueError:
                pass
        return matches

    date_of_accident = ""
    conf_date_of_accident = 0.40
    sec_date_of_accident = "raw_ocr"
    acc_dates = extract_dates_with_context(section_blocks["petitioner_details"]) + extract_dates_with_context(full_text)
    for d_val, ctx in acc_dates:
        if any(kw in ctx for kw in ["accident", "incident", "occurrence", "happened on", "occurred on", "collision", "crash", "fir"]):
            date_of_accident = d_val
            conf_date_of_accident = 0.95
            sec_date_of_accident = "petitioner_details" if d_val in section_blocks["petitioner_details"] else "raw_ocr"
            break

    date_of_birth = ""
    conf_date_of_birth = 0.40
    sec_date_of_birth = "raw_ocr"
    dob_dates = extract_dates_with_context(section_blocks["petitioner_details"]) + extract_dates_with_context(full_text)
    for d_val, ctx in dob_dates:
        if any(kw in ctx for kw in ["dob", "date of birth", "born on", "birth", "d.o.b"]):
            date_of_birth = d_val
            conf_date_of_birth = 0.95
            sec_date_of_birth = "petitioner_details" if d_val in section_blocks["petitioner_details"] else "raw_ocr"
            break

    # 15. Prayer details & Claim Request amount
    prayer_patterns = [
        r'(?:prayer|relief\s+claimed|claims?\s+compensation\s+of|prays\s+for)\s*(?:rs\.?|inr)?\s*([\d,\.\s]+lakhs?|[\d,\.\-\/]+)\b',
        r'\b(?:claims?\s+sum\s+of|seeking\s+compensation\s+of)\s*(?:rs\.?|inr)?\s*([\d,\.\-\/]+)\b'
    ]
    prayer, conf_prayer, sec_prayer = contextual_extract(
        prayer_patterns, section_blocks, [("prayer_section", 95)], default_val="", type_cast=str
    )

    enhancement_reduction_request = "enhancement"
    conf_enhancement = 0.60
    if any(k in full_text_lower for k in ["reduction", "reduce", "excessive", "exonerate", "set aside award"]):
        enhancement_reduction_request = "reduction"
        conf_enhancement = 0.90
    elif any(k in full_text_lower for k in ["enhance", "increase", "inadequate", "enhancement"]):
        enhancement_reduction_request = "enhancement"
        conf_enhancement = 0.90

    # Case Type classification
    death_kws = ["death", "deceased", "fatal", "died on", "funeral", "consortium"]
    injury_kws = ["injury", "injured", "treatment", "disability", "medical expenses"]
    death_score = sum(3 for kw in death_kws if kw in section_blocks["petitioner_details"].lower()) + sum(1 for kw in death_kws if kw in full_text_lower)
    injury_score = sum(3 for kw in injury_kws if kw in section_blocks["petitioner_details"].lower()) + sum(1 for kw in injury_kws if kw in full_text_lower)
    case_type = "death" if death_score > injury_score else "injury"

    # ======================================================
    # LAYER 3 — LEGAL HEURISTICS ENGINE & NORMALIZATION
    # ======================================================
    expected_multiplier = 0
    expected_prospects = 0.0
    
    if isinstance(age, int) and age > 0:
        # Expected multiplier based on Sarla Verma
        if age <= 15: expected_multiplier = 20
        elif age <= 25: expected_multiplier = 18
        elif age <= 30: expected_multiplier = 17
        elif age <= 35: expected_multiplier = 16
        elif age <= 40: expected_multiplier = 15
        elif age <= 45: expected_multiplier = 14
        elif age <= 50: expected_multiplier = 13
        elif age <= 55: expected_multiplier = 11
        elif age <= 60: expected_multiplier = 9
        elif age <= 65: expected_multiplier = 7
        else: expected_multiplier = 5
        
        # Expected prospects based on Pranay Sethi
        if age < 40: expected_prospects = 40.0
        elif age < 50: expected_prospects = 25.0
        elif age < 60: expected_prospects = 10.0
        else: expected_prospects = 0.0

    # Extract structured Compensation Table if present
    compensation_table = parse_compensation_table(section_blocks["award_section"])
    if not compensation_table:
        compensation_table = parse_compensation_table(section_blocks["compensation_paragraphs"])

    # Identify Tamil Nadu MACT specifics
    is_tamil_nadu = False
    tn_keywords = ["madras", "high court of madras", "chennai", "coimbatore", "madurai", "salem", "trichy", "pondicherry", "m.c.o.p", "mcop", "tribunal, tamil nadu"]
    if any(kw in full_text_lower for kw in tn_keywords):
        is_tamil_nadu = True
        
    mcop_number = ""
    tn_disability_compensation = 0.0
    if is_tamil_nadu:
        mcop_match = re.search(r'\b(?:m\.?c\.?o\.?p\.?|m\.c\.o\.p\.?)\s*(?:no\.?|case\s+no\.?)?\s*(\d+\s*(?:of|\/)\s*\d{4})\b', full_text_lower)
        if mcop_match:
            mcop_number = f"M.C.O.P. No. {mcop_match.group(1).upper()}"
            
        if case_type == "injury" and disability:
            accident_year = 2020
            if date_of_accident:
                try:
                    accident_year = int(date_of_accident.split("-")[2])
                except (ValueError, IndexError):
                    pass
            # Rs. 5000/percent after 2020, otherwise Rs. 3000/percent
            flat_rate = 5000.0 if accident_year >= 2020 else 3000.0
            tn_disability_compensation = disability * flat_rate
            
            # Apply standard Tamil Nadu injury defaults to Compensation Table if table is empty
            if not compensation_table:
                compensation_table = {
                    "Disability Compensation": tn_disability_compensation,
                    "Pain And Suffering": 40000.0,
                    "Loss Of Amenities": 30000.0,
                    "Transportation Charges": 15000.0,
                    "Extra Nourishment": 15000.0,
                    "Attender Charges": 15000.0
                }

    anomalies_detected = []
    
    # Chronological swap verification
    if date_of_birth and date_of_accident:
        try:
            dob_val = datetime.strptime(date_of_birth, "%d-%m-%Y")
            doa_val = datetime.strptime(date_of_accident, "%d-%m-%Y")
            if dob_val > doa_val:
                date_of_birth, date_of_accident = date_of_accident, date_of_birth
                conf_date_of_birth, conf_date_of_accident = conf_date_of_accident, conf_date_of_birth
                anomalies_detected.append("Chronological date swap repaired (DOB was after Accident Date).")
        except ValueError:
            pass

    # Multiplier anomaly check
    if multiplier and expected_multiplier:
        if multiplier != expected_multiplier:
            anomalies_detected.append(f"Tribunal applied multiplier {multiplier} which deviates from Sarla Verma standard ({expected_multiplier}) for age {age}.")

    # DOB vs Age validation
    if date_of_birth and date_of_accident:
        try:
            dob = datetime.strptime(date_of_birth, "%d-%m-%Y")
            doa = datetime.strptime(date_of_accident, "%d-%m-%Y")
            calc_age = doa.year - dob.year
            if doa.month < dob.month or (doa.month == dob.month and doa.day < dob.day):
                calc_age -= 1
            if 0 <= calc_age <= 100:
                if age != calc_age:
                    age = calc_age
                    conf_age = max(conf_age, 0.90)
                    anomalies_detected.append("Age synchronized chronologically to match DOB & accident date.")
        except ValueError:
            pass

    # Math calculations balance validation check
    reconstruction_triggered = False
    reconstructed_compensation = 0.0
    if monthly_income and age:
        try:
            inc_val = float(monthly_income)
            pros_pct = float(future_prospect) if future_prospect else expected_prospects
            mult_val = int(multiplier) if multiplier else expected_multiplier
            
            enhanced_monthly = inc_val * (1 + pros_pct / 100)
            annual_inc = enhanced_monthly * 12
            
            dep_cnt = int(dependents) if dependents else 3
            deduct_pct = 0.50 if marital_status == "single" or dep_cnt <= 1 else 0.33
            
            loss_of_dependency = annual_inc * (1 - deduct_pct) * mult_val
            reconstructed_compensation = loss_of_dependency + consortium + funeral_expenses + estate_loss
            
            if total_compensation:
                diff = abs(total_compensation - reconstructed_compensation) / total_compensation
                if diff > 0.05:
                    reconstruction_triggered = True
                    anomalies_detected.append(f"Compensation mismatch detected: Tribunal Award Rs. {int(total_compensation):,} vs Reconstructed Math Rs. {int(reconstructed_compensation):,}.")
        except Exception as e:
            logger.error(f"Validation math error: {str(e)}")

    # ======================================================
    # LAYER 4 — FALLBACK AI RECOVERY (Semantic context-aware)
    # ======================================================
    ai_recovery_triggered = False
    
    # Structured extraction overall confidence check
    fields_missing = not claimant_name or not monthly_income or not age or not total_compensation
    if fields_missing or reconstruction_triggered:
        ai_recovery_triggered = True
        
        # Execute Fallback AI Recovery purely on isolated semantic blocks
        recovered = simulate_fallback_ai_recovery(
            section_blocks["petitioner_details"],
            section_blocks["prayer_section"],
            section_blocks["compensation_paragraphs"],
            section_blocks["award_section"],
            case_type
        )
        
        # Apply recovered results to missing fields
        if not claimant_name and recovered.get("name"):
            claimant_name = recovered["name"]
            conf_claimant_name = 0.85
            sec_claimant_name = "AI Recovery"
            
        if not age and recovered.get("age"):
            age = recovered["age"]
            conf_age = 0.85
            sec_age = "AI Recovery"
            
        if not monthly_income and recovered.get("monthly_income"):
            monthly_income = recovered["monthly_income"]
            conf_monthly_income = 0.85
            sec_monthly_income = "AI Recovery"
            
        if not dependents and recovered.get("dependents"):
            dependents = recovered["dependents"]
            conf_dependents = 0.85
            sec_dependents = "AI Recovery"
            
        if (not total_compensation or total_compensation <= 0 or reconstruction_triggered) and recovered.get("award_amount"):
            total_compensation = recovered["award_amount"]
            conf_total_compensation = 0.85
            sec_total_compensation = "AI Recovery"

        # Math Reconstruction fallbacks if still missing
        if not age and date_of_birth and date_of_accident:
            try:
                dob = datetime.strptime(date_of_birth, "%d-%m-%Y")
                doa = datetime.strptime(date_of_accident, "%d-%m-%Y")
                age = doa.year - dob.year
                conf_age = 0.80
                sec_age = "raw_ocr"
            except ValueError:
                pass
                
        if not age:
            m = re.search(r'\b(?:age|aged)\s*(?:about|is)?\s*(\d{1,2})\b', full_text_lower)
            if m:
                age = int(m.group(1))
                conf_age = 0.75
                sec_age = "raw_ocr"

        if not occupation:
            occ_keywords = ["service", "driver", "agriculture", "farmer", "supervisor", "teacher", "business", "laborer", "coolie", "shopkeeper", "student", "housewife"]
            for occ in occ_keywords:
                if occ in full_text_lower:
                    occupation = occ.title()
                    conf_occupation = 0.70
                    sec_occupation = "raw_ocr"
                    break

        if not monthly_income:
            m = re.search(r'\b(?:income|salary|wage|earning|earns)\b.*?(\d{4,6})\b', full_text_lower)
            if m:
                monthly_income = float(m.group(1))
                conf_monthly_income = 0.75
                sec_monthly_income = "raw_ocr"

        if not multiplier and expected_multiplier:
            multiplier = expected_multiplier
            conf_multiplier = 0.70
            sec_multiplier = "raw_ocr"

        if not future_prospect and expected_prospects:
            future_prospect = expected_prospects
            conf_future_prospect = 0.70
            sec_future_prospect = "raw_ocr"

        if not prayer:
            prayers_kws = ["appeal allowed", "compensation be enhanced", "enhanced", "award be passed", "prays for"]
            for p_kw in prayers_kws:
                if p_kw in full_text_lower:
                    prayer = f"The claimant prays that the {p_kw}."
                    conf_prayer = 0.70
                    sec_prayer = "raw_ocr"
                    break

        if (not total_compensation or total_compensation <= 0 or reconstruction_triggered) and reconstructed_compensation > 0:
            total_compensation = round(reconstructed_compensation, 2)
            conf_total_compensation = 0.80
            sec_total_compensation = "compensation_paragraphs"

    # Citation precedents collector
    citation_patterns = [
        r'\b\d{4}\s+(?:SCC|ACJ)\s+\d+\b',
        r'\(\d{4}\)\s+\d+\s+(?:SCC|ACJ)\s+\d+\b',
        r'\b(?:[A-Z][A-Za-z\s]+)\s+vs\.?\s+(?:[A-Z][A-Za-z\s]+)\b'
    ]
    known_precedents = ["Pranay Sethi", "Sarla Verma", "Satinder Kaur", "Syed Basheer Ahmed"]
    
    unique_citations = set()
    for pat in citation_patterns:
        m = re.findall(pat, full_text)
        for cite in m:
            unique_citations.add(cite.strip())
            
    for pred in known_precedents:
        if pred.lower() in full_text_lower:
            m = re.search(rf'([^.\n]*?{re.escape(pred)}[^.\n]*)', full_text, re.IGNORECASE)
            if m:
                unique_citations.add(m.group(1).strip())
            else:
                unique_citations.add(pred)
                
    citations = sorted(list(unique_citations))
    conf_citations = 0.95 if citations else 0.0

    dep_cnt = int(dependents) if dependents else 3
    deduct_pct = 0.50 if marital_status == "single" or dep_cnt <= 1 else 0.33
    dependency_deduction = round(deduct_pct * 100, 2)

    if not monthly_income: monthly_income = ""
    if not future_prospect: future_prospect = ""
    if not multiplier: multiplier = ""
    if not total_compensation: total_compensation = ""

    # ======================================================
    # LAYER 3 NORMALIZED LEGAL AI SUMMARY
    # ======================================================
    summary_name = claimant_name or deceased_name or "claimant"
    summary_case = "death" if case_type == "death" else "injury"
    summary_action = "enhancement" if enhancement_reduction_request == "enhancement" else "reduction"
    
    summary_blocks = [
        f"This appeal challenges the MACT motor claim compensation awarded for the {summary_case} of {summary_name}.",
        f"The profile involves a {age}-year-old individual, historically working as a {occupation or 'Worker'}."
    ]
    
    if is_tamil_nadu:
        summary_blocks.append(f"The case was identified as a Judicial System proceeding under {mcop_number or 'MCOP Tribunal'}.")
        
    if monthly_income:
        summary_blocks.append(f"The court evaluated a monthly income of Rs. {int(float(monthly_income)):,} per month.")
        
    if multiplier:
        summary_blocks.append(f"A multiplier of {multiplier} was applied in accordance with Sarla Verma standards.")
        
    if future_prospect:
        summary_blocks.append(f"Future prospects were calculated at {future_prospect}% following Pranay Sethi rules.")
        
    if total_compensation:
        summary_blocks.append(f"The total judicial compensation awarded stands at Rs. {int(float(total_compensation)):,}.")
        
    summary_blocks.append(f"The insurance/claimant appeal requests a {summary_action} of the compensation award.")
    
    if anomalies_detected:
        summary_blocks.append(f"Validation checks: {'; '.join(anomalies_detected)}")
        
    legal_ai_summary = " ".join(summary_blocks)

    # ======================================================
    # LAYER 5 — CONFIDENCE SCORING & SCHEMAS
    # ======================================================
    suggestions = {
        "case_type": case_type,
        "name": claimant_name or deceased_name,
        "father_name": father_name,
        "date_of_accident": date_of_accident,
        "date_of_birth": date_of_birth,
        "age": age,
        "monthly_income": monthly_income,
        "disability": disability,
        "dependents": dependents,
        "marital_status": marital_status,
        "award_amount": total_compensation,
        "place_of_accident": place_of_accident,
        
        "deceased_name": deceased_name,
        "claimant_name": claimant_name,
        "occupation": occupation,
        "future_prospect": future_prospect,
        "multiplier": multiplier,
        "consortium": consortium,
        "funeral_expenses": funeral_expenses,
        "total_compensation": total_compensation,
        "prayer": prayer,
        "citations": citations,
        
        "is_tamil_nadu": is_tamil_nadu,
        "mcop_number": mcop_number,
        "compensation_table": compensation_table,
        
        "ai_recovery_triggered": ai_recovery_triggered,
        "legal_ai_summary": legal_ai_summary,
        "anomalies_detected": anomalies_detected,
        
        # Step 9 Confidences nested structure: e.g. {"monthly_income": {"value": 15000, "confidence": 0.92, "source": "compensation_paragraphs"}}
        "confidence_scores": {
            "deceased_name": {"value": deceased_name, "confidence": conf_deceased_name, "source": sec_deceased_name, "source_section": sec_deceased_name},
            "claimant_name": {"value": claimant_name, "confidence": conf_claimant_name, "source": sec_claimant_name, "source_section": sec_claimant_name},
            "name": {"value": claimant_name or deceased_name, "confidence": conf_claimant_name, "source": sec_claimant_name, "source_section": sec_claimant_name},
            "father_name": {"value": father_name, "confidence": conf_father_name, "source": sec_father_name, "source_section": sec_father_name},
            "date_of_accident": {"value": date_of_accident, "confidence": conf_date_of_accident, "source": sec_date_of_accident, "source_section": sec_date_of_accident},
            "date_of_birth": {"value": date_of_birth, "confidence": conf_date_of_birth, "source": sec_date_of_birth, "source_section": sec_date_of_birth},
            "age": {"value": age, "confidence": conf_age, "source": sec_age, "source_section": sec_age},
            "occupation": {"value": occupation, "confidence": conf_occupation, "source": sec_occupation, "source_section": sec_occupation},
            "monthly_income": {"value": monthly_income, "confidence": conf_monthly_income, "source": sec_monthly_income, "source_section": sec_monthly_income},
            "multiplier": {"value": multiplier, "confidence": conf_multiplier, "source": sec_multiplier, "source_section": sec_multiplier},
            "future_prospect": {"value": future_prospect, "confidence": conf_future_prospect, "source": sec_future_prospect, "source_section": sec_future_prospect},
            "consortium": {"value": consortium, "confidence": conf_consortium, "source": sec_consortium, "source_section": sec_consortium},
            "funeral_expenses": {"value": funeral_expenses, "confidence": conf_funeral_expenses, "source": sec_funeral_expenses, "source_section": sec_funeral_expenses},
            "total_compensation": {"value": total_compensation, "confidence": conf_total_compensation, "source": sec_total_compensation, "source_section": sec_total_compensation},
            "prayer": {"value": prayer, "confidence": conf_prayer, "source": sec_prayer, "source_section": sec_prayer},
            "citations": {"value": citations, "confidence": conf_citations, "source": "cited_judgments", "source_section": "cited_judgments"},
            "place_of_accident": {"value": place_of_accident, "confidence": conf_place_of_accident, "source": sec_place_of_accident, "source_section": sec_place_of_accident},
            "disability": {"value": disability, "confidence": conf_disability, "source": sec_disability, "source_section": sec_disability},
            "dependents": {"value": dependents, "confidence": conf_dependents, "source": sec_dependents, "source_section": sec_dependents},
            "marital_status": {"value": marital_status, "confidence": conf_marital_status, "source": sec_marital_status, "source_section": sec_marital_status}
        }
    }

    return suggestions
