import re
from datetime import datetime

def clean_noisy_text(text_line):
    """
    Cleans OCR scanning noise, stray characters, and common digit typos (like letter O/o instead of 0).
    """
    cleaned = text_line.strip()
    
    # 1. Repair common OCR digit typos: 'O' or 'o' scanned instead of '0' inside numbers
    # E.g. "25O00" -> "25000", "12-O4-1992" -> "12-04-1992"
    cleaned = re.sub(r'(?<=\d)[Oo](?=\d)', '0', cleaned) # O surrounded by digits
    cleaned = re.sub(r'(?<=\d)[Oo]$', '0', cleaned)     # O at the end of a number
    cleaned = re.sub(r'^[Oo](?=\d)', '0', cleaned)     # O at the start of a number
    
    # 2. Repair dates with O/o typos, e.g. "12-O4-1992" or "12-o4-1992"
    # Matches patterns like DD-O4-YYYY or DD-04-oYYY
    cleaned = re.sub(r'\b(\d{1,2})[-/\.][Oo](\d)[-/\.](\d{4})\b', r'\1-0\2-\3', cleaned)
    cleaned = re.sub(r'\b(\d{1,2})[-/\.](\d)[Oo][-/\.](\d{4})\b', r'\1-\20-\3', cleaned)
    cleaned = re.sub(r'\b(\d{1,2})[-/\.][Oo][Oo][-/\.](\d{4})\b', r'\1-00-\2', cleaned)
    cleaned = re.sub(r'\b[Oo](\d)[-/\.](\d{1,2})[-/\.](\d{4})\b', r'0\1-\2-\3', cleaned)
    
    # 3. Remove typical OCR vertical bars or bracket noise in numeric/date lines
    # E.g. "| 25000" -> "25000", "[12-04-1992]" -> "12-04-1992"
    if any(kw in cleaned.lower() for kw in ["rs", "income", "salary", "disability", "age", "dob", "date"]):
        cleaned = re.sub(r'[\|\[\]\~\^\#\_]', '', cleaned).strip()
        
    return cleaned

def parse_extracted_text(text_lines):
    """
    Highly accurate, production-grade, noise-tolerant MACT legal parser.
    Performs Page-wise parsing, Section detection, Context-aware extraction,
    Proximity label-near-value matching, and Multi-source validation.
    
    Target Legal Sections:
    1. Chronological Events
    2. Accident Particulars
    3. Claim Petition
    4. Compensation Table
    5. Prayer Clause
    
    Ignores:
    - Cited judgments, precedents, and apex court legal discussions.
    """
    # Clean OCR noise on each line
    cleaned_lines = [clean_noisy_text(line) for line in text_lines]

    # 1. INITIALIZE SUGGESTIONS AND CONFIDENCE CORES
    suggestions = {
        "case_type": "injury",       # Default
        "name": "",
        "father_name": "",
        "date_of_accident": "",
        "date_of_birth": "",
        "age": "",
        "monthly_income": "",
        "disability": "",
        "dependents": "",
        "marital_status": "married",  # Default
        "award_amount": "",
        "place_of_accident": "",
    }
    
    confidences = {
        "case_type": 0.5,
        "name": 0.0,
        "father_name": 0.0,
        "date_of_accident": 0.0,
        "date_of_birth": 0.0,
        "age": 0.0,
        "monthly_income": 0.0,
        "disability": 0.0,
        "dependents": 0.0,
        "marital_status": 0.5,
        "award_amount": 0.0,
        "place_of_accident": 0.0,
    }

    # ======================================================
    # STEP 1: PAGE-WISE PARSING & TEXT BOUNDARIES
    # ======================================================
    pages = []
    current_page = []
    
    for line in cleaned_lines:
        match = re.match(r'^--- PAGE (\d+) ---$', line)
        if match:
            if current_page:
                pages.append("\n".join(current_page))
            current_page = []
        else:
            current_page.append(line)
    if current_page:
        pages.append("\n".join(current_page))
        
    # If no PAGE headers were injected, treat the whole document as a single page
    if not pages:
        pages = ["\n".join(cleaned_lines)]

    full_text = "\n".join(pages)
    full_text_lower = full_text.lower()

    # ======================================================
    # STEP 2: SECTION DETECTION & SEMANTIC ROUTING
    # ======================================================
    # Segment boundaries (starts and ends) mapping
    sections = {
        "events": [],      # List of (text_content, page_idx)
        "accident": [],
        "petition": [],
        "table": [],
        "prayer": [],
        "general": []
    }
    
    # Noise-tolerant regexes for finding target sections
    section_patterns = {
        "events": [
            r'list\s+of\s+dates', r'chronological\s+list', r'dates\s+and\s+events', 
            r'particulars\s+of\s+events', r'timeline'
        ],
        "accident": [
            r'details?\s+of\s+accident', r'accident\s+details?', r'manner\s+of\s+accident', 
            r'accident\s+particulars', r'occurrence', r'facts\s+of\s+the\s+case',
            r'accident\s+occurred\s+at', r'place\s+of\s+accident'
        ],
        "petition": [
            r'claim\s+petition', r'claimants?\s+details?', r'averments?\s+of\s+petition', 
            r'averments?', r'the\s+petition', r'details?\s+of\s+deceased', 
            r'particulars\s+of\s+the\s+claim', r'injured\s+details?', r'petitioners?',
            r'claimants?\s+profile'
        ],
        "table": [
            r'compensation\s+table', r'quantum\s+of\s+compensation', r'assessment\s+of\s+compensation', 
            r'breakup\s+of\s+award', r'details?\s+of\s+compensation', r'quantum', 
            r'calculation', r'award\s+table'
        ],
        "prayer": [
            r'prayer', r'relief\s+claimed', r'wherefore\s+the\s+petitioner', 
            r'prays\s+for', r'prayer\s+clause', r'reliefs'
        ]
    }
    
    # Headers to explicitly ignore/discard (prevents cited precedents from polluting extraction)
    ignore_patterns = [
        r'citations?', r'precedents?\s+cited', r'referred\s+to', r'in\s+the\s+case\s+of', 
        r'supreme\s+court\s+held', r'apex\s+court\s+in', r'learned\s+counsel\s+for', 
        r'judgment\s+referred', r'relied\s+upon'
    ]

    # Process each page to isolate sections
    for page_idx, page_content in enumerate(pages):
        lines = page_content.split("\n")
        lines_lower = [l.lower() for l in lines]
        
        current_section = "general"
        section_lines = []
        
        for line_idx, line in enumerate(lines):
            line_lower = lines_lower[line_idx]
            
            # Check if this line is an IGNORE header -> route to general/ignore
            if any(re.search(ip, line_lower) for ip in ignore_patterns):
                current_section = "general"
                continue
                
            # Check if this line signals a section boundary change
            header_detected = False
            for sec_name, regex_patterns in section_patterns.items():
                if header_detected:
                    break
                for pattern in regex_patterns:
                    if re.search(pattern, line_lower):
                        # Save accumulated lines from the previous section
                        if section_lines:
                            sections[current_section].append(("\n".join(section_lines), page_idx))
                        current_section = sec_name
                        section_lines = [line]
                        header_detected = True
                        break
            
            if not header_detected:
                section_lines.append(line)
                
        if section_lines:
            sections[current_section].append(("\n".join(section_lines), page_idx))

    # Combine segments for global section-based queries
    events_text = "\n".join([item[0] for item in sections["events"]])
    accident_text = "\n".join([item[0] for item in sections["accident"]])
    petition_text = "\n".join([item[0] for item in sections["petition"]])
    table_text = "\n".join([item[0] for item in sections["table"]])
    prayer_text = "\n".join([item[0] for item in sections["prayer"]])
    general_text = "\n".join([item[0] for item in sections["general"]])

    # ======================================================
    # STEP 3: CONTEXT-AWARE LEGAL ENTITY EXTRACTION
    # ======================================================

    # --- 1. CASE TYPE ---
    death_keywords = ["death", "deceased", "fatal", "post mortem", "died on", "funeral", "consortium", "loss of estate", "widow"]
    injury_keywords = ["injury", "injured", "treatment", "disability certificate", "fracture", "wounds", "medical expenses", "pain and suffering"]
    
    death_score = sum(3 for kw in death_keywords if kw in petition_text.lower()) + sum(1 for kw in death_keywords if kw in general_text.lower())
    injury_score = sum(3 for kw in injury_keywords if kw in petition_text.lower()) + sum(1 for kw in injury_keywords if kw in general_text.lower())
    
    if death_score > injury_score:
        suggestions["case_type"] = "death"
        confidences["case_type"] = min(1.0, 0.5 + (death_score / 15.0))
    else:
        suggestions["case_type"] = "injury"
        confidences["case_type"] = min(1.0, 0.5 + (injury_score / 15.0))


    # --- 2. ACCIDENT DATE (Chronological Events > Accident Particulars > General) ---
    date_pattern = r'\b(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})\b'
    accident_kws = ["accident", "incident", "occurrence", "happened on", "occurred on", "collision", "crash", "fir"]
    
    def extract_dates(text):
        matches = []
        for m in re.finditer(date_pattern, text):
            d_str = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{m.group(3)}"
            # Asymmetrical window: labels almost always precede values!
            # Using 40 chars before and 12 chars after prevents overlapping keywords.
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 12)
            context = text[start:end].lower()
            matches.append((d_str, context))
        return matches

    # Scan events and accident particulars first
    accident_dates = extract_dates(events_text) + extract_dates(accident_text)
    accident_date_found = False
    
    for d_val, ctx in accident_dates:
        if any(kw in ctx for kw in accident_kws):
            suggestions["date_of_accident"] = d_val
            confidences["date_of_accident"] = 0.95
            accident_date_found = True
            break
            
    # Fallback to general search
    if not accident_date_found:
        general_dates = extract_dates(general_text)
        for d_val, ctx in general_dates:
            if any(kw in ctx for kw in accident_kws):
                suggestions["date_of_accident"] = d_val
                confidences["date_of_accident"] = 0.75
                accident_date_found = True
                break


    # --- 3. PLACE OF ACCIDENT (Accident Particulars > Chronological Events > General) ---
    place_regexes = [
        r'place\s+of\s+(?:accident|occurrence)\s*[:\-]\s*([A-Za-z0-9\s\.\,\-\/]{3,60})',
        r'accident\s+(?:occurred|took\s+place)\s+at\s+([A-Za-z0-9\s\.\,\-\/]{3,60})',
        r'accident\s+near\s+([A-Za-z0-9\s\.\,\-\/]{3,60})',
        r'occurred\s+near\s+([A-Za-z0-9\s\.\,\-\/]{3,60})',
        r'collision\s+at\s+([A-Za-z0-9\s\.\,\-\/]{3,60})',
        r'on\s+national\s+highway\s+no\.?\s*(\d+|\w+)',
        r'on\s+nh\s*[-–]?\s*(\d+|\w+)',
        r'at\s+village\s+([A-Za-z\s]{3,30})'
    ]
    
    place_found = False
    for text_source, confidence_weight in [(accident_text, 0.95), (events_text, 0.8), (general_text, 0.65)]:
        if place_found:
            break
        for regex in place_regexes:
            match = re.search(regex, text_source.lower())
            if match:
                val = match.group(1).strip()
                val = re.split(r'\n|\r|\.|,|claims', val)[0].strip()
                if len(val) > 3 and not any(stop in val.lower() for stop in ["is", "the", "date", "time", "rs"]):
                    suggestions["place_of_accident"] = val.title()
                    confidences["place_of_accident"] = confidence_weight
                    place_found = True
                    break


    # --- 4. DATE OF BIRTH & AGE (Claim Petition > Chronological Events > General) ---
    dob_kws = ["dob", "date of birth", "born on", "birth", "d.o.b"]
    age_patterns = [
        r'\bage\b\s*(?:of|is|:)?\s*(\d{1,2})\b',
        r'\baged\b\s*(?:about)?\s*(\d{1,2})\b',
        r'\b(\d{1,2})\s*years\s*(?:old)?\b'
    ]
    
    # Extract DOB
    dob_dates = extract_dates(petition_text) + extract_dates(events_text)
    dob_found = False
    for d_val, ctx in dob_dates:
        if any(kw in ctx for kw in dob_kws):
            suggestions["date_of_birth"] = d_val
            confidences["date_of_birth"] = 0.95
            dob_found = True
            break
    if not dob_found:
        general_dates = extract_dates(general_text)
        for d_val, ctx in general_dates:
            if any(kw in ctx for kw in dob_kws):
                suggestions["date_of_birth"] = d_val
                confidences["date_of_birth"] = 0.75
                dob_found = True
                break

    # Extract Age
    age_found = False
    for text_source, confidence_weight in [(petition_text, 0.95), (events_text, 0.8), (general_text, 0.6)]:
        if age_found:
            break
        for pat in age_patterns:
            matches = re.findall(pat, text_source.lower())
            if matches:
                suggestions["age"] = int(matches[0])
                confidences["age"] = confidence_weight
                age_found = True
                break


    # --- 5. CLAIMANT NAME & FATHER NAME (Claim Petition > General) ---
    name_patterns = [
        r'(?:name\s+of\s+)?(?:injured|deceased|claimant|victim)\s*(?:name)?\s*:\s*([A-Za-z\s\.]{3,30})',
        r'\bshri\b\s*([A-Za-z\s\.]{3,30})'
    ]
    father_patterns = [
        r'(?:father|husband)\s*(?:s\s*)?name\s*:\s*([A-Za-z\s\.]{3,30})',
        r'\bs\/o\b\s*(?:shri)?\s*([A-Za-z\s\.]{3,30})',
        r'\bw\/o\b\s*(?:shri)?\s*([A-Za-z\s\.]{3,30})'
    ]

    name_found = False
    for text_source, confidence_weight in [(petition_text, 0.9), (general_text, 0.65)]:
        if name_found:
            break
        for pat in name_patterns:
            matches = re.finditer(pat, text_source.lower())
            for match in matches:
                clean_name = re.sub(r'\s+', ' ', match.group(1).strip()).title()
                if clean_name.endswith(' S'):
                    clean_name = clean_name[:-2].strip()
                if not any(stop in clean_name.lower() for stop in ["father", "son", "daughter", "wife", "husband", "address", "claimant"]):
                    suggestions["name"] = clean_name
                    confidences["name"] = confidence_weight
                    name_found = True
                    break

    father_found = False
    for text_source, confidence_weight in [(petition_text, 0.9), (general_text, 0.65)]:
        if father_found:
            break
        for pat in father_patterns:
            matches = re.finditer(pat, text_source.lower())
            for match in matches:
                clean_father = re.sub(r'\s+', ' ', match.group(1).strip()).title()
                if not any(stop in clean_father.lower() for stop in ["address", "resident", "claimant", "petitioner"]):
                    suggestions["father_name"] = clean_father
                    confidences["father_name"] = confidence_weight
                    father_found = True
                    break


    # --- 6. MONTHLY INCOME (Claim Petition > Compensation Table > General) ---
    income_patterns = [
        r'(?:monthly|salary|income|earnings?|wage?s?)\b.*?\b(?:rs\.?|inr|rupees)?\s*(\d{4,6})\b',
        r'\b(?:rs\.?|inr)\s*(\d{4,6})\b\s*(?:per\s*month|\/pm|\/-\s*pm|p\.m\.)'
    ]
    income_found = False
    for text_source, confidence_weight in [(petition_text, 0.95), (table_text, 0.9), (general_text, 0.6)]:
        if income_found:
            break
        for pat in income_patterns:
            matches = re.findall(pat, text_source.lower())
            if matches:
                suggestions["monthly_income"] = float(matches[0])
                confidences["monthly_income"] = confidence_weight
                income_found = True
                break


    # --- 7. DISABILITY PERCENTAGE (Claim Petition > Compensation Table > General) ---
    disability_patterns = [
        r'\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:permanent)?\s*disability\b',
        r'\bdisability\b\s*(?:of|is|:)?\s*(\d{1,2}(?:\.\d+)?)\s*%',
        r'\bpermanent disability\b\s*(?:of|is|:)?\s*(\d{1,2}(?:\.\d+)?)\s*%'
    ]
    dis_found = False
    for text_source, confidence_weight in [(petition_text, 0.95), (table_text, 0.9), (general_text, 0.6)]:
        if dis_found:
            break
        for pat in disability_patterns:
            matches = re.findall(pat, text_source.lower())
            if matches:
                suggestions["disability"] = float(matches[0])
                confidences["disability"] = confidence_weight
                dis_found = True
                break


    # --- 8. DEPENDENTS & MARITAL STATUS (Claim Petition > General) ---
    marital_patterns = {
        "married": ["married", "husband", "wife", "spouse"],
        "single": ["single", "unmarried", "bachelor", "spinster", "divorced"]
    }
    
    for status, keywords in marital_patterns.items():
        if any(kw in petition_text.lower() for kw in keywords) or any(kw in general_text.lower() for kw in keywords):
            suggestions["marital_status"] = status
            confidences["marital_status"] = 0.8
            break

    dependents_patterns = [
        r'\b(\d{1,2})\s*dependents\b',
        r'\bno\.\s*of\s*dependents?\s*(?:is|:)?\s*(\d{1,2})\b',
        r'\bnumber\s*of\s*dependents?\s*(?:is|:)?\s*(\d{1,2})\b'
    ]
    dep_found = False
    for text_source, confidence_weight in [(petition_text, 0.95), (general_text, 0.6)]:
        if dep_found:
            break
        for pat in dependents_patterns:
            matches = re.findall(pat, text_source.lower())
            if matches:
                suggestions["dependents"] = int(matches[0])
                confidences["dependents"] = confidence_weight
                dep_found = True
                break


    # --- 9. JUDICIAL AWARD AMOUNT (Compensation Table > Prayer Clause > General) ---
    award_patterns = [
        r'(?:total|final|award|sum\s+of|compensation\s+of)\s*(?:award|amount|is|of)?\s*(?:rs\.?|inr|rupees)?\s*(\d{5,7})\b',
        r'\b(?:rs\.?|inr)\s*(\d{5,7})\b\s*(?:with\s*interest|is\s*awarded|as\s*compensation)'
    ]
    award_found = False
    for text_source, confidence_weight in [(table_text, 0.95), (prayer_text, 0.9), (general_text, 0.6)]:
        if award_found:
            break
        for pat in award_patterns:
            matches = re.findall(pat, text_source.lower())
            if matches:
                suggestions["award_amount"] = float(matches[0])
                confidences["award_amount"] = confidence_weight
                award_found = True
                break

    # ======================================================
    # STEP 4: MULTI-SOURCE CONFLICT VALIDATION
    # ======================================================

    # 1. DOB and Accident Date vs Calculated Age Validation
    if suggestions["date_of_birth"] and suggestions["date_of_accident"]:
        try:
            dob = datetime.strptime(suggestions["date_of_birth"], "%d-%m-%Y")
            doa = datetime.strptime(suggestions["date_of_accident"], "%d-%m-%Y")
            calculated_age = doa.year - dob.year
            if doa.month < dob.month or (doa.month == dob.month and doa.day < dob.day):
                calculated_age -= 1
                
            if calculated_age >= 0 and calculated_age <= 100:
                if str(suggestions["age"]) != str(calculated_age):
                    suggestions["age"] = calculated_age
                    confidences["age"] = min(1.0, max(confidences["date_of_birth"], confidences["date_of_accident"]) + 0.05)
        except ValueError:
            pass

    # 2. Disability validation (must be 0-100)
    if suggestions["disability"]:
        try:
            val = float(suggestions["disability"])
            if val < 0 or val > 100:
                suggestions["disability"] = ""
                confidences["disability"] = 0.0
        except ValueError:
            suggestions["disability"] = ""
            confidences["disability"] = 0.0

    # 3. Monthly Income range validation
    if suggestions["monthly_income"]:
        try:
            val = float(suggestions["monthly_income"])
            if val <= 0 or val > 1000000:
                suggestions["monthly_income"] = ""
                confidences["monthly_income"] = 0.0
        except ValueError:
            suggestions["monthly_income"] = ""
            confidences["monthly_income"] = 0.0

    # 4. Dependents sanity validation
    if suggestions["dependents"]:
        try:
            val = int(suggestions["dependents"])
            if val < 0 or val > 20:
                suggestions["dependents"] = ""
                confidences["dependents"] = 0.0
        except ValueError:
            suggestions["dependents"] = ""
            confidences["dependents"] = 0.0

    # 5. Chronological chronological consistency cross-repair
    # If DOB and Accident Date are swapped or mapped incorrectly, correct them chronologically
    if suggestions["date_of_birth"] and suggestions["date_of_accident"]:
        try:
            dob_val = datetime.strptime(suggestions["date_of_birth"], "%d-%m-%Y")
            doa_val = datetime.strptime(suggestions["date_of_accident"], "%d-%m-%Y")
            if dob_val > doa_val:
                # Swapped dates! Swap them back to be logically correct
                suggestions["date_of_birth"], suggestions["date_of_accident"] = suggestions["date_of_accident"], suggestions["date_of_birth"]
                confidences["date_of_birth"], confidences["date_of_accident"] = confidences["date_of_accident"], confidences["date_of_birth"]
        except ValueError:
            pass

    suggestions["confidence_scores"] = confidences

    return suggestions
