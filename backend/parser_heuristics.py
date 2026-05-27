import re
import logging
from datetime import datetime

logger = logging.getLogger("ParserHeuristics")


# Dynamic Section Keyword Definitions
HEADING_KEYWORDS = {
    "index_section": [
        "index", "description of documents", "annexure", "table of contents", "index sheet"
    ],
    "chronological_events_section": [
        "chronological events", "date of accident", "claim petition filed", "list of dates", "chronology"
    ],
    "memo_of_appeal_section": [
        "memo of appeal", "grounds of appeal", "relief claimed", "appeal memo"
    ],
    "award_copy_section": [
        "copy of award", "compensation awarded", "total compensation", "award decree", "award is passed", "impugned award"
    ],
    "vakalatnama_section": [
        "vakalatnama", "vakalat", "power of attorney", "memo of appearance"
    ],
    "claimant_section": [
        "claimants", "respondents", "legal representatives", "petitioners", "parties to the", "cause title", "party details"
    ],
    "accident_section": [
        "accident", "manner of accident", "details of accident", "occurrence of accident", "date of accident"
    ],
    "compensation_section": [
        "compensation", "quantum", "assessment of compensation", "heads of claim", "calculation", "loss of dependency"
    ],
    "relief_section": [
        "relief", "prayer", "relief claimed", "prayer clause"
    ],
    "grounds_section": [
        "grounds", "grounds of appeal", "grounds of objection", "grounds of challenge"
    ]
}


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


def extract_section_block(merged_lines, start_keywords, stop_keywords):
    """
    Isolates a standard legal section block based on start and stop keywords.
    Captures lines from a start keyword until a stop keyword is found.
    """
    block_lines = []
    capturing = False
    
    for line in merged_lines:
        line_lower = line.lower()
        
        if not capturing:
            if any(re.search(rf'\b{re.escape(kw)}\b', line_lower) for kw in start_keywords):
                capturing = True
                block_lines.append(line)
                continue
                
        if capturing:
            if any(re.search(rf'\b{re.escape(kw)}\b', line_lower) for kw in stop_keywords):
                break
            block_lines.append(line)
            
    return "\n".join(block_lines) if block_lines else ""


def clean_legal_name(name_str):
    """
    Step 3 — Name Cleaning:
    Removes legal prefixes and filters out non-claimant legal entities.
    Applies Entity Contamination Prevention keywords.
    """
    if not name_str:
        return ""
        
    # Ignore obvious non-person entities or metadata fields
    IGNORE_KEYWORDS = [
        "advocate", "counsel", "judge", "justice", 
        "insurance company", "insurance co", "citation", "referred case", 
        "cited case", "vakalatnama", "scc", "acj"
    ]
    name_lower = name_str.lower()
    if any(kw in name_lower for kw in IGNORE_KEYWORDS):
        return ""
        
    # Reject directly contaminated prefix lines to preserve strict backward compatibility with existing unit tests
    if name_lower.startswith("appellant ") or name_lower.startswith("respondent ") or name_lower.startswith("versus "):
        return ""
        
    # Clean the string by removing legal noise like "versus", "vs.", "appellant", "respondent"
    for vs_pattern in [r'\bversus\b', r'\bvs\b\.?', r'\bv\b\.?']:
        if re.search(vs_pattern, name_lower):
            name_str = re.split(vs_pattern, name_str, flags=re.IGNORECASE)[0].strip()
            name_lower = name_str.lower()
            
    # Remove role suffixes/prefixes safely
    role_patterns = [
        r'\bappellants?\b\.?', r'\brespondents?\b\.?', r'\bclaimants?\b\.?', 
        r'\bpetitioners?\b\.?', r'\bvictims?\b\.?', r'\binjured\b\.?', 
        r'\bdeceased\b\.?', r'\boriginal petitioner\b\.?', r'\bo\.p\b\.?'
    ]
    for role_pat in role_patterns:
        name_str = re.sub(role_pat, '', name_str, flags=re.IGNORECASE).strip()

    # Strip whitespace and common noise characters
    name_str = name_str.strip()
    name_str = re.sub(r'^[\"\’\‘\“\”\s\.\,\-\/]+|[\"\’\‘\“\”\s\.\,\-\/]+$', '', name_str)
    
    # Remove standard titles with case-insensitive word boundaries (optional dot included)
    prefixes = [r'\bshri\b\.?', r'\bsmt\b\.?', r'\bmr\b\.?', r'\bmrs\b\.?', r'\bkumari\b\.?', r'\blate\b\.?']
    for pref in prefixes:
        name_str = re.sub(pref, '', name_str, flags=re.IGNORECASE)
        
    # Remove relationship fragments if they leaked
    name_str = re.sub(r'[\s,\-]+(?:s/o|d/o|w/o|son of|daughter of|wife of).*$', '', name_str, flags=re.IGNORECASE)
    
    # Strip leading/trailing punctuation noise once more after prefix removal
    name_str = re.sub(r'^[\"\’\‘\“\”\s\.\,\-\/]+|[\"\’\‘\“\”\s\.\,\-\/]+$', '', name_str)

    # Normalize spaces
    name_str = re.sub(r'\s+', ' ', name_str).strip()
    
    # If the result is one of the legal roles themselves, discard it
    if name_str.lower() in ["appellant", "respondent", "versus", "vs", "petitioner", "claimant", "deceased", "injured"]:
        return ""
        
    return name_str


def extract_relationship_entities(text):
    """
    Step 4 — Relationship-Aware Entity Splitting:
    Intelligently splits "Claimant Name, S/o Father Name" into claimant_name and father_name,
    applying strict truncation boundaries on each component separately.
    """
    if not text:
        return None
        
    rel_patterns = [
        (r'(.*?)\b(?:s/o|son\s+of)\b\s*(?:shri)?\s*(.*)', "Son of"),
        (r'(.*?)\b(?:d/o|daughter\s+of)\b\s*(?:shri|smt)?\s*(.*)', "Daughter of"),
        (r'(.*?)\b(?:w/o|wife\s+of)\b\s*(?:shri)?\s*(.*)', "Wife of")
    ]
    
    for pat, rel_type in rel_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            c_part = m.group(1).strip()
            f_part = m.group(2).strip()
            
            # Strip typical claimant/petitioner label prefixes from the claimant part
            c_part = re.sub(r'^(?:claimant\s+name|petitioner\s+name|name\s+of\s+injured|name\s+of\s+claimant|name\s+of\s+victim|claimant|petitioner|victim|injured|name)\s*[:\-–\s]+', '', c_part, flags=re.IGNORECASE)
            
            # Apply boundary truncation to avoid leaking trailing fields
            stop_labels = [
                "date of birth", "dob", "d.o.b", "born on", "age", "aged",
                "occupation", "employed as", "working as", "monthly income", "salary",
                "income", "disability", "dependents", "address", "resident of", "marital status"
            ]
            
            # Truncate c_part at stop labels and comma
            for sl in stop_labels:
                sl_match = re.search(r'\b' + re.escape(sl) + r'\b', c_part, re.IGNORECASE)
                if sl_match:
                    c_part = c_part[:sl_match.start()]
            
            c_comma_pos = c_part.find(",")
            if c_comma_pos != -1:
                c_part = c_part[:c_comma_pos]
                
            # Apply boundary truncation to the father part specifically to avoid leaking trailing fields
            # 1. Truncate at comma
            comma_pos = f_part.find(",")
            if comma_pos != -1:
                f_part = f_part[:comma_pos]
                
            # 2. Truncate at newline
            newline_pos = re.search(r'[\r\n]', f_part)
            if newline_pos:
                f_part = f_part[:newline_pos.start()]
                
            # 3. Truncate at Date pattern
            date_pos = re.search(r'\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}\b', f_part)
            if date_pos:
                f_part = f_part[:date_pos.start()]
                
            # 4. Truncate at stop labels
            for sl in stop_labels:
                sl_match = re.search(r'\b' + re.escape(sl) + r'\b', f_part, re.IGNORECASE)
                if sl_match:
                    f_part = f_part[:sl_match.start()]
                    
            c_clean = clean_legal_name(c_part)
            f_clean = clean_legal_name(f_part)
            
            if c_clean and f_clean:
                return c_clean, rel_type, f_clean
                
    return None


def validate_name_confidence(name, current_confidence):
    """
    Step 5 — Confidence Validation:
    Automatically reduces confidence to <= 0.3 if the name contains digit patterns,
    other field keywords, or punctuation overflow (e.g. >= 3 separators).
    """
    if not name:
        return current_confidence
        
    name_lower = name.lower()
    
    # 1. Check for bad keywords
    bad_keywords = ["date", "age", "income", "salary", "disability", "occupation", "dependents", "address"]
    contains_bad_kw = any(kw in name_lower for kw in bad_keywords)
    
    # 2. Check for digits
    contains_digits = bool(re.search(r'\d', name))
    
    # 3. Check for punctuation overflow (>= 3 chars)
    punc_matches = re.findall(r'[.,:\-/\_\\]', name)
    overflow_punc = len(punc_matches) >= 3
    
    if contains_bad_kw or contains_digits or overflow_punc:
        logger.warning(f"Confidence validation failed for name '{name}' (bad kw: {contains_bad_kw}, digits: {contains_digits}, punc: {overflow_punc}). Dropping confidence.")
        return min(current_confidence, 0.30)
        
    return current_confidence


def parse_indian_rupee_value(text):
    """
    Parses and normalises Indian currency text, converting Lakhs, Crores, commas, and suffixes into float.
    E.g. "Rs. 1,50,000/-" -> 150000.0
         "1.5 Lakhs" -> 150000.0
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
    """
    table = {}
    lines = text.split("\n")
    
    valid_heads = ["dependency", "consortium", "funeral", "estate", "pain", "medical", "transport", "nourishment", "attender", "disability", "amenities", "earning", "structure"]
    pattern = r'(?:\d+[\.\)\-]\s*)?([A-Za-z\s&\(\)/\-\’\‘\“\”]+)\s*(?:[:\-–]|\b\.?\s*rs\.?\b)\s*(?:rs\.?|inr)?\s*([\d,\.\s]+lakhs?|[\d,\.\-\/]+)\b'
    
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        m = re.search(pattern, line_clean, re.IGNORECASE)
        if m:
            head = m.group(1).strip()
            head = re.sub(r'\s+', ' ', head).strip()
            
            if len(head) > 3 and any(kw in head.lower() for kw in valid_heads):
                if not any(kw in head.lower() for kw in ["total", "awarded", "interest", "passed", "order", "judgment"]):
                    val = parse_indian_rupee_value(m.group(2))
                    if val > 0:
                        table[head.title()] = val
                    
    return table


def fuzzy_match_heading(line, keywords):
    """Matches a line against a list of fuzzy keywords for heading detection."""
    # Remove list indicators / bullets like '1. ', 'A. ', 'I. ', 'a) ', 'i) '
    line_lower = re.sub(r'^(?:[ivxIVX]+|\d+|[a-zA-Z])[\.\)\-\]]\s*', '', line).strip().lower()
    for kw in keywords:
        kw_lower = kw.lower().strip()
        # 1. Exact match
        if kw_lower == line_lower:
            return True
        # 2. Strict substring match with length threshold to avoid matching inside paragraphs
        if kw_lower in line_lower and len(line_lower) < len(kw_lower) + 12:
            return True
        # 3. Fuzzy sequencing match
        words = kw_lower.split()
        if len(words) > 1:
            pattern = r'.*'.join(re.escape(w) for w in words)
            if re.search(r'^\s*' + pattern, line_lower) and len(line_lower) < len(kw_lower) + 15:
                return True
    return False


def classify_page_fallback(page_text, section_name):
    """Layout fallback classifier for page classification when headings are missing."""
    text_lower = page_text.lower()
    
    if section_name == "index_section":
        return any(w in text_lower for w in ["index", "description of documents", "annexure", "page no"])
        
    elif section_name == "chronological_events_section":
        dates = re.findall(r'\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}\b', page_text)
        return len(dates) >= 2 and any(w in text_lower for w in ["accident", "filed", "petition", "date"])
        
    elif section_name == "claimant_section":
        has_rel = any(w in text_lower for w in ["s/o", "d/o", "w/o", "son of", "wife of"])
        has_parties = any(w in text_lower for w in ["claimant", "petitioner", "versus", "respondent"])
        return has_rel or has_parties
        
    elif section_name == "vakalatnama_section":
        return any(w in text_lower for w in ["vakalatnama", "vakalath", "appoint", "advocate"])
        
    elif section_name == "accident_section":
        return any(w in text_lower for w in ["date of accident", "manner of accident", "accident took place"])
        
    elif section_name == "compensation_section" or section_name == "award_copy_section":
        comp_kws = ["dependency", "multiplier", "consortium", "funeral", "loss of", "pain and suffering", "medical expenses", "rs.", "compensation", "award", "awarded", "disability"]
        comp_hits = sum(1 for kw in comp_kws if kw in text_lower)
        return comp_hits >= 2
        
    elif section_name == "relief_section":
        return any(w in text_lower for w in ["prayer", "relief", "prayed for", "allow the appeal"])
        
    elif section_name == "grounds_section" or section_name == "memo_of_appeal_section":
        return any(w in text_lower for w in ["grounds of appeal", "grounds", "erred in", "failed to appreciate"])
        
    return False


def detect_document_sections(full_text, pages):
    """
    Dynamically identifies sections of the document using semantic heading matching
    and layout fallbacks.
    """
    doc_lines = []
    for p in pages:
        p_num = p["page_number"]
        for line_idx, line in enumerate(p["lines"]):
            cleaned = clean_noisy_text(line)
            if cleaned:
                doc_lines.append({
                    "text": cleaned,
                    "page": p_num,
                    "line_idx": line_idx
                })
                
    # 1. Fuzzy Heading Detection
    detected_headers = []
    for idx, item in enumerate(doc_lines):
        line_text = item["text"]
        page_num = item["page"]
        
        if len(line_text) > 70:
            continue
            
        for sec_name, keywords in HEADING_KEYWORDS.items():
            if fuzzy_match_heading(line_text, keywords):
                detected_headers.append({
                    "section_name": sec_name,
                    "line_idx": idx,
                    "page": page_num
                })
                break
                
    # 2. Section Boundary Detection
    sections = {}
    total_lines = len(doc_lines)
    
    for k, match in enumerate(detected_headers):
        sec_name = match["section_name"]
        start_idx = match["line_idx"]
        start_page = match["page"]
        
        if k + 1 < len(detected_headers):
            next_match = detected_headers[k+1]
            next_start_idx = next_match["line_idx"]
            next_page = next_match["page"]
            
            if next_page > start_page:
                end_page = next_page - 1
                end_idx = start_idx
                for idx in range(start_idx, next_start_idx):
                    if doc_lines[idx]["page"] <= end_page:
                        end_idx = idx
            else:
                end_page = start_page
                end_idx = next_start_idx - 1
        else:
            end_page = pages[-1]["page_number"] if pages else start_page
            end_idx = total_lines - 1
            
        content_lines = [doc_lines[idx]["text"] for idx in range(start_idx, end_idx + 1)]
        content = "\n".join(content_lines)
        
        if sec_name not in sections:
            sections[sec_name] = {
                "section_name": sec_name,
                "start_page": start_page,
                "end_page": end_page,
                "content": content,
                "strong_match": True
            }
        else:
            existing = sections[sec_name]
            existing["start_page"] = min(existing["start_page"], start_page)
            existing["end_page"] = max(existing["end_page"], end_page)
            existing["content"] += "\n" + content
            
    # 3. Fallback Strategy for Missing Sections
    for sec_name in HEADING_KEYWORDS.keys():
        if sec_name not in sections:
            fallback_pages = []
            for p in pages:
                p_text = p["text"]
                if classify_page_fallback(p_text, sec_name):
                    fallback_pages.append(p)
                    
            if fallback_pages:
                start_p = fallback_pages[0]["page_number"]
                end_p = fallback_pages[-1]["page_number"]
                content = "\n".join(p["text"] for p in fallback_pages)
                sections[sec_name] = {
                    "section_name": sec_name,
                    "start_page": start_p,
                    "end_page": end_p,
                    "content": content,
                    "strong_match": False
                }
                
    return sections


def find_exact_page(value, start_page, end_page, pages):
    """Finds the exact page number that contains a value within a page range."""
    if not value:
        return start_page
    val_str = str(value).lower().strip()
    for p in pages:
        p_num = p["page_number"]
        if start_page <= p_num <= end_page:
            if val_str in p["text"].lower():
                return p_num
    return start_page


def score_page_importance(page_text, page_num):
    """
    Computes an importance/confidence score for a page.
    Drastically suppresses priority if legal citation and precedent keywords are matched.
    """
    text_lower = page_text.lower()
    score = 0.5
    
    heading_kws = ["index", "chronological", "appeal", "award", "vakalatnama", "claimant", "accident", "compensation", "relief", "grounds", "prayer"]
    if any(kw in text_lower for kw in heading_kws):
        score += 0.15
        
    if any(kw in text_lower for kw in ["form", "petition under", "s/o", "d/o", "w/o", "aged about"]):
        score += 0.20
        
    dates = re.findall(r'\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}\b', page_text)
    if len(dates) >= 2 and any(kw in text_lower for kw in ["accident", "filed", "passed"]):
        score += 0.20
        
    comp_kws = ["loss of dependency", "multiplier", "consortium", "funeral expenses", "medical expenses", "pain and suffering"]
    if sum(1 for kw in comp_kws if kw in text_lower) >= 2:
        score += 0.25
        
    # Legal Citation Suppression Rule
    citation_patterns = [
        r'\b\d{4}\s+(?:SCC|ACJ)\s+\d+\b',
        r'\(\d{4}\)\s+\d+\s+(?:SCC|ACJ)\s+\d+\b',
        r'\bvs\b',
        r'\bversus\b',
        r'\breported\s+in\b'
    ]
    has_citation = any(re.search(pat, page_text, re.IGNORECASE) for pat in citation_patterns)
    precedent_terms = ["precedent", "judgment", "ruling", "held in", "cited", "referred to", "supreme court", "high court"]
    precedent_count = sum(1 for term in precedent_terms if term in text_lower)
    
    if has_citation or precedent_count >= 3:
        score = 0.10 # Drastic suppression
        
    return min(1.0, max(0.05, round(score, 3)))


def parse_chronological_events(text):
    """
    DATE -> EVENT chronological parser.
    Parses events like:
    25.12.2021 -> Date of accident
    """
    events = {
        "date_of_accident": "",
        "claim_petition_date": "",
        "award_date": ""
    }
    date_pattern = r'\b(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})\b'
    lines = text.split("\n")
    for line in lines:
        m = re.search(date_pattern, line)
        if m:
            try:
                d_str = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{m.group(3)}"
                event_text = line.replace(m.group(0), "").lower().strip()
                event_text = re.sub(r'^[\s\.\:\-\–\—\→\>\|\/\\\t\?]+|[\s\.\:\-\–\—\→\>\|\/\\\t\?]+$', '', event_text)
                
                if any(kw in event_text for kw in ["accident", "collision", "crash", "incident", "occurrence"]):
                    if not events["date_of_accident"]:
                        events["date_of_accident"] = d_str
                elif any(kw in event_text for kw in ["petition filed", "claim petition", "mcop filed", "m.c.o.p", "filed"]):
                    if not events["claim_petition_date"]:
                        events["claim_petition_date"] = d_str
                elif any(kw in event_text for kw in ["award passed", "judgment", "decree", "order", "passed", "disposed"]):
                    if not events["award_date"]:
                        events["award_date"] = d_str
            except ValueError:
                pass
    return events


def extract_compensation_table_fields(section_content):
    """
    Extracts structured compensation fields strictly from the isolated compensation table area.
    """
    fields = {
        "monthly_income": None,
        "future_prospect": None,
        "deduction": None,
        "annual_loss_dependency": None,
        "multiplier": None,
        "funeral_expenses": None,
        "consortium": None,
        "total_compensation": None
    }
    
    lines = section_content.split("\n")
    table_lines = []
    in_table = False
    consecutive_non_table = 0
    
    table_kws = ["dependency", "consortium", "funeral", "estate", "pain", "medical", "transport", "nourishment", "attender", "disability", "amenities", "earning", "multiplier", "prospects", "deduction", "income", "salary", "total", "awarded"]
    
    for line in lines:
        line_lower = line.lower()
        has_kw = any(kw in line_lower for kw in table_kws)
        has_digits = bool(re.search(r'\d', line))
        
        if has_kw and has_digits:
            in_table = True
            table_lines.append(line)
            consecutive_non_table = 0
        elif in_table:
            consecutive_non_table += 1
            if consecutive_non_table > 2:
                if "total" in line_lower:
                    table_lines.append(line)
                break
            else:
                table_lines.append(line)
                
    for line in table_lines:
        line_lower = line.lower()
        
        # Isolate the currency value part (e.g. "Rs. 12,00,000/-") to avoid serial prefix mixup
        val = 0.0
        val_match = re.search(r'(?:rs\.?|inr|rupees)?\s*([\d,]{4,12}(?:\.\d+)?)\s*(?:rs\.?|inr|rupees|\/\-)?', line_lower)
        if val_match:
            val = parse_indian_rupee_value(val_match.group(1))
        
        mult_match = re.search(r'\bmultiplier\b.*?\b(\d{1,2})\b', line_lower)
        if mult_match:
            fields["multiplier"] = int(mult_match.group(1))
            
        pros_pct_match = re.search(r'\bfuture\s+prospects?\b.*?\b(\d{1,2}(?:\.\d+)?)\s*%', line_lower)
        if pros_pct_match:
            fields["future_prospect"] = float(pros_pct_match.group(1))
            
        ded_pct_match = re.search(r'\bdeduction\b.*?\b(\d+(?:\.\d+)?)\s*(?:%|/|\b)', line_lower)
        if ded_pct_match:
            fields["deduction"] = float(ded_pct_match.group(1))
            
        if val > 0:
            if "monthly" in line_lower and ("income" in line_lower or "salary" in line_lower or "earnings" in line_lower):
                fields["monthly_income"] = val
            elif "loss of dependency" in line_lower or "annual loss" in line_lower:
                fields["annual_loss_dependency"] = val
            elif "funeral" in line_lower:
                fields["funeral_expenses"] = val
            elif "consortium" in line_lower:
                fields["consortium"] = val
            elif "total" in line_lower:
                fields["total_compensation"] = val
                
    return fields


def contextual_extract(patterns, sections, priority_list, type_cast=str, default_val=None, field_name=None, debug_info=None, pages=None, sections_metadata=None, page_importances=None):
    """
    Upgraded Contextual Entity Extraction with dynamic section priority and page-importance tracking.
    """
    STOP_LABELS = [
        "date of birth", "dob", "d.o.b", "born on",
        "age", "aged",
        "occupation", "employed as", "working as",
        "monthly income", "salary", "earning", "income",
        "disability", "permanent disability",
        "dependents", "no. of dependents",
        "address", "resident of",
        "marital status",
        "prayer", "relief",
        "award", "awarded",
        "s/o", "d/o", "w/o", "son of", "daughter of", "wife of"
    ]
    
    if debug_info is None:
        debug_info = {}
        
    for sec_name, base_weight in priority_list:
        text = sections.get(sec_name, "")
        if not text:
            continue
            
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                matched_source = m.group(0)
                raw_val = m.group(1).strip()
                
                active_stop_labels = []
                for sl in STOP_LABELS:
                    if field_name == "father_name" and sl in ["s/o", "d/o", "w/o", "son of", "daughter of", "wife of"]:
                        continue
                    active_stop_labels.append(sl)
                    
                truncated_val = raw_val
                stop_token_triggered = "None (EOL/EOF)"
                
                is_text_field = (type_cast == str) and field_name in ["claimant_name", "deceased_name", "father_name", "occupation", "address"]
                
                if is_text_field:
                    comma_pos = truncated_val.find(",")
                    if comma_pos != -1:
                        truncated_val = truncated_val[:comma_pos]
                        stop_token_triggered = ", (comma)"
                        
                newline_pos = re.search(r'[\r\n]', truncated_val)
                if newline_pos:
                    truncated_val = truncated_val[:newline_pos.start()]
                    stop_token_triggered = "Newline boundary"
                    
                date_pos = re.search(r'\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4}\b', truncated_val)
                if date_pos:
                    truncated_val = truncated_val[:date_pos.start()]
                    stop_token_triggered = f"Date pattern ({date_pos.group(0)})"
                    
                for sl in active_stop_labels:
                    sl_match = re.search(r'\b' + re.escape(sl) + r'\b', truncated_val, re.IGNORECASE)
                    if sl_match:
                        if sl_match.start() < len(truncated_val):
                            truncated_val = truncated_val[:sl_match.start()]
                            stop_token_triggered = f"Stop label '{sl}'"
                            
                if is_text_field:
                    num_meta_match = re.search(r'\b\d+\s*(?:years|yrs|percent|%|\b)', truncated_val, re.IGNORECASE)
                    if num_meta_match:
                        truncated_val = truncated_val[:num_meta_match.start()]
                        stop_token_triggered = f"Numeric metadata boundary ({num_meta_match.group(0)})"
                        
                final_val = re.sub(r'\s+', ' ', truncated_val).strip()
                if is_text_field:
                    final_val = clean_legal_name(final_val)
                    
                if field_name:
                    debug_info[field_name] = {
                        "matched_source_text": matched_source.strip(),
                        "regex_used": pat,
                        "stop_token_triggered": stop_token_triggered,
                        "raw_captured": raw_val.strip(),
                        "final_extracted": final_val
                    }
                    
                # Determine source page
                sec_meta = sections_metadata.get(sec_name, {}) if sections_metadata else {}
                start_p = sec_meta.get("start_page", 1)
                end_p = sec_meta.get("end_page", 1)
                matched_page = find_exact_page(final_val, start_p, end_p, pages) if pages else start_p
                
                # Base confidence score
                confidence = round(base_weight / 100.0, 2)
                
                # Boost confidence if the section is strongly matched
                if sec_meta.get("strong_match", False):
                    confidence = min(0.99, confidence + 0.15)
                    
                # Boost confidence for early pages
                if matched_page <= 3:
                    confidence = min(0.99, confidence + 0.10)
                else:
                    confidence = max(0.10, confidence - 0.15)
                    
                # Adjust confidence based on Page Importance / Suppression
                if page_importances and matched_page in page_importances:
                    page_importance = page_importances[matched_page]
                    if page_importance <= 0.15:
                        confidence = max(0.05, confidence - 0.40)
                    else:
                        confidence = min(0.99, confidence * (0.5 + 0.5 * page_importance))
                        
                if is_text_field:
                    confidence = validate_name_confidence(final_val, confidence)
                    
                if type_cast == float:
                    val = parse_indian_rupee_value(final_val)
                    if val > 0:
                        return val, round(confidence, 2), sec_name, matched_page
                elif type_cast == int:
                    digit_match = re.search(r'\d+', final_val)
                    if digit_match:
                        try:
                            val = int(digit_match.group(0))
                            return val, round(confidence, 2), sec_name, matched_page
                        except ValueError:
                            pass
                else:
                    if len(final_val) > 2:
                        return final_val, round(confidence, 2), sec_name, matched_page
                        
    fallback_confidence = 0.30
    return default_val, fallback_confidence, "raw_ocr", 1


def real_text_recovery(petitioner_details, prayer_section, compensation_paragraphs, award_section, case_type):
    """
    Layer 4: Real-Text Recovery.
    """
    logger.info("Executing Real-Text Recovery on isolated sections...")
    recovered = {}

    name_m = re.search(r'\b(?:injured|deceased|claimant|petitioner|late shri|late smt|shri|smt|mr|mrs|kumari)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', petitioner_details)
    if name_m:
        recovered["name"] = name_m.group(1).strip()

    age_m = re.search(r'\b(?:age|aged|approximately)\s*(\d{1,2})\b', petitioner_details + " " + compensation_paragraphs)
    if age_m:
        recovered["age"] = int(age_m.group(1))

    # Extremely robust monthly income extraction that handles commas and currencies
    inc_m = re.search(r'\b(?:monthly\s+income|salary|earning|coolie|wages?)\b\s*(?:is|was|of|@)?\s*(?:rs\.?|inr|rupees)?\s*([\d,]{4,10})\b', compensation_paragraphs, re.IGNORECASE)
    if not inc_m:
        # Fallback regex with broad search
        inc_m = re.search(r'\b(?:monthly\s+income|salary|earning|coolie|wages?)\b.*?([\d,]{4,10})\b', compensation_paragraphs, re.IGNORECASE)
        
    if inc_m:
        recovered["monthly_income"] = parse_indian_rupee_value(inc_m.group(1))

    dep_m = re.search(r'\b(\d{1,2})\s*(?:dependents?|family\s+members)\b', petitioner_details)
    if dep_m:
        recovered["dependents"] = int(dep_m.group(1))

    # Extremely robust award amount extraction that handles commas and currencies
    aw_m = re.search(r'\b(?:awarded|compensation|award|sum\s+of)\s*(?:of|is|was|amounting\s+to)?\s*(?:rs\.?|inr|rupees)?\s*([\d,]{5,11})\b', award_section, re.IGNORECASE)
    if not aw_m:
        # Fallback regex with broad search
        aw_m = re.search(r'\b(?:awarded|compensation\s+of\s+rs\.?|tribunal\s+awards)\s*([\d,\.]+)\b', award_section, re.IGNORECASE)
        
    if aw_m:
        recovered["award_amount"] = parse_indian_rupee_value(aw_m.group(1))

    return recovered


def extract_dates_with_context(text):
    date_pattern = r'\b(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})\b'
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


def parse_extracted_text(text_lines):
    """
    Highly advanced Section-Aware Legal Semantic Parser / Legal Document Intelligence Engine.
    Uses fuzzy heading matching, dynamic section boundary detection, fallback layout-hint clustering,
    section priority rules, entity contamination filters, page importance/citation suppression,
    chronological parsing, compensation table extraction, and detailed confidence tracking.
    """
    # 1. Segment text_lines into pages
    pages = []
    current_page_num = 1
    current_page_lines = []
    
    for line in text_lines:
        line_strip = line.strip()
        if line_strip.startswith("--- PAGE"):
            if current_page_lines:
                pages.append({
                    "page_number": current_page_num,
                    "lines": current_page_lines,
                    "text": "\n".join(current_page_lines)
                })
            m = re.search(r'PAGE\s+(\d+)', line_strip, re.IGNORECASE)
            if m:
                current_page_num = int(m.group(1))
            current_page_lines = []
        else:
            current_page_lines.append(line)
            
    if current_page_lines or not pages:
        pages.append({
            "page_number": current_page_num,
            "lines": current_page_lines,
            "text": "\n".join(current_page_lines)
        })

    # 2. Compute Page Importances & Legal Citation Suppression
    page_importances = {}
    for p in pages:
        page_importances[p["page_number"]] = score_page_importance(p["text"], p["page_number"])

    # 3. Dynamic Section Detection & Boundary Determination
    merged_lines = merge_ocr_lines_to_paragraphs(text_lines)
    full_text = "\n".join(merged_lines)
    full_text_lower = full_text.lower()
    
    sections_metadata = detect_document_sections(full_text, pages)
    sections = {name: info["content"] for name, info in sections_metadata.items()}
    sections["raw_ocr"] = full_text

    # Populate backward-compatible blocks
    petition_block = sections.get("claimant_section", "") or sections.get("chronological_events_section", "") or sections.get("accident_section", "")
    prayer_block = sections.get("relief_section", "")
    award_block = sections.get("compensation_section", "") or sections.get("award_copy_section", "")
    
    total_lines = len(merged_lines)
    if not petition_block:
        cutoff = max(10, int(total_lines * 0.35))
        petition_block = "\n".join(merged_lines[:cutoff])
        
    if not prayer_block:
        start_idx = int(total_lines * 0.3)
        end_idx = int(total_lines * 0.7)
        prayer_block = "\n".join(merged_lines[start_idx:end_idx])
        
    if not award_block:
        start_idx = int(total_lines * 0.6)
        award_block = "\n".join(merged_lines[start_idx:])

    # Helper for contextual extraction parameters
    parser_debug = {}

    # ======================================================
    # FIELD EXTRACTION WITH SECTION PRIORITIZATION & CONTAMINATION FILTERS
    # ======================================================

    # 1. Claimant Name extraction
    claimant_patterns = [
        r'^(?:\d+[\.\)\-]\s*)?\b(?:claimant|injured|victim)\b\s*(?:name)?\s*[:\-]\s*(.*)',
        r'\b(?:name\s+of\s+)(?:claimant|injured|victim)\b\s*[:\-]\s*(.*)',
        r'^(?:\d+[\.\)\-]\s*)?\bpetitioner\b\s*(?:name)?\s*[:\-]\s*(.*)',
        r'\b(?:name\s+of\s+)petitioner\b\s*[:\-]\s*(.*)',
        r'^(?:\d+[\.\)\-]\s*)?\bappellant\b\s*(?:name)?\s*[:\-]\s*(.*)',
        r'\b(?:name\s+of\s+)appellant\b\s*[:\-]\s*(.*)',
        r'^(?:\d+[\.\)\-]\s*)?\brespondent\b\s*(?:name)?\s*[:\-]\s*(.*)',
        r'\b(?:name\s+of\s+)respondent\b\s*[:\-]\s*(.*)',
        r'\bsmt\b\s*(.*)',
        r'\bshri\b\s*(.*)',
        r'\bmr\b\s*(.*)',
        r'\bmrs\b\s*(.*)',
        r'\bkumari\b\s*(.*)'
    ]
    claimant_name, conf_claimant_name, sec_claimant_name, page_claimant_name = contextual_extract(
        claimant_patterns, sections, [("claimant_section", 90), ("memo_of_appeal_section", 80)], type_cast=str,
        field_name="claimant_name", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_claimant_name = "Section-Aware Contextual Regex"
    if claimant_name: claimant_name = claimant_name.title()

    # 2. Deceased Name extraction
    dec_patterns = [
        r'^(?:\d+[\.\)\-]\s*)?\bdeceased\b\s*(?:name)?\s*[:\-]\s*(.*)',
        r'\b(?:name\s+of\s+)deceased\b\s*[:\-]\s*(.*)',
        r'^(?:\d+[\.\)\-]\s*)?\bdeath\s+of\s+(.*)',
        r'\blate\b\s*(?:shri|smt)?\s*(.*)'
    ]
    deceased_name, conf_deceased_name, sec_deceased_name, page_deceased_name = contextual_extract(
        dec_patterns, sections, [("claimant_section", 90), ("memo_of_appeal_section", 80)], type_cast=str,
        field_name="deceased_name", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_deceased_name = "Section-Aware Contextual Regex"
    if deceased_name: deceased_name = deceased_name.title()

    # Deceased Block Extraction (Page 8 - High Court Factual Details)
    deceased_block_match = re.search(
        r'\b(?:deceased\s+person|description\s+of\s+deceased)\b.*?\b(?:name)\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        full_text,
        re.IGNORECASE | re.DOTALL
    )
    if deceased_block_match:
        deceased_name = deceased_block_match.group(1).strip().title()
        conf_deceased_name = 0.99
        sec_deceased_name = "compensation_section"
        page_deceased_name = find_exact_page(deceased_name, 1, len(pages), pages) if pages else 8
        method_deceased_name = "Deceased Block Extraction"
        parser_debug["deceased_name"] = {
            "matched_source_text": deceased_block_match.group(0).strip(),
            "regex_used": "Deceased Block Extraction (Name)",
            "stop_token_triggered": "Block Match",
            "raw_captured": deceased_block_match.group(1),
            "final_extracted": deceased_name
        }

    # Apply Deceased overrides (Requirement 6)
    if claimant_name and any(kw in claimant_name.lower() for kw in ["late shri", "late smt", "late "]):
        if not deceased_name:
            deceased_name = claimant_name
            conf_deceased_name = conf_claimant_name
            sec_deceased_name = sec_claimant_name
            page_deceased_name = page_claimant_name
            method_deceased_name = method_claimant_name
        claimant_name = None
        conf_claimant_name = 0.0
        sec_claimant_name = "claimant_section"
        page_claimant_name = 1
        method_claimant_name = "Deceased Override Check"

    # 3. Father / Husband Name
    father_patterns = [
        r'(?:father|husband)\s*(?:s\s*)?name\s*[:\-]\s*(.*)',
        r'\bs\/o\b\s*(?:shri)?\s*(.*)',
        r'\bw\/o\b\s*(?:shri)?\s*(.*)'
    ]
    father_name, conf_father_name, sec_father_name, page_father_name = contextual_extract(
        father_patterns, sections, [("claimant_section", 90), ("memo_of_appeal_section", 80)], type_cast=str,
        field_name="father_name", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_father_name = "Section-Aware Contextual Regex"
    if father_name: father_name = father_name.title()

    # Splitting Claimant Inline Relationship
    source_line = sections.get("claimant_section", "")
    split_res = extract_relationship_entities(source_line)
    if split_res:
        c_split, rel_type, f_split = split_res
        if c_split:
            claimant_name = c_split.title()
            conf_claimant_name = max(conf_claimant_name, 0.95)
            sec_claimant_name = "claimant_section"
            method_claimant_name = "Relationship Splitting"
            if "claimant_name" in parser_debug:
                parser_debug["claimant_name"]["final_extracted"] = claimant_name
                parser_debug["claimant_name"]["stop_token_triggered"] = f"Relationship split '{rel_type}'"
        if f_split and (not father_name or len(father_name) < 3 or "date" in father_name.lower()):
            father_name = f_split.title()
            conf_father_name = max(conf_father_name, 0.95)
            sec_father_name = "claimant_section"
            page_father_name = find_exact_page(father_name, 1, 10, pages)
            method_father_name = "Relationship Splitting"
            parser_debug["father_name"] = {
                "matched_source_text": source_line[:200].strip(),
                "regex_used": "Relationship split from Claimant",
                "stop_token_triggered": f"Relationship split '{rel_type}'",
                "raw_captured": f_split,
                "final_extracted": father_name
            }

    # 4. Age only from claimant/petition section or chronological events
    age_patterns = [
        r'(?:aged\s+about|age\s+of\s+deceased|aged|approximately)\s*[:\-]?\s*(\d{1,2})\b',
        r'\b(\d{1,2})\s*years\s*(?:old)?\b'
    ]
    age, conf_age, sec_age, page_age = contextual_extract(
        age_patterns, sections, [("claimant_section", 95), ("chronological_events_section", 80)], default_val="", type_cast=int,
        field_name="age", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_age = "Section-Aware Contextual Regex"

    # Deceased Block Extraction (Age)
    deceased_age_match = re.search(
        r'\b(?:deceased\s+person|description\s+of\s+deceased)\b.*?\b(?:age)\s*[:\-]\s*(\d{1,2})\b',
        full_text,
        re.IGNORECASE | re.DOTALL
    )
    if deceased_age_match:
        age = int(deceased_age_match.group(1))
        conf_age = 0.99
        sec_age = "compensation_section"
        page_age = find_exact_page(str(age), 1, len(pages), pages) if pages else 8
        method_age = "Deceased Block Extraction"
        parser_debug["age"] = {
            "matched_source_text": deceased_age_match.group(0).strip(),
            "regex_used": "Deceased Block Extraction (Age)",
            "stop_token_triggered": "Block Match",
            "raw_captured": deceased_age_match.group(1),
            "final_extracted": age
        }

    # 5. Occupation only from claimant/petition section
    occ_patterns = [
        r'occupation\s*[:\-]\s*(.*)',
        r'employed\s+as\s+(.*)',
        r'working\s+as\s+(.*)',
        r'earning\s+as\s+(.*)'
    ]
    occupation, conf_occupation, sec_occupation, page_occupation = contextual_extract(
        occ_patterns, sections, [("claimant_section", 90), ("memo_of_appeal_section", 80)], default_val="", type_cast=str,
        field_name="occupation", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_occupation = "Section-Aware Contextual Regex"
    if occupation: occupation = occupation.title()

    # Deceased Block Extraction (Occupation)
    deceased_occ_match = re.search(
        r'\b(?:deceased\s+person|description\s+of\s+deceased)\b.*?\b(?:occupation)\s*[:\-]\s*([A-Za-z\s]+)\b',
        full_text,
        re.IGNORECASE | re.DOTALL
    )
    if deceased_occ_match:
        occupation = deceased_occ_match.group(1).strip().title()
        conf_occupation = 0.99
        sec_occupation = "compensation_section"
        page_occupation = find_exact_page(occupation, 1, len(pages), pages) if pages else 8
        method_occupation = "Deceased Block Extraction"
        parser_debug["occupation"] = {
            "matched_source_text": deceased_occ_match.group(0).strip(),
            "regex_used": "Deceased Block Extraction (Occupation)",
            "stop_token_triggered": "Block Match",
            "raw_captured": deceased_occ_match.group(1),
            "final_extracted": occupation
        }

    # 6. Place of accident
    place_regexes = [
        r'place\s+of\s+(?:accident|occurrence)\s*[:\-]\s*(.*)',
        r'accident\s+(?:occurred|took\s+place)\s+at\s+(.*)',
        r'accident\s+near\s+(.*)'
    ]
    place_of_accident, conf_place_of_accident, sec_place_of_accident, page_place_of_accident = contextual_extract(
        place_regexes, sections, [("accident_section", 95), ("chronological_events_section", 90)], default_val="", type_cast=str,
        field_name="place_of_accident", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_place_of_accident = "Section-Aware Contextual Regex"
    if place_of_accident: place_of_accident = place_of_accident.title()

    # 7. Dependents only from claimant/petition section
    dependents_patterns = [
        r'\b(\d{1,2})\s*dependents\b',
        r'\bno\.\s*of\s*dependents?\s*(?:is|:)?\s*(\d{1,2})\b',
        r'\bnumber\s*of\s*dependents?\s*(?:is|:)?\s*(\d{1,2})\b'
    ]
    dependents, conf_dependents, sec_dependents, page_dependents = contextual_extract(
        dependents_patterns, sections, [("claimant_section", 95), ("memo_of_appeal_section", 80)], default_val="", type_cast=int,
        field_name="dependents", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_dependents = "Section-Aware Contextual Regex"

    # 8. Marital Status from claimant section
    marital_status = "married"
    conf_marital_status = 0.50
    sec_marital_status = "raw_ocr"
    page_marital_status = 1
    method_marital_status = "Default Heuristic"
    marital_patterns = {
        "married": ["married", "husband", "wife", "spouse"],
        "single": ["single", "unmarried", "bachelor", "spinster", "divorced"]
    }
    claimant_sec_text = sections.get("claimant_section", "").lower()
    for status, keywords in marital_patterns.items():
        if any(kw in claimant_sec_text for kw in keywords):
            marital_status = status
            conf_marital_status = 0.90
            sec_marital_status = "claimant_section"
            sec_meta = sections_metadata.get("claimant_section", {})
            page_marital_status = find_exact_page(status, sec_meta.get("start_page", 1), sec_meta.get("end_page", 1), pages)
            method_marital_status = "Keyword Matching"
            break

    # ======================================================
    # QUANTITATIVE AND COMPENSATION TABLE EXTRACTION
    # ======================================================

    comp_fields = extract_compensation_table_fields(sections.get("compensation_section", "") or sections.get("award_copy_section", ""))
    
    # 9.1 Monthly Income
    monthly_income = comp_fields["monthly_income"]
    if monthly_income:
        conf_monthly_income = 0.98
        sec_monthly_income = "compensation_section"
        sec_meta = sections_metadata.get("compensation_section", {}) or sections_metadata.get("award_copy_section", {})
        page_monthly_income = find_exact_page(int(monthly_income), sec_meta.get("start_page", 1), sec_meta.get("end_page", 1), pages)
        method_monthly_income = "Compensation Table Extraction"
    else:
        income_patterns = [
            r'(?:monthly\s+income|salary|earning|notional\s+income|coolie|wages?)\s*(?:is|was|of|@)?\s*(?:rs\.?|inr)?\s*([\d,\.\s]+lakhs?|[\d,\.\s]+lacs?|[\d,\.\s]+)\b',
            r'\b(?:rs\.?|inr)?\s*([\d,\.]+)\s*(?:rs\.?|inr)?\s*(?:per\s*month|\/pm|\/-\s*pm|p\.m\.)',
            r'per\s*month\b.*?([\d,\.]+)\b'
        ]
        monthly_income, conf_monthly_income, sec_monthly_income, page_monthly_income = contextual_extract(
            income_patterns, sections, [("compensation_section", 95), ("award_copy_section", 90)], default_val="", type_cast=float,
            field_name="monthly_income", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
        )
        method_monthly_income = "Section-Aware Contextual Regex"

    # 9.2 Multiplier
    multiplier = comp_fields["multiplier"]
    if multiplier:
        conf_multiplier = 0.98
        sec_multiplier = "compensation_section"
        sec_meta = sections_metadata.get("compensation_section", {}) or sections_metadata.get("award_copy_section", {})
        page_multiplier = find_exact_page(int(multiplier), sec_meta.get("start_page", 1), sec_meta.get("end_page", 1), pages)
        method_multiplier = "Compensation Table Extraction"
    else:
        multiplier_patterns = [
            r'multiplier\s*(?:of|is|applied)?\s*(\d{1,2})\b',
            r'applied\s+multiplier\s+of\s*(\d{1,2})\b',
            r'\b(\d{1,2})\s*multiplier\b'
        ]
        multiplier, conf_multiplier, sec_multiplier, page_multiplier = contextual_extract(
            multiplier_patterns, sections, [("compensation_section", 95), ("award_copy_section", 90)], default_val="", type_cast=int,
            field_name="multiplier", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
        )
        method_multiplier = "Section-Aware Contextual Regex"

    # 9.3 Future Prospect
    future_prospect = comp_fields["future_prospect"]
    if future_prospect:
        conf_future_prospect = 0.98
        sec_future_prospect = "compensation_section"
        sec_meta = sections_metadata.get("compensation_section", {}) or sections_metadata.get("award_copy_section", {})
        page_future_prospect = find_exact_page(int(future_prospect), sec_meta.get("start_page", 1), sec_meta.get("end_page", 1), pages)
        method_future_prospect = "Compensation Table Extraction"
    else:
        prospects_patterns = [
            r'future\s+prospects?\s*(?:of|at|is|@)?\s*(\d{1,2})\s*%',
            r'addition\s+of\s*(\d{1,2})\s*%\s*(?:towards)?\s*future\s+prospects'
        ]
        future_prospect, conf_future_prospect, sec_future_prospect, page_future_prospect = contextual_extract(
            prospects_patterns, sections, [("compensation_section", 95), ("award_copy_section", 90)], default_val="", type_cast=float,
            field_name="future_prospect", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
        )
        method_future_prospect = "Section-Aware Contextual Regex"

    # 9.4 Consortium
    consortium = comp_fields["consortium"]
    if consortium:
        conf_consortium = 0.98
        sec_consortium = "compensation_section"
        sec_meta = sections_metadata.get("compensation_section", {}) or sections_metadata.get("award_copy_section", {})
        page_consortium = find_exact_page(int(consortium), sec_meta.get("start_page", 1), sec_meta.get("end_page", 1), pages)
        method_consortium = "Compensation Table Extraction"
    else:
        cons_patterns = [r'consortium\s*(?:of)?\s*(?:rs\.?|inr)?\s*(\d{4,6})\b']
        consortium, conf_consortium, sec_consortium, page_consortium = contextual_extract(
            cons_patterns, sections, [("compensation_section", 95), ("award_copy_section", 90)], default_val=40000.0, type_cast=float,
            field_name="consortium", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
        )
        method_consortium = "Section-Aware Contextual Regex"

    # 9.5 Funeral Expenses
    funeral_expenses = comp_fields["funeral_expenses"]
    if funeral_expenses:
        conf_funeral_expenses = 0.98
        sec_funeral_expenses = "compensation_section"
        sec_meta = sections_metadata.get("compensation_section", {}) or sections_metadata.get("award_copy_section", {})
        page_funeral_expenses = find_exact_page(int(funeral_expenses), sec_meta.get("start_page", 1), sec_meta.get("end_page", 1), pages)
        method_funeral_expenses = "Compensation Table Extraction"
    else:
        fun_patterns = [r'funeral\s*(?:expenses)?\s*(?:of)?\s*(?:rs\.?|inr)?\s*(\d{4,6})\b']
        funeral_expenses, conf_funeral_expenses, sec_funeral_expenses, page_funeral_expenses = contextual_extract(
            fun_patterns, sections, [("compensation_section", 95), ("award_copy_section", 90)], default_val=15000.0, type_cast=float,
            field_name="funeral_expenses", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
        )
        method_funeral_expenses = "Section-Aware Contextual Regex"

    # 9.6 Total Compensation
    total_compensation = comp_fields["total_compensation"]
    if total_compensation:
        conf_total_compensation = 0.98
        sec_total_compensation = "compensation_section"
        sec_meta = sections_metadata.get("compensation_section", {}) or sections_metadata.get("award_copy_section", {})
        page_total_compensation = find_exact_page(int(total_compensation), sec_meta.get("start_page", 1), sec_meta.get("end_page", 1), pages)
        method_total_compensation = "Compensation Table Extraction"
    else:
        award_patterns = [
            r'(?:awarded|compensation\s+of\s+rs\.?|tribunal\s+awards|granted\s+compensation\s+of\s+rs\.?)\s*([\d,\.\s]+lakhs?|[\d,\.\-\/]+)\b',
            r'\b(?:awarded\s+sum\s+of|compensation\s+amount\s+of|total\s+compensation\s+of)\s*(?:rs\.?|inr)?\s*([\d,\.\-\/]+)\b'
        ]
        total_compensation, conf_total_compensation, sec_total_compensation, page_total_compensation = contextual_extract(
            award_patterns, sections, [("compensation_section", 95), ("award_copy_section", 90)], default_val="", type_cast=float,
            field_name="total_compensation", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
        )
        method_total_compensation = "Section-Aware Contextual Regex"

    # 9.7 Disability
    disability_patterns = [
        r'\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:permanent)?\s*disability\b',
        r'\bdisability\b\s*(?:of|is|:)?\s*(\d{1,2}(?:\.\d+)?)\s*%'
    ]
    disability, conf_disability, sec_disability, page_disability = contextual_extract(
        disability_patterns, sections, [("compensation_section", 95), ("award_copy_section", 90)], default_val="", type_cast=float,
        field_name="disability", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_disability = "Section-Aware Contextual Regex"

    # 9.8 Estate Loss
    est_patterns = [r'(?:loss\s+of\s+)?estate\s*(?:of)?\s*(?:rs\.?|inr)?\s*(\d{4,6})\b']
    estate_loss, conf_estate_loss, sec_estate_loss, page_estate_loss = contextual_extract(
        est_patterns, sections, [("compensation_section", 95), ("award_copy_section", 90)], default_val=15000.0, type_cast=float,
        field_name="estate_loss", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_estate_loss = "Section-Aware Contextual Regex"

    # 10. Prayer Amount / Prayer Section
    prayer_patterns = [
        r'(?:prayer|relief\s+claimed|claims?\s+compensation\s+of|prays\s+for)\s*(?:rs\.?|inr)?\s*([\d,\.\s]+lakhs?|[\d,\.\-\/]+)\b',
        r'\b(?:claims?\s+sum\s+of|seeking\s+compensation\s+of)\s*(?:rs\.?|inr)?\s*([\d,\.\-\/]+)\b'
    ]
    prayer, conf_prayer, sec_prayer, page_prayer = contextual_extract(
        prayer_patterns, sections, [("relief_section", 95)], default_val="", type_cast=str,
        field_name="prayer", debug_info=parser_debug, pages=pages, sections_metadata=sections_metadata, page_importances=page_importances
    )
    method_prayer = "Section-Aware Contextual Regex"

    # ======================================================
    # CHRONOLOGICAL DATES EXTRACTION
    # ======================================================
    
    chronology = parse_chronological_events(sections.get("chronological_events_section", "") or sections.get("index_section", "") or full_text)
    
    # Accident Date
    date_of_accident = chronology["date_of_accident"]
    if date_of_accident:
        conf_date_of_accident = 0.98
        sec_date_of_accident = "chronological_events_section"
        sec_meta = sections_metadata.get("chronological_events_section", {})
        page_date_of_accident = find_exact_page(date_of_accident, sec_meta.get("start_page", 1), sec_meta.get("end_page", 1), pages)
        method_date_of_accident = "Chronological Event Extraction"
    else:
        date_of_accident = ""
        conf_date_of_accident = 0.40
        sec_date_of_accident = "raw_ocr"
        page_date_of_accident = 1
        method_date_of_accident = "Fallback Contextual Search"
        
        acc_dates = extract_dates_with_context(sections.get("claimant_section", "") or full_text)
        for d_val, ctx in acc_dates:
            if any(kw in ctx for kw in ["accident", "incident", "occurrence", "happened on", "occurred on", "collision", "crash", "fir"]):
                date_of_accident = d_val
                conf_date_of_accident = 0.95
                sec_date_of_accident = "claimant_section" if d_val in sections.get("claimant_section", "") else "raw_ocr"
                page_date_of_accident = find_exact_page(d_val, 1, 10, pages)
                break

    # Birth Date
    date_of_birth = ""
    conf_date_of_birth = 0.40
    sec_date_of_birth = "raw_ocr"
    page_date_of_birth = 1
    method_date_of_birth = "Fallback Contextual Search"
    
    dob_dates = extract_dates_with_context(sections.get("claimant_section", "") or full_text)
    for d_val, ctx in dob_dates:
        if any(kw in ctx for kw in ["dob", "date of birth", "born on", "birth", "d.o.b"]):
            date_of_birth = d_val
            conf_date_of_birth = 0.95
            sec_date_of_birth = "claimant_section" if d_val in sections.get("claimant_section", "") else "raw_ocr"
            page_date_of_birth = find_exact_page(d_val, 1, 10, pages)
            break

    # ======================================================
    # NORMALIZATION & VALIDATION (unchanged legal logic)
    # ======================================================
    expected_multiplier = 0
    expected_prospects = 0.0
    
    if isinstance(age, int) and age > 0:
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
        
        if age < 40: expected_prospects = 40.0
        elif age < 50: expected_prospects = 25.0
        elif age < 60: expected_prospects = 10.0
        else: expected_prospects = 0.0

    compensation_table = parse_compensation_table(award_block)
    
    # Synchronize table extraction values with compensation_table
    if not compensation_table:
        compensation_table = {}
    for k, v in comp_fields.items():
        if v and k not in ["monthly_income", "multiplier", "future_prospect", "deduction", "total_compensation"]:
            head_title = k.replace("_", " ").title()
            compensation_table[head_title] = v

    # Classification logic
    enhancement_reduction_request = "enhancement"
    if any(k in full_text_lower for k in ["reduction", "reduce", "excessive", "exonerate", "set aside award"]):
        enhancement_reduction_request = "reduction"
    elif any(k in full_text_lower for k in ["enhance", "increase", "inadequate", "enhancement"]):
        enhancement_reduction_request = "enhancement"

    death_kws = ["death", "deceased", "fatal", "died on", "funeral expenses", "loss of dependency"]
    injury_kws = ["injury", "injured", "treatment", "disability", "medical expenses", "permanent disability"]
    death_score = sum(3 for kw in death_kws if kw in petition_block.lower()) + sum(1 for kw in death_kws if kw in full_text_lower)
    injury_score = sum(3 for kw in injury_kws if kw in petition_block.lower()) + sum(1 for kw in injury_kws if kw in full_text_lower)
    case_type = "death" if (death_score - injury_score) >= 2 else "injury"

    tn_mcop_signal = bool(re.search(r'\bm\.?c\.?o\.?p\.?\b', full_text_lower))
    tn_city_keywords = ["high court of madras", "chennai", "coimbatore", "madurai", "salem", "trichy", "pondicherry", "tribunal, tamil nadu", "madras high court"]
    tn_city_signal = any(kw in full_text_lower for kw in tn_city_keywords)
    is_tamil_nadu = tn_mcop_signal and tn_city_signal
        
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
            flat_rate = 5000.0 if accident_year >= 2020 else 3000.0
            tn_disability_compensation = disability * flat_rate
            
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

    if multiplier and expected_multiplier:
        if multiplier != expected_multiplier:
            anomalies_detected.append(f"Tribunal applied multiplier {multiplier} which deviates from Sarla Verma standard ({expected_multiplier}) for age {age}.")

    if date_of_birth and date_of_accident:
        try:
            dob_val = datetime.strptime(date_of_birth, "%d-%m-%Y")
            doa_val = datetime.strptime(date_of_accident, "%d-%m-%Y")
            calc_age = doa_val.year - dob_val.year
            if doa_val.month < dob_val.month or (doa_val.month == dob_val.month and doa_val.day < dob_val.day):
                calc_age -= 1
            if 0 <= calc_age <= 100:
                if age != calc_age:
                    age = calc_age
                    conf_age = max(conf_age, 0.90)
                    anomalies_detected.append("Age synchronized chronologically to match DOB & accident date.")
        except ValueError:
            pass

    functional_disability_keywords = [
        "loss of earning capacity", "inability to work", "unable to continue", "reduced earning",
        "loss of future earning", "functional disability", "earning capacity reduced",
        "affecting earning", "loss of earning ability", "multiplier method"
    ]
    has_functional_disability = bool(disability) and any(kw in full_text_lower for kw in functional_disability_keywords)

    reconstruction_keywords = [
        "loss of future income", "future income loss", "earning capacity", "earning capacity reduction",
        "affecting earning", "loss of earning capacity", "multiplier method", "future prospects",
        "sarla verma", "pranay sethi", "loss of dependency", "dependency loss"
    ]
    can_reconstruct = any(kw in full_text_lower for kw in reconstruction_keywords)
    
    compensation_mode = "simple_injury_award"
    if case_type == "death":
        compensation_mode = "death_case_formula"
    else:
        if disability and has_functional_disability:
            compensation_mode = "permanent_disability_formula"
        elif any(kw in full_text_lower for kw in ["lump sum", "lumpsum", "consolidated", "globally"]):
            compensation_mode = "lump_sum_award"
        else:
            compensation_mode = "simple_injury_award"

    reconstruction_triggered = False
    reconstructed_compensation = 0.0
    reconstruction_trigger_reason = "can_reconstruct=False (no explicit legal discussion)"

    if monthly_income and age and can_reconstruct:
        try:
            inc_val = float(monthly_income)
            mult_val = int(multiplier) if multiplier else expected_multiplier

            if compensation_mode == "death_case_formula":
                pros_pct = float(future_prospect) if future_prospect else expected_prospects
                enhanced_monthly = inc_val * (1.0 + pros_pct / 100.0)
                annual_inc = enhanced_monthly * 12.0
                dep_cnt = int(dependents) if dependents else 3
                if marital_status == "single":
                    deduct_pct = 0.50
                elif dep_cnt <= 1:
                    deduct_pct = 0.50
                elif dep_cnt <= 3:
                    deduct_pct = 1.0 / 3.0
                elif dep_cnt <= 6:
                    deduct_pct = 0.25
                else:
                    deduct_pct = 0.20
                family_contribution = annual_inc * (1.0 - deduct_pct)
                loss_of_dependency = family_contribution * mult_val
                reconstructed_compensation = loss_of_dependency + consortium + funeral_expenses + estate_loss
                reconstruction_trigger_reason = f"death_case_formula: loss_dep={int(loss_of_dependency)}, consortium={consortium}, funeral={funeral_expenses}"

            elif compensation_mode == "permanent_disability_formula":
                annual_inc = inc_val * 12.0
                dis_pct = float(disability) if disability else 0.0
                future_income_loss = annual_inc * (dis_pct / 100.0) * mult_val
                med_exp = float(compensation_table.get("Medical Expenses", compensation_table.get("Disability Compensation", 0.0)))
                pain_suf = float(compensation_table.get("Pain And Suffering", 0.0))
                trans = float(compensation_table.get("Transportation Charges", 0.0))
                diet = float(compensation_table.get("Extra Nourishment", 0.0))
                attender = float(compensation_table.get("Attender Charges", 0.0))
                loss_inc = float(compensation_table.get("Loss Of Income", 0.0))
                reconstructed_compensation = future_income_loss + med_exp + pain_suf + trans + diet + attender + loss_inc
                reconstruction_trigger_reason = f"permanent_disability_formula: future_income_loss={int(future_income_loss)}, dis={dis_pct}%, mult={mult_val}"

            if total_compensation and reconstructed_compensation > 0:
                diff = abs(total_compensation - reconstructed_compensation) / total_compensation
                if diff > 0.05:
                    reconstruction_triggered = True
                    anomalies_detected.append(
                        f"Compensation mismatch detected: Tribunal Award Rs. {int(total_compensation):,} vs Reconstructed Math Rs. {int(reconstructed_compensation):,}."
                    )
        except Exception as e:
            logger.error(f"Validation math error: {str(e)}")

    if reconstructed_compensation <= 0:
        table_sum = sum(compensation_table.values()) if compensation_table else 0.0
        if table_sum > 0:
            reconstructed_compensation = table_sum

    # AI Recovery Fallback
    ai_recovery_triggered = False
    fields_missing = not claimant_name or not monthly_income or not age or not total_compensation
    if fields_missing or reconstruction_triggered:
        ai_recovery_triggered = True
        
        recovered = real_text_recovery(
            petition_block,
            prayer_block,
            award_block,
            award_block,
            case_type
        )
        
        if not claimant_name and recovered.get("name"):
            claimant_name = recovered["name"]
            conf_claimant_name = 0.85
            sec_claimant_name = "AI Recovery"
            page_claimant_name = 1
            method_claimant_name = "AI RealTextRecovery Fallback"
            
        if not age and recovered.get("age"):
            age = recovered["age"]
            conf_age = 0.85
            sec_age = "AI Recovery"
            page_age = 1
            method_age = "AI RealTextRecovery Fallback"
            
        if not monthly_income and recovered.get("monthly_income"):
            monthly_income = recovered["monthly_income"]
            conf_monthly_income = 0.85
            sec_monthly_income = "AI Recovery"
            page_monthly_income = 1
            method_monthly_income = "AI RealTextRecovery Fallback"
            
        if not dependents and recovered.get("dependents"):
            dependents = recovered["dependents"]
            conf_dependents = 0.85
            sec_dependents = "AI Recovery"
            page_dependents = 1
            method_dependents = "AI RealTextRecovery Fallback"
            
        if (not total_compensation or total_compensation <= 0 or conf_total_compensation < 0.70) and recovered.get("award_amount"):
            total_compensation = recovered["award_amount"]
            conf_total_compensation = 0.85
            sec_total_compensation = "AI Recovery"
            page_total_compensation = 1
            method_total_compensation = "AI RealTextRecovery Fallback"

        if not age and date_of_birth and date_of_accident:
            try:
                dob_val = datetime.strptime(date_of_birth, "%d-%m-%Y")
                doa_val = datetime.strptime(date_of_accident, "%d-%m-%Y")
                age = doa_val.year - dob_val.year
                conf_age = 0.80
                sec_age = "raw_ocr"
                page_age = 1
                method_age = "Date Chronology Sync Fallback"
            except ValueError:
                pass
                
        if not age:
            m = re.search(r'\b(?:age|aged)\s*(?:about|is)?\s*(\d{1,2})\b', petition_block.lower())
            if m:
                age = int(m.group(1))
                conf_age = 0.75
                sec_age = "petition_block"
                page_age = 1
                method_age = "Local Age Regex Fallback"

        if not occupation:
            occ_keywords = ["service", "driver", "agriculture", "farmer", "supervisor", "teacher", "business", "laborer", "coolie", "shopkeeper", "student", "housewife"]
            for occ in occ_keywords:
                if occ in petition_block.lower():
                    occupation = occ.title()
                    conf_occupation = 0.70
                    sec_occupation = "petition_block"
                    page_occupation = 1
                    method_occupation = "Keyword Extraction Fallback"
                    break

        if not monthly_income:
            m = re.search(r'\b(?:income|salary|wage|earning|earns)\b\s*(?:is|was|of|@)?\s*(?:rs\.?|inr|rupees)?\s*([\d,]{4,10})\b', petition_block.lower())
            if not m:
                m = re.search(r'\b(?:income|salary|wage|earning|earns)\b.*?([\d,]{4,10})\b', petition_block.lower())
            if m:
                monthly_income = parse_indian_rupee_value(m.group(1))
                conf_monthly_income = 0.75
                sec_monthly_income = "petition_block"
                page_monthly_income = 1
                method_monthly_income = "Regex Local Income Fallback"

        if not multiplier and expected_multiplier:
            multiplier = expected_multiplier
            conf_multiplier = 0.70
            sec_multiplier = "raw_ocr"
            page_multiplier = 1
            method_multiplier = "Age expected multiplier sync"

        if not future_prospect and expected_prospects:
            future_prospect = expected_prospects
            conf_future_prospect = 0.70
            sec_future_prospect = "raw_ocr"
            page_future_prospect = 1
            method_future_prospect = "Age expected prospects sync"

        if not prayer:
            prayers_kws = ["appeal allowed", "compensation be enhanced", "enhanced", "award be passed", "prays for"]
            for p_kw in prayers_kws:
                if p_kw in prayer_block.lower():
                    prayer = f"The claimant prays that the {p_kw}."
                    conf_prayer = 0.70
                    sec_prayer = "prayer_block"
                    page_prayer = 1
                    method_prayer = "Keyword Extraction Fallback"
                    break

        excessive_deviation = False
        if total_compensation and reconstructed_compensation > 0:
            ratio = float(reconstructed_compensation) / float(total_compensation)
            if ratio > 3.0 or ratio < (1.0 / 3.0):
                excessive_deviation = True
                anomalies_detected.append(
                    f"Excessive math deviation: Reconstructed formula (Rs. {int(reconstructed_compensation):,}) is >3x or <1/3x of Tribunal Award (Rs. {int(total_compensation):,})."
                )

        if (not total_compensation or total_compensation <= 0 or (conf_total_compensation < 0.70 and not excessive_deviation)) and reconstructed_compensation > 0:
            total_compensation = round(reconstructed_compensation, 2)
            conf_total_compensation = 0.80
            sec_total_compensation = "award_block"
            page_total_compensation = 1
            method_total_compensation = "Reconstructed Math Sync"

        if excessive_deviation:
            conf_total_compensation = min(conf_total_compensation, 0.60)
            reconstruction_trigger_reason = f"excessive_deviation_clamped"

    award_validation_ratio = 0.0
    if total_compensation and reconstructed_compensation > 0:
        try:
            award_validation_ratio = round(float(reconstructed_compensation) / float(total_compensation), 3)
        except Exception:
            pass

    parser_debug["_meta"] = {
        "functional_disability_detected": has_functional_disability,
        "can_reconstruct": can_reconstruct,
        "compensation_mode": compensation_mode,
        "reconstruction_trigger_reason": reconstruction_trigger_reason,
        "reconstruction_triggered": reconstruction_triggered,
        "award_validation_ratio": award_validation_ratio,
        "section_confidence": {
            "petition_block": round(len(petition_block) / max(len(full_text), 1), 3),
            "prayer_block": round(len(prayer_block) / max(len(full_text), 1), 3),
            "award_block": round(len(award_block) / max(len(full_text), 1), 3)
        },
        "is_tamil_nadu": is_tamil_nadu,
        "tn_signals": {"mcop": tn_mcop_signal, "city": tn_city_signal} if is_tamil_nadu else {"mcop": tn_mcop_signal, "city": tn_city_signal}
    }

    # Citations
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

    # Legal AI Summary
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

    # Set flat 'name' field for the calculator
    flat_name = claimant_name
    if case_type == "death" and deceased_name:
        flat_name = deceased_name

    # Helper to extract flat values from compensation_table
    def get_table_value(keys):
        for k in keys:
            for t_key, t_val in compensation_table.items():
                if k.lower() in t_key.lower():
                    return t_val
        return None

    # Map table/heuristic values to flat fields
    loss_estate_val = get_table_value(["estate"]) or estate_loss or 15000.0
    
    extracted_future_medical = get_table_value(["future medical"])
    extracted_medical = None
    for t_key, t_val in compensation_table.items():
        if "medical" in t_key.lower() and "future" not in t_key.lower():
            extracted_medical = t_val
            break
    if not extracted_medical:
        extracted_medical = get_table_value(["medical"])
        
    extracted_pain = get_table_value(["pain"])
    extracted_transport = get_table_value(["transport"])
    extracted_diet = get_table_value(["nourishment", "diet"])
    extracted_attender = get_table_value(["attender", "attendant"])
    extracted_loss_income = get_table_value(["loss of income", "loss of earning", "earning"])

    suggestions = {
        "case_type": case_type,
        "compensation_mode": compensation_mode,
        "name": flat_name,
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
        
        "loss_estate": loss_estate_val,
        "medical_expenses": extracted_medical,
        "future_medical_expenses": extracted_future_medical,
        "pain_and_suffering": extracted_pain,
        "transportation": extracted_transport,
        "special_diet": extracted_diet,
        "attender_charges": extracted_attender,
        "loss_of_income": extracted_loss_income,

        "is_tamil_nadu": is_tamil_nadu,
        "mcop_number": mcop_number,
        "compensation_table": compensation_table,
        
        "ai_recovery_triggered": ai_recovery_triggered,
        "legal_ai_summary": legal_ai_summary,
        "anomalies_detected": anomalies_detected,
        "_debug": parser_debug,
        
        "confidence_scores": {
            "deceased_name": {
                "value": deceased_name,
                "confidence": conf_deceased_name,
                "source": sec_deceased_name,
                "source_section": sec_deceased_name,
                "source_page": page_deceased_name,
                "extraction_method": method_deceased_name
            },
            "claimant_name": {
                "value": claimant_name,
                "confidence": conf_claimant_name,
                "source": sec_claimant_name,
                "source_section": sec_claimant_name,
                "source_page": page_claimant_name,
                "extraction_method": method_claimant_name
            },
            "name": {
                "value": claimant_name or deceased_name,
                "confidence": conf_claimant_name,
                "source": sec_claimant_name,
                "source_section": sec_claimant_name,
                "source_page": page_claimant_name,
                "extraction_method": method_claimant_name
            },
            "father_name": {
                "value": father_name,
                "confidence": conf_father_name,
                "source": sec_father_name,
                "source_section": sec_father_name,
                "source_page": page_father_name,
                "extraction_method": method_father_name
            },
            "date_of_accident": {
                "value": date_of_accident,
                "confidence": conf_date_of_accident,
                "source": sec_date_of_accident,
                "source_section": sec_date_of_accident,
                "source_page": page_date_of_accident,
                "extraction_method": method_date_of_accident
            },
            "date_of_birth": {
                "value": date_of_birth,
                "confidence": conf_date_of_birth,
                "source": sec_date_of_birth,
                "source_section": sec_date_of_birth,
                "source_page": page_date_of_birth,
                "extraction_method": method_date_of_birth
            },
            "age": {
                "value": age,
                "confidence": conf_age,
                "source": sec_age,
                "source_section": sec_age,
                "source_page": page_age,
                "extraction_method": method_age
            },
            "occupation": {
                "value": occupation,
                "confidence": conf_occupation,
                "source": sec_occupation,
                "source_section": sec_occupation,
                "source_page": page_occupation,
                "extraction_method": method_occupation
            },
            "monthly_income": {
                "value": monthly_income,
                "confidence": conf_monthly_income,
                "source": sec_monthly_income,
                "source_section": sec_monthly_income,
                "source_page": page_monthly_income,
                "extraction_method": method_monthly_income
            },
            "multiplier": {
                "value": multiplier,
                "confidence": conf_multiplier,
                "source": sec_multiplier,
                "source_section": sec_multiplier,
                "source_page": page_multiplier,
                "extraction_method": method_multiplier
            },
            "future_prospect": {
                "value": future_prospect,
                "confidence": conf_future_prospect,
                "source": sec_future_prospect,
                "source_section": sec_future_prospect,
                "source_page": page_future_prospect,
                "extraction_method": method_future_prospect
            },
            "consortium": {
                "value": consortium,
                "confidence": conf_consortium,
                "source": sec_consortium,
                "source_section": sec_consortium,
                "source_page": page_consortium,
                "extraction_method": method_consortium
            },
            "funeral_expenses": {
                "value": funeral_expenses,
                "confidence": conf_funeral_expenses,
                "source": sec_funeral_expenses,
                "source_section": sec_funeral_expenses,
                "source_page": page_funeral_expenses,
                "extraction_method": method_funeral_expenses
            },
            "total_compensation": {
                "value": total_compensation,
                "confidence": conf_total_compensation,
                "source": sec_total_compensation,
                "source_section": sec_total_compensation,
                "source_page": page_total_compensation,
                "extraction_method": method_total_compensation
            },
            "prayer": {
                "value": prayer,
                "confidence": conf_prayer,
                "source": sec_prayer,
                "source_section": sec_prayer,
                "source_page": page_prayer,
                "extraction_method": method_prayer
            },
            "citations": {
                "value": citations,
                "confidence": conf_citations,
                "source": "cited_judgments",
                "source_section": "cited_judgments",
                "source_page": 1,
                "extraction_method": "Citation Pattern Matching"
            },
            "place_of_accident": {
                "value": place_of_accident,
                "confidence": conf_place_of_accident,
                "source": sec_place_of_accident,
                "source_section": sec_place_of_accident,
                "source_page": page_place_of_accident,
                "extraction_method": method_place_of_accident
            },
            "disability": {
                "value": disability,
                "confidence": conf_disability,
                "source": sec_disability,
                "source_section": sec_disability,
                "source_page": page_disability,
                "extraction_method": method_disability
            },
            "dependents": {
                "value": dependents,
                "confidence": conf_dependents,
                "source": sec_dependents,
                "source_section": sec_dependents,
                "source_page": page_dependents,
                "extraction_method": method_dependents
            },
            "marital_status": {
                "value": marital_status,
                "confidence": conf_marital_status,
                "source": sec_marital_status,
                "source_section": sec_marital_status,
                "source_page": page_marital_status,
                "extraction_method": method_marital_status
            }
        }
    }

    return suggestions
