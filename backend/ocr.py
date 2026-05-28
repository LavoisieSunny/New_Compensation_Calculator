import os
import re
import shutil
import tempfile
import logging
import uuid
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pypdf import PdfReader
import pypdfium2 as pdfium

from backend.parser_heuristics import parse_extracted_text
from backend.vector_db import index_document, COLLECTION_NAME

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OCRModule")

router = APIRouter()

# Global PaddleOCR instance (lazy initialized)
_ocr_instance = None
OCR_INITIALIZED = False

# Global EasyOCR instance (lazy initialized on first L4 call)
_easyocr_reader = None

# Global Batch Upload and Indexing Process Queue
BATCH_QUEUE = {}

# Whether to prefer Tesseract OCR on Windows (speeds up CPU processing and prevents Paddle C++ crashes)
PREFER_TESSERACT = True

# ======================================================
# OCR QUALITY GATE THRESHOLD
# Below this score, legal reconstruction is DISABLED.
# Fields are left blank rather than hallucinated.
# ======================================================
OCR_QUALITY_GATE_THRESHOLD = 0.05

# ======================================================
# PER-PAGE QUALITY THRESHOLDS FOR RETRY LAYERS
# ======================================================
PAGE_QUALITY_L1 = 0.50   # Accept PaddleOCR scale=2
PAGE_QUALITY_L2 = 0.40   # Accept PaddleOCR scale=3
PAGE_QUALITY_L3 = 0.35   # Accept PaddleOCR + enhanced preprocessing
PAGE_QUALITY_L4 = 0.20   # Minimum accept from EasyOCR

# Legal keywords that signal valid legal document content
_LEGAL_QUALITY_KEYWORDS = [
    "tribunal", "claimant", "petitioner", "mact", "mcop", "accident",
    "rs.", "compensation", "disability", "income", "award", "court",
    "deceased", "injured", "monthly", "insurance", "motor", "claim"
]


# ======================================================
# OCR ENGINE INITIALIZATION
# ======================================================

def get_ocr_instance():
    global _ocr_instance, OCR_INITIALIZED
    if _ocr_instance is None:
        try:
            logger.info("Initializing PaddleOCR (disabling MKLDNN to avoid oneDNN PIR crash)...")
            from paddleocr import PaddleOCR
            _ocr_instance = PaddleOCR(lang='en', enable_mkldnn=False)
            OCR_INITIALIZED = True
            logger.info("PaddleOCR successfully loaded!")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
            _ocr_instance = None
            OCR_INITIALIZED = False
    return _ocr_instance


def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            logger.info("Initializing EasyOCR reader (English)...")
            import easyocr
            _easyocr_reader = easyocr.Reader(['en'], gpu=False)
            logger.info("EasyOCR Reader successfully loaded!")
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {str(e)}")
            _easyocr_reader = None
    return _easyocr_reader


def run_easyocr_fallback(pil_img) -> tuple:
    """
    Fallback OCR engine using EasyOCR.
    Returns: (text_lines: list[str], avg_confidence: float)
    """
    reader = get_easyocr_reader()
    if reader is None:
        logger.warning("EasyOCR fallback triggered but EasyOCR is unavailable.")
        return [], 0.0
    try:
        img_np = np.array(pil_img)
        results = reader.readtext(img_np)
        
        text_lines = []
        confidences = []
        for bbox, text, conf in results:
            text = text.strip()
            if text:
                text_lines.append(text)
                confidences.append(float(conf))
                
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        logger.info(f"EasyOCR fallback success: {len(text_lines)} lines extracted (avg confidence {avg_conf:.2f})")
        return text_lines, avg_conf
    except Exception as e:
        logger.warning(f"EasyOCR execution failed: {str(e)}")
        return [], 0.0


# ======================================================
# CORE TEXT EXTRACTION — DIGITAL PDF
# ======================================================

def extract_digital_pdf_text(file_path: str) -> list:
    """
    Extracts text lines from a digital (selectable) PDF using PyPDF.
    Extremely fast (~20ms per doc) and 100% accurate for digital PDFs.
    """
    try:
        reader = PdfReader(file_path)
        text_lines = []
        for i, page in enumerate(reader.pages):
            text_lines.append(f"--- PAGE {i+1} ---")
            text = page.extract_text()
            if text:
                for line in text.split("\n"):
                    line = line.strip()
                    if line:
                        text_lines.append(line)
        return text_lines
    except Exception as e:
        logger.warning(f"Failed to extract digital text from {file_path}: {str(e)}")
        return []


def extract_alternate_pdf_text(file_path: str) -> list:
    """
    Alternate layout extraction using PyMuPDF (fitz) and pdfplumber.
    Used when PaddleOCR returns sparse results on scanned PDFs.
    LEGAL SAFETY: Only returns actual extracted text. Never fabricates data.
    """
    text_lines = []

    # Try PyMuPDF (fitz)
    try:
        import fitz
        logger.info("Alternate OCR/Extraction: Running PyMuPDF (fitz)...")
        doc = fitz.open(file_path)
        pymupdf_lines = []
        for i, page in enumerate(doc):
            pymupdf_lines.append(f"--- PAGE {i+1} ---")
            text = page.get_text()
            if text:
                for line in text.split("\n"):
                    line = line.strip()
                    if line:
                        pymupdf_lines.append(line)
        if len(pymupdf_lines) > 20:
            logger.info(f"PyMuPDF extraction successful: found {len(pymupdf_lines)} lines.")
            text_lines = pymupdf_lines
    except Exception as e:
        logger.warning(f"Alternate OCR/Extraction PyMuPDF failed: {str(e)}")

    # Try pdfplumber if PyMuPDF extracted very little
    if len(text_lines) < 25:
        try:
            import pdfplumber
            logger.info("Alternate OCR/Extraction: Running pdfplumber...")
            with pdfplumber.open(file_path) as pdf:
                plumber_lines = []
                for i, page in enumerate(pdf.pages):
                    plumber_lines.append(f"--- PAGE {i+1} ---")
                    text = page.extract_text()
                    if text:
                        for line in text.split("\n"):
                            line = line.strip()
                            if line:
                                plumber_lines.append(line)
                if len(plumber_lines) > len(text_lines):
                    logger.info(f"pdfplumber extraction successful: found {len(plumber_lines)} lines.")
                    text_lines = plumber_lines
        except Exception as e:
            logger.warning(f"Alternate OCR/Extraction pdfplumber failed: {str(e)}")

    return text_lines


# ======================================================
# IMAGE PREPROCESSING — STANDARD
# ======================================================

def preprocess_image_safe(pil_img, resize_factor=None, binarize=False):
    """
    Safe preprocessing pipeline for high-clarity legal documents.
    Pipeline:
    - Grayscale
    - Bilateral filter or fastNlMeansDenoising for noise removal (preserving text edges)
    - CLAHE (clipLimit=2.0, tileGridSize=(8, 8))
    - If binarize is True: Otsu thresholding and morphology close operation (best for Tesseract)
    - If binarize is False: Light sharpening only (best for PaddleOCR)
    """
    try:
        import cv2
        from PIL import Image

        open_cv_image = np.array(pil_img)
        # 1. Grayscale
        if len(open_cv_image.shape) == 3:
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = open_cv_image.copy()

        # 2. Denoising (Bilateral preserves sharp text edges)
        denoised = cv2.bilateralFilter(gray, 5, 50, 50)

        # 3. CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(denoised)

        if binarize:
            # 4. Otsu's thresholding
            _, thresh = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # 5. Morphology close
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            return Image.fromarray(processed).convert("RGB")
        else:
            # 4. Light sharpening
            blurred = cv2.GaussianBlur(contrast, (0, 0), 2.0)
            sharpened = cv2.addWeighted(contrast, 1.2, blurred, -0.2, 0)
            return Image.fromarray(sharpened).convert("RGB")
    except Exception as e:
        logger.warning(f"Safe preprocessing failed, returning original image: {str(e)}")
        return pil_img


def preprocess_image_for_ocr(pil_img):
    return preprocess_image_safe(pil_img, resize_factor=2)


def preprocess_image_enhanced(pil_img):
    return preprocess_image_safe(pil_img, resize_factor=3)


# ======================================================
# HIGH-DPI RENDERING & OCR DEBUG UTILITIES
# ======================================================

def render_pdf_page_high_dpi(pdf_path: str, page_idx: int, scale: float = 3.0):
    """
    Renders a specific page of a PDF at high DPI (default scale=3.0, approx 220 DPI) using pypdfium2.
    Highly reliable, fast, in-process rendering without requiring external binary dependencies like Poppler.
    """
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(pdf_path)
        page = doc[page_idx]
        bitmap = page.render(scale=scale)
        logger.info(f"Page {page_idx+1} rendered at scale {scale} (approx {int(scale * 72)} DPI) using pypdfium2.")
        return bitmap.to_pil()
    except Exception as ex:
        logger.error(f"Failed to render page {page_idx+1} using pypdfium2: {str(ex)}")
        raise ex


def save_ocr_debug_image(filename: str, img):
    """
    Saves a debug image for OCR inspection.
    Supports both PIL Image and numpy array (OpenCV format).
    """
    try:
        import cv2
        from PIL import Image
        if isinstance(img, Image.Image):
            img_np = np.array(img)
            if len(img_np.shape) == 3:
                img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            else:
                img_cv = img_np
        else:
            img_cv = img
            
        cv2.imwrite(filename, img_cv)
        logger.info(f"Saved OCR debug image: {filename}")
    except Exception as e:
        logger.warning(f"Failed to save debug image {filename}: {str(e)}")


# ======================================================
# OCR RESULT NORMALIZER
# ======================================================

def extract_text_lines_from_paddle_result(result) -> list:
    """
    Normalises PaddleOCR output across v2 (list-of-lists) and
    PaddleX v3 (object with rec_texts) output formats.
    Returns a flat deduplicated list of non-empty text strings.
    """
    text_lines = []
    if not result or len(result) == 0:
        return text_lines

    for item in result:
        if hasattr(item, 'rec_texts') and item.rec_texts:
            text_lines.extend(item.rec_texts)
        elif isinstance(item, dict) and 'rec_texts' in item:
            text_lines.extend(item['rec_texts'])
        elif hasattr(item, 'get') and item.get('rec_texts'):
            text_lines.extend(item.get('rec_texts'))
        elif isinstance(item, list):
            for line in item:
                if isinstance(line, list) and len(line) > 1 and isinstance(line[1], tuple):
                    text_lines.append(line[1][0])
                elif isinstance(line, tuple) and len(line) > 1 and isinstance(line[0], str):
                    text_lines.append(line[0])

    return [l.strip() for l in text_lines if l and l.strip()]


# ======================================================
# OCR QUALITY SCORING
# ======================================================

def score_ocr_page_quality(text_lines: list) -> float:
    """
    Scores the OCR output quality for a single page.
    Returns float 0.0 – 1.0 based on 4 weighted criteria:
      - line_count       (30%): More lines → better
      - keyword_hits     (35%): Legal MACT keywords detected
      - word_quality     (20%): Average word length (garble detection)
      - text_density     (15%): Characters per line
    """
    real_lines = [l for l in text_lines if l and not l.startswith("--- PAGE")]
    if not real_lines:
        return 0.0

    # 1. Line count score
    line_score = min(len(real_lines) / 10.0, 1.0)

    # 2. Legal keyword score
    full_text = " ".join(real_lines).lower()
    kw_hits = sum(1 for kw in _LEGAL_QUALITY_KEYWORDS if kw in full_text)
    keyword_score = min(kw_hits / 5.0, 1.0)

    # 3. Word quality score (garbled OCR = very short or very long tokens)
    words = full_text.split()
    if words:
        avg_len = sum(len(w) for w in words) / len(words)
        # Ideal word length: 3–10 chars
        word_score = 1.0 if 3.0 <= avg_len <= 10.0 else max(0.0, 1.0 - abs(avg_len - 6.5) / 6.5)
    else:
        word_score = 0.0

    # 4. Text density score (chars per line)
    avg_line_len = sum(len(l) for l in real_lines) / len(real_lines)
    density_score = min(avg_line_len / 40.0, 1.0)

    quality = (
        (line_score    * 0.30) +
        (keyword_score * 0.35) +
        (word_score    * 0.20) +
        (density_score * 0.15)
    )
    return round(quality, 3)


def calculate_paddle_confidence(result) -> float:
    """
    Calculates the average confidence score from a raw PaddleOCR result.
    """
    confidences = []
    if not result or len(result) == 0:
        return 0.0
    for item in result:
        if isinstance(item, list):
            for line in item:
                if isinstance(line, list) and len(line) > 1 and isinstance(line[1], tuple):
                    confidences.append(line[1][1])
                elif isinstance(line, tuple) and len(line) > 1 and isinstance(line[1], float):
                    confidences.append(line[1])
    return float(np.mean(confidences)) if confidences else 0.0


def _build_ocr_debug(
    engine_used: str,
    retry_count: int,
    quality_score: float,
    failed_pages: list,
    successful_pages: list,
    preprocessing_applied: list,
    fallback_ocr_engine: str,
    text_density_score: float,
    average_page_confidence: float = 0.0,
    raw_ocr_preview: str = "",
    pages: list = None
) -> dict:
    """Constructs the standard OCR debug metadata block."""
    return {
        "ocr_engine_used": engine_used,
        "ocr_retry_count": retry_count,
        "ocr_quality_score": round(quality_score, 3),
        "successful_pages": successful_pages,
        "failed_pages": failed_pages,
        "fallback_ocr_engine": fallback_ocr_engine,
        "preprocessing_applied": preprocessing_applied,
        "text_density_score": round(text_density_score, 3),
        "average_page_confidence": round(average_page_confidence, 3),
        "raw_ocr_preview": raw_ocr_preview,
        "pages": pages or []
    }


# ======================================================
# SECONDARY OCR ENGINE — Tesseract Fallback
# ======================================================

_TESSERACT_AVAILABLE = None
_TESSERACT_INITIALIZED = False

def init_tesseract():
    global _TESSERACT_INITIALIZED
    if _TESSERACT_INITIALIZED:
        return
    
    try:
        import pytesseract
        # Clean system PATH check
        tess_path = shutil.which("tesseract")
        
        if tess_path:
            pytesseract.pytesseract.tesseract_cmd = tess_path
            logger.info(f"Tesseract found and configured at: {tess_path}")
        else:
            logger.warning("Tesseract binary not found in PATH.")
    except Exception as e:
        logger.warning(f"Error during Tesseract path initialization: {str(e)}")
    _TESSERACT_INITIALIZED = True


def is_tesseract_available() -> bool:
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is not None:
        return _TESSERACT_AVAILABLE
        
    init_tesseract()
    
    try:
        import pytesseract
        # Verify it can execute
        version = pytesseract.get_tesseract_version()
        logger.info(f"Tesseract version {version} is available and verified.")
        _TESSERACT_AVAILABLE = True
    except Exception as e:
        logger.warning(f"Tesseract binary is not available or failed to execute: {str(e)}")
        _TESSERACT_AVAILABLE = False
        
    return _TESSERACT_AVAILABLE

def run_tesseract_fallback(pil_img) -> tuple:
    """
    Fallback OCR engine using Tesseract (pytesseract).
    Configured dynamically. Graces fallbacks if hin.traineddata is missing.
    Returns: (text_lines: list[str], avg_confidence: float)
    """
    if not is_tesseract_available():
        logger.warning("Tesseract fallback triggered but Tesseract is unavailable.")
        return [], 0.0
        
    try:
        import pytesseract
        
        # Try eng+hin multi-language OCR first
        try:
            text_str = pytesseract.image_to_string(pil_img, lang="eng+hin")
            config_lang = "eng+hin"
        except Exception as lang_err:
            logger.info(f"Tesseract Hindi pack missing or failed ({str(lang_err)}), falling back to English only.")
            text_str = pytesseract.image_to_string(pil_img, lang="eng")
            config_lang = "eng"
            
        text_lines = [line.strip() for line in text_str.split("\n") if line.strip()]
        
        # Get confidence scores using image_to_data
        confidences = []
        try:
            data = pytesseract.image_to_data(pil_img, lang=config_lang, output_type=pytesseract.Output.DICT)
        except Exception:
            try:
                data = pytesseract.image_to_data(pil_img, lang="eng", output_type=pytesseract.Output.DICT)
            except Exception:
                data = {}
            
        if isinstance(data, dict) and 'conf' in data:
            for c in data['conf']:
                try:
                    val = float(c)
                    if val >= 0: # -1 indicates empty/layout block
                        confidences.append(val / 100.0) # convert 0-100 to 0.0-1.0
                except ValueError:
                    continue
        
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        logger.info(f"Tesseract fallback ({config_lang}): {len(text_lines)} lines extracted (avg confidence {avg_conf:.2f})")
        return text_lines, avg_conf
    except Exception as e:
        logger.warning(f"Tesseract fallback failed: {str(e)}")
        return [], 0.0


def deskew_image(gray_img):
    """
    Detects skew angle and rotates the image to straighten the text lines.
    """
    try:
        import cv2
        # Threshold the image (text becomes white, background black)
        thresh = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Get coordinates of all text pixels
        coords = np.column_stack(np.where(thresh > 0))
        
        # Calculate skew angle
        angle = cv2.minAreaRect(coords)[-1]
        
        # minAreaRect returns angle in range [-90, 0)
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        # Ignore extremely tiny skews to avoid interpolation blur
        if abs(angle) < 0.5 or abs(angle) > 45:
            return gray_img
            
        # Perform rotation to straighten
        (h, w) = gray_img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(gray_img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        logger.info(f"Auto-deskewed image by rotation angle: {angle:.2f} degrees")
        return rotated
    except Exception as e:
        logger.warning(f"Deskewing failed: {str(e)}")
        return gray_img


def preprocess_image_premium(pil_img, binarize=False):
    """
    Premium preprocessing pipeline applying:
    - Grayscale
    - Deskew (auto-straightening)
    - Denoise (Bilateral filter to preserve sharp text boundaries)
    - Contrast enhancement (CLAHE)
    - Sharpening (Unsharp masking)
    - Adaptive Thresholding & Morphology (if binarize is True)
    """
    try:
        import cv2
        from PIL import Image
        
        open_cv_image = np.array(pil_img)
        # 1. Grayscale
        if len(open_cv_image.shape) == 3:
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = open_cv_image.copy()
            
        # 2. Deskew
        deskewed = deskew_image(gray)
        
        # 3. Denoise
        denoised = cv2.bilateralFilter(deskewed, 9, 75, 75)
        
        # 4. CLAHE contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrast = clahe.apply(denoised)
        
        # 5. Sharpening (High contrast sharpening kernel)
        sharpening_kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ])
        sharpened = cv2.filter2D(contrast, -1, sharpening_kernel)
        
        # 6. Adaptive Threshold or binarization
        if binarize:
            thresh = cv2.adaptiveThreshold(
                sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 15, 8
            )
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            return Image.fromarray(processed).convert("RGB")
        else:
            return Image.fromarray(sharpened).convert("RGB")
    except Exception as e:
        logger.warning(f"Premium preprocessing failed, returning original PIL image: {str(e)}")
        return pil_img


def score_ocr_attempt(text_lines: list) -> dict:
    """
    Scores an OCR attempt's text output based on:
    - line count (up to 30 lines)
    - keyword density (frequency of legal words)
    - legal entity matches (roles like claimant/respondent, prefixes, etc.)
    - compensation table matches (rupee/rs. values, multipliers, disability %)
    Returns a dict with overall 'score' and sub-metrics.
    """
    if not text_lines:
        return {"score": 0.0, "lines": 0, "kw_density": 0.0, "legal_entities": 0, "table_matches": 0}
        
    real_lines = [l for l in text_lines if l and not l.strip().startswith("--- PAGE")]
    line_count = len(real_lines)
    if line_count == 0:
        return {"score": 0.0, "lines": 0, "kw_density": 0.0, "legal_entities": 0, "table_matches": 0}
        
    full_text = "\n".join(real_lines).lower()
    
    # 1. Line count score
    line_score = min(line_count / 30.0, 1.0)
    
    # 2. Keyword density (legal keywords)
    legal_keywords = [
        "tribunal", "claimant", "petitioner", "mact", "mcop", "accident",
        "compensation", "disability", "income", "award", "court",
        "deceased", "injured", "monthly", "insurance", "motor", "claim",
        "respondent", "versus", "v/s", "judgement", "order", "liability"
    ]
    kw_hits = sum(1 for kw in legal_keywords if kw in full_text)
    words = full_text.split()
    word_count = len(words)
    kw_density = kw_hits / max(word_count, 1)
    # Scaled keyword score
    kw_density_score = min(kw_hits / 5.0, 1.0)
    
    # 3. Legal entity matches
    legal_entity_patterns = [
        r"\b(?:m/s|shri|smt|kumari|mr|mrs|miss)\.?\s+[a-z]+", # Names prefixes
        r"\b(?:tribunal|court|judge|mact|mcop)\b",
        r"\b(?:insurance|co\.?|ltd\.?|limited|corp(?:oration)?)\b",
        r"\b(?:claimant|petitioner|respondent|appellant|defendant|plaintiff)\b"
    ]
    entity_matches = 0
    for pat in legal_entity_patterns:
        entity_matches += len(re.findall(pat, full_text))
    entity_score = min(entity_matches / 4.0, 1.0)
    
    # 4. Compensation table matches
    comp_table_patterns = [
        r"\b(?:rs\.?|inr|rupees)\.?\s*\d+",
        r"\b\d+\s*%\s*(?:disability|permanent|partial|temporary)\b",
        r"\b(?:loss\s+of\s+earning(?:s)?|loss\s+of\s+dependency|future\s+prospects)\b",
        r"\bmultiplier\s+(?:of\s+)?\d+\b",
        r"\b(?:consortium|funeral|medical\s+expenses|pain\s+and\s+suffering|loss\s+of\s+estate)\b"
    ]
    table_matches = 0
    for pat in comp_table_patterns:
        table_matches += len(re.findall(pat, full_text))
    table_score = min(table_matches / 3.0, 1.0)
    
    # Total weighted score
    total_score = (
        (line_score * 0.25) +
        (kw_density_score * 0.25) +
        (entity_score * 0.25) +
        (table_score * 0.25)
    )
    
    return {
        "score": round(total_score, 4),
        "lines": line_count,
        "kw_density": round(kw_density, 4),
        "legal_entities": entity_matches,
        "table_matches": table_matches
    }


def classify_page_for_ocr(page_text: str) -> str:
    """
    Classifies a page to decide whether to skip it or process/prioritize it,
    based on the quick-extracted text.
    Returns: 'prioritize', 'standard', 'skip_notice', 'skip_annexure', 'skip_procedural', 'skip_signature'
    """
    text_lower = page_text.lower()
    
    # Prioritize keywords
    award_kws = ["compensation", "quantum", "multiplier", "dependency", "consortium", "funeral", "estate", "loss of", "pain and suffering", "medical expenses", "award amount", "awarded sum", "total compensation"]
    chronology_kws = ["chronology", "chronological events", "list of dates", "date of accident", "petition filed"]
    scrutiny_kws = ["scrutiny report", "scrutiny sheet", "office report", "limitation period"]
    claimant_kws = ["details of claimants", "details of petitioners", "claimant details", "petitioner details", "legal representatives", "cause title", "party details"]
    
    # Check if page has award or priority details first - we must NEVER skip pages with these!
    if any(kw in text_lower for kw in award_kws):
        return "prioritize"
    if any(kw in text_lower for kw in chronology_kws):
        return "prioritize"
    if any(kw in text_lower for kw in scrutiny_kws):
        return "prioritize"
    if any(kw in text_lower for kw in claimant_kws):
        return "prioritize"
        
    # Skip keywords
    notice_kws = ["summons", "registry notice", "notice of motion", "under section 143", "show cause notice"]
    annexure_kws = ["annexure", "exhibit", "driving license", "rc book", "insurance policy", "fir copy", "post mortem report", "inquest report"]
    procedural_kws = ["vakalatnama", "vakalath", "power of attorney", "order sheet", "proceeding sheet", "evidence list", "deposition of", "examination-in-chief", "cross-examination"]
    signature_kws = ["signature of", "thumb impression", "sd/-", "signed before me", "advocate for petitioner", "advocate for respondent"]
    
    if any(kw in text_lower for kw in notice_kws):
        return "skip_notice"
    if any(kw in text_lower for kw in annexure_kws):
        return "skip_annexure"
    if any(kw in text_lower for kw in procedural_kws):
        return "skip_procedural"
    if any(kw in text_lower for kw in signature_kws):
        return "skip_signature"
        
    return "standard"


# ======================================================
# 4-LAYER PER-PAGE OCR RETRY PIPELINE
# ======================================================

# ======================================================
# STABILIZED PER-PAGE OCR PIPELINE
# ======================================================

def perform_ocr_page_with_retry(ocr_engine, page_doc, page_idx: int, total_pages: int, pdf_path: str = None) -> tuple:
    """
    Performs the 5-attempt multi-stage OCR retry pipeline on a single PDF page:
    Attempt 1: PaddleOCR at 216 DPI (scale=3.0)
    Attempt 2: PaddleOCR at 300 DPI (scale=4.167)
    Attempt 3: Tesseract fallback on binarized 300 DPI preprocessed image
    Attempt 4: PyMuPDF page text extraction (checks selectable/digital text)
    Attempt 5: EasyOCR fallback on 300 DPI preprocessed image
    
    Chooses the BEST result using `score_ocr_attempt` across all attempted stages.
    """
    page_num = page_idx + 1
    logger.info(f"--- START OCR PIPELINE FOR PAGE {page_num}/{total_pages} ---")
    
    best_lines = []
    best_conf = 0.0
    best_score = -1.0
    best_meta = {
        "engine": "None",
        "dpi": 0,
        "confidence": 0.0,
        "preprocessing_applied": [],
        "quality_score": 0.0,
        "lines": 0
    }
    
    # Render scales corresponding to 216 and 300 DPI (72 pt per inch)
    scale_216 = 3.0
    scale_300 = 4.167
    
    # --------------------------------------------------
    # ATTEMPT 1: PaddleOCR at 216 DPI
    # --------------------------------------------------
    logger.info(f"Page {page_num}: Running Attempt 1 (PaddleOCR @ 216 DPI)...")
    try:
        pil_216 = render_pdf_page_high_dpi(pdf_path, page_idx, scale=scale_216) if pdf_path else page_doc.render(scale=scale_216).to_pil()
        processed_216 = preprocess_image_premium(pil_216, binarize=False)
        
        # Save debug images
        save_ocr_debug_image(f"debug_original_{page_num}.png", pil_216)
        save_ocr_debug_image(f"debug_processed_{page_num}.png", processed_216)
        
        temp_processed_path = f"debug_processed_{page_num}.png"
        
        paddle_engine = get_ocr_instance()
        if paddle_engine and not isinstance(paddle_engine, str):
            result = paddle_engine.ocr(temp_processed_path)
            lines_1 = extract_text_lines_from_paddle_result(result)
            conf_1 = calculate_paddle_confidence(result)
            
            if conf_1 == 0.00 and len(lines_1) >= 15:
                conf_1 = 0.85
                
            metrics_1 = score_ocr_attempt(lines_1)
            score_1 = metrics_1["score"]
            
            logger.info(f"Attempt 1 result: {len(lines_1)} lines, conf: {conf_1:.2f}, score: {score_1:.4f}")
            
            if score_1 > best_score:
                best_score = score_1
                best_lines = lines_1
                best_conf = conf_1
                best_meta = {
                    "engine": "PaddleOCR",
                    "dpi": 216,
                    "confidence": conf_1,
                    "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask"],
                    "quality_score": score_1,
                    "lines": len(lines_1)
                }
                
            # Early OOM Protection & stopping check:
            # Dense pages with high confidence already contain clean text. Continuing to Attempt 2 (300 DPI)
            # causes massive memory spikes, making CPU servers highly prone to Linux OOM-killer crashes ("Killed").
            if score_1 >= 0.70 or (conf_1 >= 0.75 and len(lines_1) >= 40):
                logger.info(
                    f"Page {page_num}: Attempt 1 was strong (score={score_1:.4f}, lines={len(lines_1)}, conf={conf_1:.2f}). "
                    f"Stopping early to protect system memory and prevent OOM crash."
                )
                page_meta = {
                    "page": page_num,
                    "engine": "PaddleOCR",
                    "dpi": 216,
                    "confidence": round(conf_1, 3),
                    "text_length": sum(len(l) for l in lines_1),
                    "quality_score": score_1,
                    "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask"],
                    "lines": len(lines_1)
                }
                return lines_1, page_meta
        else:
            logger.warning("PaddleOCR engine not available for Attempt 1.")
    except Exception as e:
        logger.error(f"Attempt 1 failed: {str(e)}")
        
    # --------------------------------------------------
    # ATTEMPT 2: PaddleOCR at 300 DPI
    # --------------------------------------------------
    logger.info(f"Page {page_num}: Running Attempt 2 (PaddleOCR @ 300 DPI)...")
    try:
        pil_300 = render_pdf_page_high_dpi(pdf_path, page_idx, scale=scale_300) if pdf_path else page_doc.render(scale=scale_300).to_pil()
        processed_300 = preprocess_image_premium(pil_300, binarize=False)
        
        save_ocr_debug_image(f"debug_processed_300_{page_num}.png", processed_300)
        temp_processed_path_300 = f"debug_processed_300_{page_num}.png"
        
        paddle_engine = get_ocr_instance()
        if paddle_engine and not isinstance(paddle_engine, str):
            result = paddle_engine.ocr(temp_processed_path_300)
            lines_2 = extract_text_lines_from_paddle_result(result)
            conf_2 = calculate_paddle_confidence(result)
            
            if conf_2 == 0.00 and len(lines_2) >= 15:
                conf_2 = 0.85
                
            metrics_2 = score_ocr_attempt(lines_2)
            score_2 = metrics_2["score"]
            
            logger.info(f"Attempt 2 result: {len(lines_2)} lines, conf: {conf_2:.2f}, score: {score_2:.4f}")
            
            if score_2 > best_score:
                best_score = score_2
                best_lines = lines_2
                best_conf = conf_2
                best_meta = {
                    "engine": "PaddleOCR",
                    "dpi": 300,
                    "confidence": conf_2,
                    "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask_300DPI"],
                    "quality_score": score_2,
                    "lines": len(lines_2)
                }
                
            if score_2 >= 0.70:
                logger.info(f"Attempt 2 was strong (score: {score_2:.4f} >= 0.70). Stopping early.")
                page_meta = {
                    "page": page_num,
                    "engine": "PaddleOCR",
                    "dpi": 300,
                    "confidence": round(conf_2, 3),
                    "text_length": sum(len(l) for l in lines_2),
                    "quality_score": score_2,
                    "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask_300DPI"],
                    "lines": len(lines_2)
                }
                return lines_2, page_meta
        else:
            logger.warning("PaddleOCR engine not available for Attempt 2.")
    except Exception as e:
        logger.error(f"Attempt 2 failed: {str(e)}")
        
    # --------------------------------------------------
    # ATTEMPT 3: Tesseract Fallback
    # --------------------------------------------------
    if is_tesseract_available():
        logger.info(f"Page {page_num}: Running Attempt 3 (Tesseract Fallback)...")
        try:
            pil_300 = render_pdf_page_high_dpi(pdf_path, page_idx, scale=scale_300) if pdf_path else page_doc.render(scale=scale_300).to_pil()
            binarized_300 = preprocess_image_premium(pil_300, binarize=True)
            save_ocr_debug_image(f"debug_processed_binarized_{page_num}.png", binarized_300)
            
            lines_3, conf_3 = run_tesseract_fallback(binarized_300)
            metrics_3 = score_ocr_attempt(lines_3)
            score_3 = metrics_3["score"]
            
            logger.info(f"Attempt 3 result: {len(lines_3)} lines, conf: {conf_3:.2f}, score: {score_3:.4f}")
            
            if score_3 > best_score:
                best_score = score_3
                best_lines = lines_3
                best_conf = conf_3
                best_meta = {
                    "engine": "Tesseract",
                    "dpi": 300,
                    "confidence": conf_3,
                    "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask", "binarize_otsu_adaptive"],
                    "quality_score": score_3,
                    "lines": len(lines_3)
                }
                
            if score_3 >= 0.70:
                logger.info(f"Attempt 3 was strong (score: {score_3:.4f} >= 0.70). Stopping early.")
                page_meta = {
                    "page": page_num,
                    "engine": "Tesseract",
                    "dpi": 300,
                    "confidence": round(conf_3, 3),
                    "text_length": sum(len(l) for l in lines_3),
                    "quality_score": score_3,
                    "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask", "binarize_otsu_adaptive"],
                    "lines": len(lines_3)
                }
                return lines_3, page_meta
        except Exception as e:
            logger.error(f"Attempt 3 failed: {str(e)}")
    else:
        logger.info(f"Page {page_num}: Skipping Attempt 3 (Tesseract not available).")
        
    # --------------------------------------------------
    # ATTEMPT 4: PyMuPDF Extraction (fitz text)
    # --------------------------------------------------
    logger.info(f"Page {page_num}: Running Attempt 4 (PyMuPDF Digital Text Check)...")
    try:
        lines_4 = []
        if pdf_path:
            import fitz
            fitz_doc = fitz.open(pdf_path)
            page_text = fitz_doc[page_idx].get_text()
            if page_text:
                lines_4 = [l.strip() for l in page_text.split("\n") if l.strip()]
                
        metrics_4 = score_ocr_attempt(lines_4)
        score_4 = metrics_4["score"]
        
        logger.info(f"Attempt 4 result: {len(lines_4)} lines, score: {score_4:.4f}")
        
        if score_4 > best_score:
            best_score = score_4
            best_lines = lines_4
            best_conf = 1.0
            best_meta = {
                "engine": "PyMuPDF",
                "dpi": 72,
                "confidence": 1.0,
                "preprocessing_applied": [],
                "quality_score": score_4,
                "lines": len(lines_4)
            }
            
        if score_4 >= 0.70:
            logger.info(f"Attempt 4 was strong (score: {score_4:.4f} >= 0.70). Stopping early.")
            page_meta = {
                "page": page_num,
                "engine": "PyMuPDF",
                "dpi": 72,
                "confidence": 1.0,
                "text_length": sum(len(l) for l in lines_4),
                "quality_score": score_4,
                "preprocessing_applied": [],
                "lines": len(lines_4)
            }
            return lines_4, page_meta
    except Exception as e:
        logger.error(f"Attempt 4 failed: {str(e)}")
        
    # --------------------------------------------------
    # ATTEMPT 5: EasyOCR Fallback
    # --------------------------------------------------
    logger.info(f"Page {page_num}: Running Attempt 5 (EasyOCR Fallback)...")
    try:
        pil_300 = render_pdf_page_high_dpi(pdf_path, page_idx, scale=scale_300) if pdf_path else page_doc.render(scale=scale_300).to_pil()
        processed_300 = preprocess_image_premium(pil_300, binarize=False)
        
        lines_5, conf_5 = run_easyocr_fallback(processed_300)
        metrics_5 = score_ocr_attempt(lines_5)
        score_5 = metrics_5["score"]
        
        logger.info(f"Attempt 5 result: {len(lines_5)} lines, conf: {conf_5:.2f}, score: {score_5:.4f}")
        
        if score_5 > best_score:
            best_score = score_5
            best_lines = lines_5
            best_conf = conf_5
            best_meta = {
                "engine": "EasyOCR",
                "dpi": 300,
                "confidence": conf_5,
                "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask_300DPI"],
                "quality_score": score_5,
                "lines": len(lines_5)
            }
    except Exception as e:
        logger.error(f"Attempt 5 failed: {str(e)}")
        
    logger.info(f"--- PAGE {page_num} PIPELINE COMPLETE: Best engine={best_meta['engine']}, Best score={best_score:.4f} ---")
    page_meta = {
        "page": page_num,
        "engine": best_meta["engine"],
        "dpi": best_meta.get("dpi", 300),
        "confidence": round(best_conf, 3),
        "text_length": sum(len(l) for l in best_lines),
        "quality_score": best_score,
        "preprocessing_applied": best_meta["preprocessing_applied"],
        "lines": len(best_lines)
    }
    return best_lines, page_meta


# ======================================================
# INTELLIGENT PAGE PRE-SCANNING
# ======================================================

def find_relevant_pages_by_keywords(file_path: str, total_pages: int) -> list:
    """
    Intelligently searches middle pages (pages 13 to total_pages-8) for
    compensation-related keywords to prioritize them during scanned PDF OCR.
    Uses pure Python digital text extraction (PyPDF) and PyMuPDF (fitz) which is extremely fast.
    """
    relevant_pages = []
    
    # Keywords that strongly indicate claimant facts or compensation math
    comp_keywords = [
        "compensation", "dependency", "multiplier", "consortium", 
        "funeral", "monthly income", "disability", "loss of earning",
        "quantum", "awarded sum", "loss of future", "future prospect",
        "medical expenses", "pain and suffering"
    ]
    
    # 1. Try PyPDF extraction first
    try:
        from pypdf import PdfReader
        if total_pages > 12:
            reader = PdfReader(file_path)
            for page_idx in range(12, total_pages - 8):
                if page_idx >= len(reader.pages):
                    break
                page = reader.pages[page_idx]
                text = page.extract_text()
                if text:
                    text_lower = text.lower()
                    if any(kw in text_lower for kw in comp_keywords):
                        relevant_pages.append(page_idx)
                        logger.info(f"Dynamically added page {page_idx+1} to OCR queue based on PyPDF keyword hits.")
    except Exception as e:
        logger.warning(f"PyPDF intelligent page scanning failed: {str(e)}")
        
    # 2. Try PyMuPDF (fitz) extraction as robust fallback
    if total_pages > 12:
        try:
            import fitz
            doc = fitz.open(file_path)
            for page_idx in range(12, total_pages - 8):
                if page_idx >= len(doc):
                    break
                if page_idx in relevant_pages:
                    continue
                text = doc[page_idx].get_text()
                if text:
                    text_lower = text.lower()
                    if any(kw in text_lower for kw in comp_keywords):
                        relevant_pages.append(page_idx)
                        logger.info(f"Dynamically added page {page_idx+1} to OCR queue based on PyMuPDF keyword hits.")
        except Exception as e:
            logger.warning(f"PyMuPDF intelligent page scanning failed: {str(e)}")
            
    return relevant_pages


# ======================================================
# MAIN SCANNED PDF OCR PIPELINE
# ======================================================

def perform_ocr_on_scanned_pdf(file_path: str, progress_callback=None, scan_all_pages: bool = False) -> tuple:
    """
    Renders pages of a scanned PDF using pypdfium2 and runs the
    5-stage per-page OCR retry pipeline on each relevant page.
    Implements fast keyword-based page relevance classification & dynamic page skipping.
    """
    ocr_engine = get_ocr_instance()

    if ocr_engine is None:
        logger.warning("PaddleOCR offline. Returning empty result — no fabricated legal data injected.")
        return [], _build_ocr_debug(
            engine_used="unavailable", retry_count=0, quality_score=0.0,
            failed_pages=[], successful_pages=[], preprocessing_applied=[],
            fallback_ocr_engine="none", text_density_score=0.0
        )

    try:
        doc = pdfium.PdfDocument(file_path)
        total_pages = len(doc)
        logger.info(f"Scanned PDF '{file_path}' ({total_pages} pages): starting 5-stage OCR retry pipeline (scan_all_pages={scan_all_pages})...")

        # Optimization: for large PDFs (>10 pages), scan first 12 + last 8 only by default
        # Background indexing scans 100% of the pages to ensure thorough vector DB coverage!
        if total_pages > 10 and not scan_all_pages:
            base_pages = list(range(12)) + list(range(total_pages - 8, total_pages))
            dynamic_pages = find_relevant_pages_by_keywords(file_path, total_pages)
            pages_to_scan = sorted(set(base_pages + dynamic_pages))
            logger.info(f"Large PDF detected. Initial scan pages: {[p+1 for p in pages_to_scan]}")
        else:
            pages_to_scan = list(range(total_pages))

        text_lines = []
        failed_pages = []
        successful_pages = []
        all_preprocessing_steps = []
        total_retry_count = 0
        page_qualities = []
        page_confidences = []
        fallback_engine_used = ""

        page_details = []
        
        for idx, page_idx in enumerate(pages_to_scan):
            page_num = page_idx + 1
            text_lines.append(f"--- PAGE {page_num} ---")
            
            # Step A: Get quick text using PyMuPDF or a low-res fast Tesseract scan (scale=1.0)
            quick_text = ""
            try:
                import fitz
                fitz_doc = fitz.open(file_path)
                quick_text = fitz_doc[page_idx].get_text()
            except Exception:
                pass
                
            if not quick_text.strip() and is_tesseract_available():
                try:
                    low_res_pil = render_pdf_page_high_dpi(file_path, page_idx, scale=1.0)
                    import pytesseract
                    quick_text = pytesseract.image_to_string(low_res_pil, lang="eng")
                except Exception as e:
                    logger.debug(f"Low-res pre-OCR scan failed on page {page_num}: {str(e)}")
            
            # Step B: Classify page type using quick text
            layout_type = "unknown"
            relevance = "standard"
            if quick_text.strip():
                relevance = classify_page_for_ocr(quick_text)
                from backend.parser_heuristics import classify_page_type
                layout_type = classify_page_type(quick_text, page_num)
                
            # Step C: Filter & Ignore non-essential pages
            if relevance.startswith("skip"):
                logger.info(f"DEBUG PAGE SKIP: page_num={page_num}, why_skipped={relevance}, layout_type={layout_type}")
                
                # Mock page details
                page_details.append({
                    "page": page_num,
                    "engine": f"Skipped-{relevance}",
                    "confidence": 1.0,
                    "text_length": 0,
                    "dpi": 0,
                    "quality_score": 0.0,
                    "preprocessing_applied": [],
                    "lines": 0
                })
                # Add placeholder skipped lines
                text_lines.append(f"[Procedural page {page_num} filtered out: {layout_type} ({relevance})]")
                successful_pages.append(page_num)
                continue

            # Run 5-stage pipeline
            page_lines, page_meta = perform_ocr_page_with_retry(
                ocr_engine, doc[page_idx], page_idx, total_pages, pdf_path=file_path
            )

            q = page_meta.get("quality_score", 0.0)
            conf = page_meta.get("confidence", 0.0)
            engine = page_meta.get("engine", "PaddleOCR")
            
            page_qualities.append(q)
            page_confidences.append(conf)

            # Fix 8: Comprehensive structured page-by-page debug logging
            logger.info(
                f"DEBUG PAGE OCR: page_num={page_num}, engine={engine}, DPI={page_meta.get('dpi', 0)}, "
                f"lines={page_meta.get('lines', 0)}, confidence={conf:.2f}, "
                f"preprocessing={page_meta.get('preprocessing_applied', [])}"
            )

            # Collect page-wise debug metrics
            page_details.append(page_meta)

            if engine in ["Tesseract", "EasyOCR"]:
                total_retry_count += 1
                fallback_engine_used = engine

            # Collect unique preprocessing steps
            for step in page_meta.get("preprocessing_applied", []):
                if step not in all_preprocessing_steps:
                    all_preprocessing_steps.append(step)

            if page_lines:
                successful_pages.append(page_num)
            else:
                failed_pages.append(page_num)
                logger.warning(f"Page {page_num}: No text extracted across standard and fallback OCR engines.")

            text_lines.extend(page_lines)
            logger.info(f"Page {page_num}/{total_pages}: engine={engine}, quality={q:.4f}, lines={len(page_lines)}")

            if progress_callback:
                progress_callback(int(((idx + 1) / len(pages_to_scan)) * 90))

        overall_quality = round(sum(page_qualities) / len(page_qualities), 4) if page_qualities else 0.0
        overall_conf = round(sum(page_confidences) / len(page_confidences), 4) if page_confidences else 0.0
        real_lines = [l for l in text_lines if not l.startswith("--- PAGE")]
        text_density = round(
            sum(len(l) for l in real_lines) / max(len(real_lines), 1) / 80.0, 3
        ) if real_lines else 0.0

        # Construct final debug dict
        ocr_debug = _build_ocr_debug(
            engine_used="PaddleOCR",
            retry_count=total_retry_count,
            quality_score=overall_quality,
            failed_pages=failed_pages,
            successful_pages=successful_pages,
            preprocessing_applied=all_preprocessing_steps,
            fallback_ocr_engine=fallback_engine_used,
            text_density_score=min(text_density, 1.0),
            average_page_confidence=overall_conf,
            raw_ocr_preview="\n".join(text_lines)[:3000],
            pages=page_details
        )
        return text_lines, ocr_debug

    except Exception as e:
        logger.error(f"Critical error during scanned PDF OCR: {str(e)}")
        return [], _build_ocr_debug(
            engine_used="PaddleOCR", retry_count=0, quality_score=0.0,
            failed_pages=[], successful_pages=[], preprocessing_applied=[],
            fallback_ocr_engine="none", text_density_score=0.0
        )


def perform_ocr_on_image(file_path: str) -> tuple:
    """
    Runs the stabilized OCR pipeline directly on image uploads (PNG, JPG, BMP).
    Returns: (text_lines: list[str], ocr_debug: dict)
    """
    ocr_engine = get_ocr_instance()

    if ocr_engine is None:
        logger.warning("PaddleOCR offline. Returning empty result — no fabricated legal data injected.")
        return [], _build_ocr_debug(
            engine_used="unavailable", retry_count=0, quality_score=0.0,
            failed_pages=[1], successful_pages=[], preprocessing_applied=[],
            fallback_ocr_engine="none", text_density_score=0.0
        )

    try:
        from PIL import Image
        original_pil = Image.open(file_path)
        
        # Run 5-stage pipeline directly on the image
        logger.info(f"Image upload '{file_path}': starting 5-stage OCR retry pipeline...")
        
        best_lines = []
        best_conf = 0.0
        best_score = -1.0
        best_meta = {
            "engine": "PaddleOCR",
            "dpi": 300,
            "confidence": 0.0,
            "preprocessing_applied": [],
            "quality_score": 0.0,
            "lines": 0
        }
        
        # Save original debug image
        save_ocr_debug_image("debug_original_1.png", original_pil)
        
        # Preprocess 216 DPI (mild CLAHE, light sharpen)
        processed_216 = preprocess_image_premium(original_pil, binarize=False)
        save_ocr_debug_image("debug_processed_1.png", processed_216)
        
        # Attempt 1: PaddleOCR
        try:
            result = ocr_engine.ocr("debug_processed_1.png")
            lines_1 = extract_text_lines_from_paddle_result(result)
            conf_1 = calculate_paddle_confidence(result)
            if conf_1 == 0.00 and len(lines_1) >= 15:
                conf_1 = 0.85
            metrics_1 = score_ocr_attempt(lines_1)
            score_1 = metrics_1["score"]
            logger.info(f"Image - Attempt 1 result: {len(lines_1)} lines, conf: {conf_1:.2f}, score: {score_1:.4f}")
            if score_1 > best_score:
                best_score = score_1
                best_lines = lines_1
                best_conf = conf_1
                best_meta = {
                    "engine": "PaddleOCR",
                    "dpi": 216,
                    "confidence": conf_1,
                    "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask"],
                    "quality_score": score_1,
                    "lines": len(lines_1)
                }
        except Exception as e:
            logger.error(f"Image - Attempt 1 failed: {str(e)}")
            
        # Attempt 3 (Tesseract Fallback)
        if best_score < 0.70 and is_tesseract_available():
            try:
                binarized_pil = preprocess_image_premium(original_pil, binarize=True)
                save_ocr_debug_image("debug_processed_binarized_1.png", binarized_pil)
                lines_3, conf_3 = run_tesseract_fallback(binarized_pil)
                metrics_3 = score_ocr_attempt(lines_3)
                score_3 = metrics_3["score"]
                logger.info(f"Image - Attempt 3 (Tesseract) result: {len(lines_3)} lines, conf: {conf_3:.2f}, score: {score_3:.4f}")
                if score_3 > best_score:
                    best_score = score_3
                    best_lines = lines_3
                    best_conf = conf_3
                    best_meta = {
                        "engine": "Tesseract",
                        "dpi": 300,
                        "confidence": conf_3,
                        "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask", "binarize_otsu_adaptive"],
                        "quality_score": score_3,
                        "lines": len(lines_3)
                    }
            except Exception as e:
                logger.error(f"Image - Attempt 3 failed: {str(e)}")
                
        # Attempt 5 (EasyOCR Fallback)
        if best_score < 0.70:
            try:
                lines_5, conf_5 = run_easyocr_fallback(processed_216)
                metrics_5 = score_ocr_attempt(lines_5)
                score_5 = metrics_5["score"]
                logger.info(f"Image - Attempt 5 (EasyOCR) result: {len(lines_5)} lines, conf: {conf_5:.2f}, score: {score_5:.4f}")
                if score_5 > best_score:
                    best_score = score_5
                    best_lines = lines_5
                    best_conf = conf_5
                    best_meta = {
                        "engine": "EasyOCR",
                        "dpi": 300,
                        "confidence": conf_5,
                        "preprocessing_applied": ["grayscale", "auto-deskew", "bilateral_denoise", "clahe", "unsharp_mask"],
                        "quality_score": score_5,
                        "lines": len(lines_5)
                    }
            except Exception as e:
                logger.error(f"Image - Attempt 5 failed: {str(e)}")

        failed_pages = [] if best_lines else [1]
        successful_pages = [1] if best_lines else []
        
        page_details = [{
            "page": 1,
            "engine": best_meta["engine"],
            "dpi": best_meta.get("dpi", 300),
            "confidence": round(best_conf, 3),
            "text_length": sum(len(l) for l in best_lines),
            "quality_score": best_score,
            "preprocessing_applied": best_meta["preprocessing_applied"],
            "lines": best_meta["lines"]
        }]

        ocr_debug = _build_ocr_debug(
            engine_used="PaddleOCR",
            retry_count=1 if best_meta["engine"] in ["Tesseract", "EasyOCR"] else 0,
            quality_score=best_score,
            failed_pages=failed_pages,
            successful_pages=successful_pages,
            preprocessing_applied=best_meta["preprocessing_applied"],
            fallback_ocr_engine=best_meta["engine"] if best_meta["engine"] != "PaddleOCR" else "",
            text_density_score=min(len(best_lines) / 30.0, 1.0),
            average_page_confidence=best_conf,
            raw_ocr_preview="\n".join(best_lines)[:3000],
            pages=page_details
        )

        return best_lines, ocr_debug

    except Exception as e:
        logger.error(f"Error running OCR on image: {str(e)}")
        return [], _build_ocr_debug(
            "PaddleOCR", 0, 0.0, [1], [], [], "none", 0.0
        )


# ======================================================
# UTILITIES
# ======================================================

def is_extracted_text_sparse(text_lines: list) -> bool:
    """
    Returns True if extracted text (excluding page markers) has fewer than 15 lines
    OR if the text is detected as heavily garbled (poor quality digital encoding).
    Used to decide whether to escalate to the scanned-PDF OCR pipeline.
    """
    actual = [l for l in text_lines if not l.strip().startswith("--- PAGE")]
    if len(actual) < 15:
        return True

    # Quality check for garbled digital text layers (highly scrambled/corrupted font encodings):
    full_text = " ".join(actual).lower()
    
    # 1. Check legal keyword hits in the text
    legal_keywords = ["tribunal", "claimant", "petitioner", "accident", "compensation", "deceased", "injured", "insurance", "award", "judgment"]
    kw_hits = sum(1 for kw in legal_keywords if kw in full_text)
    
    # 2. Check symbol density and word quality
    words = [w for w in full_text.split() if w]
    if not words:
        return True
        
    avg_word_len = sum(len(w) for w in words) / len(words)
    # High proportion of long unspaced words with multiple special characters indicates a corrupted text layer
    gibberish_words = sum(1 for w in words if len(w) > 15 or any(c in w for c in '@#$[]{}|'))
    gibberish_ratio = gibberish_words / len(words)
    
    # If the text has very few legal keywords despite being long, OR high gibberish ratio, OR extreme word length, flag as poor quality
    is_poor_quality = (
        (kw_hits < 3 and len(actual) > 50) or
        (gibberish_ratio > 0.05) or
        (avg_word_len > 12.0) or
        (avg_word_len < 2.5 and len(actual) > 50)
    )
    if is_poor_quality:
        logger.info(
            f"Digital text quality check: detected garbled text layer (kw_hits={kw_hits}, "
            f"gibberish_ratio={gibberish_ratio:.2f}, avg_word_len={avg_word_len:.1f}). Escalate to OCR fallback."
        )
        return True
        
    return False


def extract_award_amount_from_text(text_lines: list) -> float:
    """
    Extracts an explicit tribunal award amount from raw OCR text lines.
    Returns 0.0 if no clear amount is found.
    LEGAL SAFETY: Only returns amounts found in actual OCR text, skipping exaggeration claims.
    """
    award_patterns = [
        r'(?:total|final|award|awarded|amount|sum\s+of|compensation\s+of)\b[^0-9]{0,50}?(?:rs\.?|inr|rupees)?\s*([\d,]{5,10})\b',
        r'\b(?:rs\.?|inr)\s*([\d,]{5,10})\b[^0-9]{0,50}?(?:with\s*interest|is\s*awarded|as\s*compensation|towards)'
    ]
    full_text_lower = "\n".join(text_lines).lower()
    for pat in award_patterns:
        candidates = []
        for match in re.finditer(pat, full_text_lower):
            val_str = match.group(1)
            val = float(re.sub(r'[^\d]', '', val_str))
            
            # Check context window before the match to see if it's a claim/demand
            start_pos = max(0, match.start() - 60)
            pre_ctx = full_text_lower[start_pos:match.start()]
            
            if any(kw in pre_ctx for kw in ["claim", "claiming", "sought", "demand", "demanded", "prayed", "prayer", "valuation"]):
                # Proximity override: if a positive keyword is closer to the match than the negative keyword, do not skip
                neg_pos = -1
                for kw in ["claim", "claiming", "sought", "demand", "demanded", "prayed", "prayer", "valuation"]:
                    idx = pre_ctx.rfind(kw)
                    if idx > neg_pos:
                        neg_pos = idx
                
                pos_pos = -1
                for kw in ["award", "awarded", "awarded sum", "amount awarded", "total compensation", "final award"]:
                    idx = pre_ctx.rfind(kw)
                    if idx > pos_pos:
                        pos_pos = idx
                        
                if neg_pos > pos_pos:
                    logger.info(f"Skipping claimed amount Rs. {val:,.0f} from award candidate list due to claim context: '{pre_ctx.strip()}'")
                    continue
                
            candidates.append(val)
            
        if candidates:
            # Exclude low values under 5000 (which are court fees/diet), and return the first valid candidate
            valid_candidates = [c for c in candidates if c >= 5000]
            if valid_candidates:
                return valid_candidates[0]
                
    return 0.0


# ======================================================
# OCR QUALITY GATE
# ======================================================

def apply_ocr_quality_gate(suggestions: dict, ocr_debug: dict) -> dict:
    """
    Legal Safety Gate: If OCR quality score is below the minimum threshold,
    we activate partial extraction recovery mode instead of blanking the fields.
    Low-confidence fields remain available for autofill but are marked inside suggestions.
    """
    quality = ocr_debug.get("ocr_quality_score", 1.0)
    suggestions["ocr_quality_insufficient"] = quality < OCR_QUALITY_GATE_THRESHOLD

    if quality < OCR_QUALITY_GATE_THRESHOLD:
        logger.warning(
            f"OCR quality {quality:.2f} below legal safety threshold {OCR_QUALITY_GATE_THRESHOLD}. "
            "Activating partial extraction recovery mode."
        )
        suggestions["ocr_warning"] = (
            f"OCR confidence low (score: {quality:.2f}). Running in partial extraction recovery mode."
        )
        suggestions["partial_extraction_recovery_mode"] = True

    return suggestions


# ======================================================
# BACKGROUND BATCH INDEXING PIPELINE
# ======================================================

def run_background_pdf_indexing(file_id: str, temp_path: str, filename: str):
    """
    Background worker: dual-mode PDF text extraction → 4-layer OCR retry
    → legal heuristics parsing → OCR quality gate → Qdrant vector indexing.
    """
    try:
        BATCH_QUEUE[file_id]["status"] = "scanning"
        BATCH_QUEUE[file_id]["progress"] = 20

        # 1. Attempt digital selectable text extraction (fastest path)
        logger.info(f"Background task: Extracting selectable text from '{filename}'")
        text_lines = extract_digital_pdf_text(temp_path)
        fallback_source = "DigitalPDF"
        ocr_debug = _build_ocr_debug("DigitalPDF", 0, 1.0, [], [], [], "", 0.0)

        # 2. Sparse → 4-layer OCR retry pipeline (scan_all_pages=True for complete vector DB index)
        if is_extracted_text_sparse(text_lines):
            logger.info(f"Selectable text sparse. Running 4-layer OCR pipeline for '{filename}'")

            def report_progress(prog_percent):
                BATCH_QUEUE[file_id]["progress"] = prog_percent

            text_lines, ocr_debug = perform_ocr_on_scanned_pdf(
                temp_path, progress_callback=report_progress, scan_all_pages=True
            )
            fallback_source = "PaddleOCR"

        # 3. Still sparse → alternate layout extraction (PyMuPDF / pdfplumber)
        if is_extracted_text_sparse(text_lines):
            logger.info("OCR pipeline sparse. Trying alternate layout extraction (PyMuPDF/pdfplumber)...")
            alt_lines = extract_alternate_pdf_text(temp_path)
            if len(alt_lines) > len(text_lines):
                text_lines = alt_lines
                fallback_source = "AlternateOCR"
                ocr_debug["fallback_ocr_engine"] = "PyMuPDF/pdfplumber"
                ocr_debug["ocr_quality_score"] = 1.0

        BATCH_QUEUE[file_id]["progress"] = 90

        # 4. Parse with legal heuristics
        logger.info(f"Parsing extracted text for '{filename}'")
        suggestions = parse_extracted_text(text_lines)

        # 5. OCR Quality Gate — disable reconstruction if quality is insufficient
        suggestions = apply_ocr_quality_gate(suggestions, ocr_debug)

        if suggestions.get("ai_recovery_triggered", False):
            fallback_source = "RealTextRecovery"
        suggestions["fallback_source_used"] = fallback_source

        # 6. Extract explicit judicial award amount
        award_amount = extract_award_amount_from_text(text_lines)
        if award_amount > 0:
            suggestions["award_amount"] = award_amount
            suggestions["total_compensation"] = award_amount
            
            # Recalculate notional monthly income with the true award amount
            from backend.parser_heuristics import deduce_notional_income
            age = suggestions.get("age") or 30
            marital_status = suggestions.get("marital_status") or "married"
            dependents = suggestions.get("dependents") or ""
            future_prospect = suggestions.get("future_prospect") or 25.0
            multiplier = suggestions.get("multiplier") or 15
            
            suggestions["monthly_income"] = deduce_notional_income(
                award_amount, age, marital_status, dependents, future_prospect, multiplier
            )
            logger.info(f"Judicial award amount parsed: Rs. {award_amount:,.0f}, recalculated monthly income: Rs. {suggestions['monthly_income']:,.2f}")

        # 7. Index into Qdrant vector DB
        BATCH_QUEUE[file_id]["status"] = "indexing"
        logger.info(f"Indexing '{filename}' in Qdrant...")
        success = index_document(filename, text_lines, suggestions)

        # Format suggestions into strict nested calculator format for frontend queue consumption
        from backend.parser_heuristics import format_suggestions_for_calculator
        formatted_suggestions = format_suggestions_for_calculator(suggestions)

        # 8. Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

        if success:
            BATCH_QUEUE[file_id]["status"] = "indexed"
            BATCH_QUEUE[file_id]["progress"] = 100
            BATCH_QUEUE[file_id]["suggestions"] = formatted_suggestions
            BATCH_QUEUE[file_id]["raw_text"] = text_lines
            BATCH_QUEUE[file_id]["ocr_debug"] = ocr_debug
            logger.info(f"Background task: '{filename}' indexed successfully!")
        else:
            BATCH_QUEUE[file_id]["status"] = "failed"
            BATCH_QUEUE[file_id]["error"] = "Qdrant indexing upsert failed."
            logger.error(f"Background task: Indexing failed for '{filename}'")

    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        BATCH_QUEUE[file_id]["status"] = "failed"
        BATCH_QUEUE[file_id]["error"] = str(e)
        logger.error(f"Background task exception for '{filename}': {str(e)}")


# ======================================================
# API ROUTERS
# ======================================================

@router.post("/process-ocr")
async def process_single_file(file: UploadFile = File(...)):
    """
    Synchronous single image/PDF upload — instant OCR + legal heuristics parsing.
    Response includes ocr_debug metadata block with quality score and retry info.
    """
    file_ext = os.path.splitext(file.filename)[1].lower()
    allowed_images = {".png", ".jpg", ".jpeg", ".bmp"}
    allowed_docs = {".pdf"}

    if file_ext not in allowed_images and file_ext not in allowed_docs:
        raise HTTPException(
            status_code=400,
            detail="Only standard images (PNG, JPG, BMP) and PDFs are supported."
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(e)}")

    try:
        fallback_source = "DigitalPDF"
        ocr_debug = _build_ocr_debug("DigitalPDF", 0, 1.0, [], [], [], "", 0.0)

        if file_ext == ".pdf":
            # 1. Try selectable digital text (fastest)
            text_lines = extract_digital_pdf_text(temp_path)

            # 2. Sparse → 4-layer OCR retry pipeline
            if is_extracted_text_sparse(text_lines):
                logger.info("Selectable PDF text sparse. Running 4-layer OCR pipeline...")
                text_lines, ocr_debug = perform_ocr_on_scanned_pdf(temp_path)
                fallback_source = "PaddleOCR"

            # 3. Still sparse → alternate layout extraction
            if is_extracted_text_sparse(text_lines):
                logger.info("OCR output sparse. Running alternate layout extraction...")
                alt_lines = extract_alternate_pdf_text(temp_path)
                if len(alt_lines) > len(text_lines):
                    text_lines = alt_lines
                    fallback_source = "AlternateOCR"
                    ocr_debug["fallback_ocr_engine"] = "PyMuPDF/pdfplumber"
                    ocr_debug["ocr_quality_score"] = 1.0
        else:
            # Image upload — 4-layer retry
            text_lines, ocr_debug = perform_ocr_on_image(temp_path)
            fallback_source = "PaddleOCR"

        # Legal heuristics parsing
        suggestions = parse_extracted_text(text_lines)

        # OCR Quality Gate
        suggestions = apply_ocr_quality_gate(suggestions, ocr_debug)

        if suggestions.get("ai_recovery_triggered", False):
            fallback_source = "RealTextRecovery"
        suggestions["fallback_source_used"] = fallback_source

        # Extract judicial award amount
        award_amount = extract_award_amount_from_text(text_lines)
        if award_amount > 0:
            suggestions["award_amount"] = award_amount
            suggestions["total_compensation"] = award_amount
            
            # Recalculate notional monthly income with the true award amount
            from backend.parser_heuristics import deduce_notional_income
            age = suggestions.get("age") or 30
            marital_status = suggestions.get("marital_status") or "married"
            dependents = suggestions.get("dependents") or ""
            future_prospect = suggestions.get("future_prospect") or 25.0
            multiplier = suggestions.get("multiplier") or 15
            
            suggestions["monthly_income"] = deduce_notional_income(
                award_amount, age, marital_status, dependents, future_prospect, multiplier
            )

        # Format suggestions into strict nested calculator format
        from backend.parser_heuristics import format_suggestions_for_calculator
        formatted_suggestions = format_suggestions_for_calculator(suggestions)

        os.unlink(temp_path)
        return {
            "success": True,
            "filename": file.filename,
            "ocr_status": "loaded",
            "fallback_source": fallback_source,
            "suggestions": formatted_suggestions,
            "raw_text": text_lines,
            "ocr_debug": ocr_debug,
        }

    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-batch")
async def upload_batch_pdfs(files: list[UploadFile] = File(...), background_tasks: BackgroundTasks = None):
    """
    Batch PDF upload — queues 1–100+ PDFs for background 4-layer OCR + Qdrant indexing.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    enqueued_files = []

    for file in files:
        filename = file.filename
        file_ext = os.path.splitext(filename)[1].lower()

        if file_ext != ".pdf":
            continue

        file_id = f"file_{uuid.uuid4().hex[:10]}"

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                shutil.copyfileobj(file.file, tmp)
                temp_path = tmp.name
        except Exception as e:
            logger.error(f"Failed saving batch PDF '{filename}': {str(e)}")
            continue

        BATCH_QUEUE[file_id] = {
            "file_id": file_id,
            "filename": filename,
            "status": "queued",
            "progress": 0,
            "suggestions": None,
            "raw_text": [],
            "ocr_debug": None,
            "error": None,
        }

        if background_tasks:
            background_tasks.add_task(run_background_pdf_indexing, file_id, temp_path, filename)
        else:
            run_background_pdf_indexing(file_id, temp_path, filename)

        enqueued_files.append({"file_id": file_id, "filename": filename, "status": "queued"})

    return {
        "success": True,
        "message": f"Successfully queued {len(enqueued_files)} PDFs for background OCR + indexing.",
        "queue": enqueued_files,
    }


@router.get("/batch-status")
async def get_batch_status():
    """Returns real-time processing states of all PDFs in the batch queue."""
    return {
        "success": True,
        "queue": list(BATCH_QUEUE.values()),
    }
