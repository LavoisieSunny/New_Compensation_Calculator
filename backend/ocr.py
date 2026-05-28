import os
import re
import gc
import shutil
import tempfile
import logging
import uuid
import threading
import numpy as np
from PIL import Image
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pypdf import PdfReader
import pypdfium2 as pdfium

from backend.parser_heuristics import parse_extracted_text
from backend.vector_db import index_document, COLLECTION_NAME

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OCRModule")

router = APIRouter()

# Global PaddleOCR instance (lazy initialized cached singleton)
_ocr_instance = None
OCR_INITIALIZED = False

# Global Batch Upload and Indexing Process Queue
BATCH_QUEUE = {}

# OCR Quality Gate Threshold
OCR_QUALITY_GATE_THRESHOLD = 0.05

# Legal keywords that signal valid legal document content
_LEGAL_QUALITY_KEYWORDS = [
    "tribunal", "claimant", "petitioner", "mact", "mcop", "accident",
    "rs.", "compensation", "disability", "income", "award", "court",
    "deceased", "injured", "monthly", "insurance", "motor", "claim"
]


# ======================================================
# PADDLEOCR SINGLETON INITIALIZATION
# ======================================================

def get_ocr_instance():
    """Returns the cached global singleton PaddleOCR instance."""
    global _ocr_instance, OCR_INITIALIZED
    if _ocr_instance is None:
        try:
            logger.info("Initializing PaddleOCR Singleton (disabling MKLDNN to avoid PIR crashes)...")
            from paddleocr import PaddleOCR
            _ocr_instance = PaddleOCR(lang='en', enable_mkldnn=False)
            OCR_INITIALIZED = True
            logger.info("PaddleOCR Singleton successfully loaded!")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR Singleton: {str(e)}")
            _ocr_instance = None
            OCR_INITIALIZED = False
    return _ocr_instance


# ======================================================
# OCR TIMEOUT GUARD
# ======================================================

def run_with_timeout(func, args=(), kwargs={}, timeout=40.0):
    """
    Runs a function in a daemon thread and enforces a hard timeout limit.
    Protects uvicorn/fastapi request process loops from hung/corrupted OCR pages.
    """
    class FuncThread(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
            self.result = None
            self.exception = None
            self.daemon = True

        def run(self):
            try:
                self.result = func(*args, **kwargs)
            except Exception as e:
                self.exception = e

    thread = FuncThread()
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        logger.warning(f"OCR execution timed out after {timeout} seconds on thread {thread.ident}.")
        return None, "timeout"
    if thread.exception:
        raise thread.exception
    return thread.result, "success"


# ======================================================
# CORE TEXT EXTRACTION — DIGITAL PDF
# ======================================================

def extract_digital_pdf_text(file_path: str) -> list:
    """
    Extracts text lines from a digital (selectable) PDF using PyPDF.
    Extremely fast and 100% accurate for digital PDFs.
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
# VISUAL PAGE CLASSIFIER & ENTROPY CHECK
# ======================================================

def classify_scanned_page(pil_img) -> str:
    """
    Intelligent pre-OCR Page Classifier.
    Analyzes visual entropy (stddev) and edge pixel density.
    Bypasses blank, separator, or low-entropy pages from OCR to protect memory.
    """
    try:
        import cv2
        open_cv_image = np.array(pil_img)
        if len(open_cv_image.shape) == 3:
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = open_cv_image.copy()

        stddev = np.std(gray)
        logger.info(f"Page Classifier: Grayscale standard deviation = {stddev:.2f}")

        # Completely blank scan/separator detection
        if stddev < 7.0:
            return "scanned_blank"

        # Count high-contrast edge/text pixels
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        white_pixels = np.sum(thresh == 255)
        total_pixels = thresh.size
        ratio = white_pixels / total_pixels
        logger.info(f"Page Classifier: Text/Edge pixel ratio = {ratio:.4f}")

        # If less than 0.15% has content, classify as blank
        if ratio < 0.0015:
            return "scanned_blank"

        # If massive dark blocks (large pictures, non-text)
        if ratio > 0.40:
            return "image_only"

        return "dense_text"
    except Exception as e:
        logger.warning(f"Fast page classification failed, defaulting to dense_text: {str(e)}")
        return "dense_text"


# ======================================================
# MAX PAGE MEMORY GUARD (DOWNSCALE GUARD)
# ======================================================

def guard_and_downscale_image(pil_img):
    """
    Automatically scales down extremely high-resolution images to prevent OOM.
    Applies if width > 5000px OR estimated bitmap memory footprint > 120MB.
    """
    width, height = pil_img.size
    est_memory = width * height * 3
    
    if width > 5000 or est_memory > 120 * 1024 * 1024:
        logger.info(f"Max Page Memory Guard Triggered: {width}x{height} image (Est memory: {est_memory / (1024*1024):.1f}MB)")
        # Scale down to a safe width max of 2000px preserving aspect ratio
        ratio = min(2000.0 / width, (120.0 * 1024 * 1024 / est_memory) ** 0.5)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        logger.info(f"Downscaling image to {new_width}x{new_height} for stable execution.")
        return pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return pil_img


# ======================================================
# SAFE PREPROCESSING — LIGHTWEIGHT
# ======================================================

def preprocess_image_light(pil_img, binarize=True):
    """
    Minimal and lightweight preprocessing to prevent massive array allocations.
    Applies only: Grayscale conversion, Light Gaussian denoise, CLAHE, Adaptive threshold.
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

        # 2. Light denoise (Gaussian blur)
        denoised = cv2.GaussianBlur(gray, (3, 3), 0)

        # 3. CLAHE (Contrast Enhancement)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(denoised)

        # 4. Adaptive thresholding
        if binarize:
            processed = cv2.adaptiveThreshold(
                contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
        else:
            processed = contrast

        return Image.fromarray(processed).convert("RGB")
    except Exception as e:
        logger.warning(f"Lightweight preprocessing failed, returning original: {str(e)}")
        return pil_img


# ======================================================
# HIGH-DPI RENDERING & OCR DEBUG UTILITIES
# ======================================================

def render_pdf_page_high_dpi(pdf_path: str, page_idx: int, scale: float = 3.0):
    """
    Renders a specific page of a PDF using pypdfium2.
    Scale 3.0 corresponds exactly to 216 DPI.
    """
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(pdf_path)
        page = doc[page_idx]
        bitmap = page.render(scale=scale)
        logger.info(f"Page {page_idx+1} rendered at scale {scale} (approx {int(scale * 72)} DPI).")
        return bitmap.to_pil()
    except Exception as ex:
        logger.error(f"Failed to render page {page_idx+1} using pypdfium2: {str(ex)}")
        raise ex


def save_ocr_debug_image(filename: str, img):
    """Saves a debug image ONLY if DEBUG_OCR environment variable is true."""
    if os.getenv("DEBUG_OCR", "false").lower() != "true":
        return
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
# OCR RESULT NORMALIZER & CONFIDENCE
# ======================================================

def extract_text_lines_from_paddle_result(result) -> list:
    """Normalizes raw PaddleOCR text lines extraction."""
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


def calculate_paddle_confidence(result) -> float:
    """Calculates the average confidence score from a raw PaddleOCR result."""
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


# ======================================================
# OCR QUALITY SCORING
# ======================================================

def score_ocr_page_quality(text_lines: list) -> float:
    """Scores OCR text output quality based on keywords, line counts, and garble checks."""
    real_lines = [l for l in text_lines if l and not l.startswith("--- PAGE")]
    if not real_lines:
        return 0.0

    line_score = min(len(real_lines) / 10.0, 1.0)
    full_text = " ".join(real_lines).lower()
    kw_hits = sum(1 for kw in _LEGAL_QUALITY_KEYWORDS if kw in full_text)
    keyword_score = min(kw_hits / 5.0, 1.0)

    words = full_text.split()
    if words:
        avg_len = sum(len(w) for w in words) / len(words)
        word_score = 1.0 if 3.0 <= avg_len <= 10.0 else max(0.0, 1.0 - abs(avg_len - 6.5) / 6.5)
    else:
        word_score = 0.0

    avg_line_len = sum(len(l) for l in real_lines) / len(real_lines)
    density_score = min(avg_line_len / 40.0, 1.0)

    quality = (
        (line_score    * 0.30) +
        (keyword_score * 0.35) +
        (word_score    * 0.20) +
        (density_score * 0.15)
    )
    return round(quality, 3)


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
# CONTINGENCY OCR ENGINE — Tesseract Fallback
# ======================================================

_TESSERACT_AVAILABLE = None
_TESSERACT_INITIALIZED = False

def init_tesseract():
    global _TESSERACT_INITIALIZED
    if _TESSERACT_INITIALIZED:
        return
    try:
        import pytesseract
        tess_path = shutil.which("tesseract")
        if tess_path:
            pytesseract.pytesseract.tesseract_cmd = tess_path
            logger.info(f"Tesseract found and configured at: {tess_path}")
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
        pytesseract.get_tesseract_version()
        _TESSERACT_AVAILABLE = True
    except Exception:
        _TESSERACT_AVAILABLE = False
    return _TESSERACT_AVAILABLE


def run_tesseract_fallback(pil_img) -> tuple:
    """Lightweight fallback OCR using Tesseract (pytesseract)."""
    if not is_tesseract_available():
        return [], 0.0
    try:
        import pytesseract
        try:
            text_str = pytesseract.image_to_string(pil_img, lang="eng+hin")
            config_lang = "eng+hin"
        except Exception:
            text_str = pytesseract.image_to_string(pil_img, lang="eng")
            config_lang = "eng"
            
        text_lines = [line.strip() for line in text_str.split("\n") if line.strip()]
        
        confidences = []
        try:
            data = pytesseract.image_to_data(pil_img, lang=config_lang, output_type=pytesseract.Output.DICT)
            if isinstance(data, dict) and 'conf' in data:
                for c in data['conf']:
                    try:
                        val = float(c)
                        if val >= 0:
                            confidences.append(val / 100.0)
                    except ValueError:
                        continue
        except Exception:
            pass
        
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        return text_lines, avg_conf
    except Exception as e:
        logger.warning(f"Tesseract fallback failed: {str(e)}")
        return [], 0.0


# ======================================================
# STABILIZED SEQUENTIAL PAGE OCR STAGE
# ======================================================

def perform_ocr_page_stable(ocr_engine, page_doc, page_idx: int, total_pages: int, pdf_path: str = None) -> tuple:
    """
    Performs stable single-pass OCR on a page.
    1. PYMUPDF Digital Selectable Text Check (TRUST native text first)
    2. Visual Page Classification (Skip blank / separator pages)
    3. Memory downscale guards for extremely large pages
    4. Lightweight preprocessing
    5. Single-pass PaddleOCR at 216 DPI (with timeout guard)
    6. Conditionally allow a 300 DPI retry only if conf < 0.20 and pages <= 3
    7. Basic last-resort Tesseract fallback
    8. Strict page-wise variable deletion and garbage collection
    """
    page_num = page_idx + 1
    logger.info(f"--- START OCR PIPELINE FOR PAGE {page_num}/{total_pages} ---")
    
    # 1. Native Selectable Text Check
    page_text = ""
    if pdf_path:
        try:
            import fitz
            fitz_doc = fitz.open(pdf_path)
            if page_idx < len(fitz_doc):
                page_text = fitz_doc[page_idx].get_text()
        except Exception as e:
            logger.warning(f"PyMuPDF text extraction failed on page {page_num}: {str(e)}")

    if len(page_text.strip()) > 200:
        # Verify text quality
        keywords = ["court", "claimant", "petitioner", "respondent", "accident", "compensation", "tribunal", "judgment", "deceased", "injured"]
        hits = sum(1 for kw in keywords if kw in page_text.lower())
        if hits >= 2:
            logger.info(f"Page {page_num}: TRUST native PyMuPDF text (len={len(page_text)}, keyword_hits={hits}). Bypassing OCR.")
            lines = [l.strip() for l in page_text.split("\n") if l.strip()]
            page_meta = {
                "page": page_num,
                "engine": "PyMuPDF",
                "dpi": 72,
                "confidence": 1.0,
                "text_length": len(page_text),
                "quality_score": 1.0,
                "preprocessing_applied": [],
                "lines": len(lines)
            }
            return lines, page_meta

    # 2. Render Page image at 216 DPI (scale=3.0)
    pil_img = None
    try:
        pil_img = render_pdf_page_high_dpi(pdf_path, page_idx, scale=3.0) if pdf_path else page_doc.render(scale=3.0).to_pil()
    except Exception as e:
        logger.error(f"Failed to render page {page_num} at 216 DPI: {str(e)}")
        return [], {"page": page_num, "engine": "Error", "confidence": 0.0, "lines": 0}

    # 3. Visual Page Classifier (Skip blank scans)
    classification = classify_scanned_page(pil_img)
    if classification in ["scanned_blank", "image_only"]:
        logger.info(f"Page {page_num}: Classified as {classification}. Bypassing OCR entirely.")
        del pil_img
        gc.collect()
        return [], {
            "page": page_num,
            "engine": f"Skipped-{classification}",
            "dpi": 0,
            "confidence": 1.0,
            "text_length": 0,
            "quality_score": 0.0,
            "preprocessing_applied": [],
            "lines": 0
        }

    # 4. Max Page Memory Guard (Downscale Guard)
    pil_img = guard_and_downscale_image(pil_img)

    # 5. Lightweight Preprocessing
    processed_img = preprocess_image_light(pil_img, binarize=True)
    
    # Debug image conditional writes
    save_ocr_debug_image(f"debug_original_{page_num}.png", pil_img)
    save_ocr_debug_image(f"debug_processed_{page_num}.png", processed_img)

    # 6. Single Pass PaddleOCR with Timeout Guard (40 seconds max)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    processed_img.save(temp_file)
    
    lines = []
    conf = 0.0
    engine_used = "PaddleOCR"
    dpi_used = 216
    
    def run_paddle():
        engine = get_ocr_instance()
        if engine:
            return engine.ocr(temp_file)
        return None

    try:
        result, status = run_with_timeout(run_paddle, timeout=40.0)
        if status == "timeout":
            logger.warning(f"PaddleOCR timed out on page {page_num} after 40 seconds. Aborting page safely.")
            result = None

        if result:
            lines = extract_text_lines_from_paddle_result(result)
            conf = calculate_paddle_confidence(result)
            if conf == 0.00 and len(lines) >= 15:
                conf = 0.85
    except Exception as e:
        logger.error(f"PaddleOCR execution failed on page {page_num}: {str(e)}")
    finally:
        try:
            os.unlink(temp_file)
        except Exception:
            pass

    # 7. Optional 300 DPI Retry (ONLY if confidence < 0.20 and total pages <= 3)
    if len(lines) == 0 or (conf < 0.20 and total_pages <= 3):
        logger.info(f"Page {page_num}: Low confidence/empty. Retrying at 300 DPI (short doc safety).")
        try:
            pil_300 = render_pdf_page_high_dpi(pdf_path, page_idx, scale=4.167) if pdf_path else page_doc.render(scale=4.167).to_pil()
            pil_300 = guard_and_downscale_image(pil_300)
            processed_300 = preprocess_image_light(pil_300, binarize=True)
            
            save_ocr_debug_image(f"debug_processed_300_{page_num}.png", processed_300)
            temp_file_300 = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
            processed_300.save(temp_file_300)
            
            def run_paddle_300():
                engine = get_ocr_instance()
                if engine:
                    return engine.ocr(temp_file_300)
                return None
                
            result_300, status_300 = run_with_timeout(run_paddle_300, timeout=40.0)
            if result_300:
                lines = extract_text_lines_from_paddle_result(result_300)
                conf = calculate_paddle_confidence(result_300)
                if conf == 0.00 and len(lines) >= 15:
                    conf = 0.85
                dpi_used = 300
                logger.info(f"300 DPI retry successful: {len(lines)} lines, conf={conf:.2f}")
            
            try:
                os.unlink(temp_file_300)
            except Exception:
                pass
            del pil_300, processed_300
        except Exception as err300:
            logger.error(f"300 DPI retry failed: {str(err300)}")

    # 8. Last-resort basic Tesseract fallback
    if len(lines) == 0 and is_tesseract_available():
        logger.info(f"Page {page_num}: PaddleOCR returned empty. Running last-resort Tesseract fallback.")
        try:
            lines, conf = run_tesseract_fallback(processed_img)
            engine_used = "Tesseract"
        except Exception as tess_err:
            logger.error(f"Tesseract fallback failed: {str(tess_err)}")

    # 9. Strict page-wise memory cleanup
    del pil_img, processed_img
    gc.collect()
    
    page_meta = {
        "page": page_num,
        "engine": engine_used,
        "dpi": dpi_used,
        "confidence": round(conf, 3),
        "text_length": sum(len(l) for l in lines),
        "quality_score": score_ocr_page_quality(lines),
        "preprocessing_applied": ["grayscale", "adaptive_threshold", "light_denoise"],
        "lines": len(lines)
    }
    
    logger.info(f"Page {page_num} completed. lines={len(lines)}, conf={conf:.2f}")
    return lines, page_meta


def perform_ocr_page_with_retry(ocr_engine, page_doc, page_idx: int, total_pages: int, pdf_path: str = None) -> tuple:
    """Alias for backwards compatibility with scratch scripts."""
    return perform_ocr_page_stable(ocr_engine, page_doc, page_idx, total_pages, pdf_path)


# ======================================================
# INTELLIGENT PAGE PRE-SCANNING
# ======================================================

def find_relevant_pages_by_keywords(file_path: str, total_pages: int) -> list:
    """Searches middle pages for key motor claims keywords to prioritize them in OCR queue."""
    relevant_pages = []
    comp_keywords = [
        "compensation", "dependency", "multiplier", "consortium", 
        "funeral", "monthly income", "disability", "loss of earning",
        "quantum", "awarded sum", "loss of future", "future prospect",
        "medical expenses", "pain and suffering"
    ]
    
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
                        logger.info(f"Dynamically added page {page_idx+1} to OCR queue.")
    except Exception as e:
        logger.warning(f"Intelligent page scanning failed: {str(e)}")
        
    return relevant_pages


# ======================================================
# SCANNED PDF OCR PIPELINE
# ======================================================

def perform_ocr_on_scanned_pdf(file_path: str, progress_callback=None, scan_all_pages: bool = False) -> tuple:
    """
    Sequentially renders and processes relevant pages of a scanned PDF.
    Excludes procedural or summons pages, processes sequentially with direct memory cleanups.
    """
    ocr_engine = get_ocr_instance()

    if ocr_engine is None:
        logger.warning("PaddleOCR offline. Returning empty result.")
        return [], _build_ocr_debug(
            engine_used="unavailable", retry_count=0, quality_score=0.0,
            failed_pages=[], successful_pages=[], preprocessing_applied=[],
            fallback_ocr_engine="none", text_density_score=0.0
        )

    try:
        doc = pdfium.PdfDocument(file_path)
        total_pages = len(doc)
        logger.info(f"Scanned PDF '{file_path}' ({total_pages} pages): sequential stable OCR pipeline...")

        # Optimization: scan first 12 + last 8 + dynamically found keyword pages
        if total_pages > 10 and not scan_all_pages:
            base_pages = list(range(12)) + list(range(total_pages - 8, total_pages))
            dynamic_pages = find_relevant_pages_by_keywords(file_path, total_pages)
            pages_to_scan = sorted(set(base_pages + dynamic_pages))
            logger.info(f"Large PDF detected. Scanning pages: {[p+1 for p in pages_to_scan]}")
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
        
        # Process pages strictly sequentially (no multiprocessing, no thread pools)
        for idx, page_idx in enumerate(pages_to_scan):
            page_num = page_idx + 1
            text_lines.append(f"--- PAGE {page_num} ---")
            
            # Run stable pipeline on page
            page_lines, page_meta = perform_ocr_page_stable(
                ocr_engine, doc[page_idx], page_idx, total_pages, pdf_path=file_path
            )

            q = page_meta.get("quality_score", 0.0)
            conf = page_meta.get("confidence", 0.0)
            engine = page_meta.get("engine", "PaddleOCR")
            
            page_qualities.append(q)
            page_confidences.append(conf)

            logger.info(f"Page {page_num}/{total_pages}: engine={engine}, quality={q:.2f}, lines={len(page_lines)}")
            page_details.append(page_meta)

            if engine in ["Tesseract", "EasyOCR"]:
                total_retry_count += 1
                fallback_engine_used = engine

            for step in page_meta.get("preprocessing_applied", []):
                if step not in all_preprocessing_steps:
                    all_preprocessing_steps.append(step)

            if page_lines:
                successful_pages.append(page_num)
            else:
                failed_pages.append(page_num)

            text_lines.extend(page_lines)

            if progress_callback:
                progress_callback(int(((idx + 1) / len(pages_to_scan)) * 90))

        overall_quality = round(sum(page_qualities) / len(page_qualities), 4) if page_qualities else 0.0
        overall_conf = round(sum(page_confidences) / len(page_confidences), 4) if page_confidences else 0.0
        real_lines = [l for l in text_lines if not l.startswith("--- PAGE")]
        text_density = round(
            sum(len(l) for l in real_lines) / max(len(real_lines), 1) / 80.0, 3
        ) if real_lines else 0.0

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
    """Runs the stable single-page OCR pipeline directly on uploaded image (PNG, JPG, BMP)."""
    ocr_engine = get_ocr_instance()

    if ocr_engine is None:
        logger.warning("PaddleOCR offline. Returning empty result.")
        return [], _build_ocr_debug(
            engine_used="unavailable", retry_count=0, quality_score=0.0,
            failed_pages=[1], successful_pages=[], preprocessing_applied=[],
            fallback_ocr_engine="none", text_density_score=0.0
        )

    try:
        original_pil = Image.open(file_path)
        logger.info(f"Image upload '{file_path}': starting OCR pipeline...")
        
        # Max Page Memory Guard (Downscale Guard)
        original_pil = guard_and_downscale_image(original_pil)
        
        # Lightweight Preprocessing
        processed_img = preprocess_image_light(original_pil, binarize=True)
        
        save_ocr_debug_image("debug_original_1.png", original_pil)
        save_ocr_debug_image("debug_processed_1.png", processed_img)
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        processed_img.save(temp_file)
        
        lines = []
        conf = 0.0
        engine_used = "PaddleOCR"
        
        def run_paddle():
            engine = get_ocr_instance()
            if engine:
                return engine.ocr(temp_file)
            return None
            
        try:
            result, status = run_with_timeout(run_paddle, timeout=40.0)
            if status == "timeout":
                logger.warning("PaddleOCR timed out on image upload.")
                result = None
                
            if result:
                lines = extract_text_lines_from_paddle_result(result)
                conf = calculate_paddle_confidence(result)
                if conf == 0.00 and len(lines) >= 15:
                    conf = 0.85
        except Exception as e:
            logger.error(f"Image PaddleOCR failed: {str(e)}")
        finally:
            try:
                os.unlink(temp_file)
            except Exception:
                pass

        # Last-resort Tesseract Fallback
        if len(lines) == 0 and is_tesseract_available():
            logger.info("Image PaddleOCR returned empty. Running last-resort Tesseract fallback.")
            try:
                lines, conf = run_tesseract_fallback(processed_img)
                engine_used = "Tesseract"
            except Exception as e:
                logger.error(f"Tesseract image fallback failed: {str(e)}")

        # Explicit Memory Cleanup
        del original_pil, processed_img
        gc.collect()
        
        failed_pages = [] if lines else [1]
        successful_pages = [1] if lines else []
        
        page_details = [{
            "page": 1,
            "engine": engine_used,
            "dpi": 216,
            "confidence": round(conf, 3),
            "text_length": sum(len(l) for l in lines),
            "quality_score": score_ocr_page_quality(lines),
            "preprocessing_applied": ["grayscale", "adaptive_threshold", "light_denoise"],
            "lines": len(lines)
        }]

        ocr_debug = _build_ocr_debug(
            engine_used="PaddleOCR",
            retry_count=1 if engine_used == "Tesseract" else 0,
            quality_score=score_ocr_page_quality(lines),
            failed_pages=failed_pages,
            successful_pages=successful_pages,
            preprocessing_applied=["grayscale", "adaptive_threshold", "light_denoise"],
            fallback_ocr_engine=engine_used if engine_used != "PaddleOCR" else "",
            text_density_score=min(len(lines) / 30.0, 1.0),
            average_page_confidence=conf,
            raw_ocr_preview="\n".join(lines)[:3000],
            pages=page_details
        )

        return lines, ocr_debug

    except Exception as e:
        logger.error(f"Error running OCR on image: {str(e)}")
        return [], _build_ocr_debug(
            "PaddleOCR", 0, 0.0, [1], [], [], "none", 0.0
        )


# ======================================================
# HEURISTIC UTILITIES & SAFETY GATE
# ======================================================

def is_extracted_text_sparse(text_lines: list) -> bool:
    """
    Returns True if extracted text has fewer than 15 lines
    OR if the text is detected as heavily garbled (poor quality digital layers).
    """
    actual = [l for l in text_lines if not l.strip().startswith("--- PAGE")]
    if len(actual) < 15:
        return True

    full_text = " ".join(actual).lower()
    legal_keywords = ["tribunal", "claimant", "petitioner", "accident", "compensation", "deceased", "injured", "insurance", "award", "judgment"]
    kw_hits = sum(1 for kw in legal_keywords if kw in full_text)
    
    words = [w for w in full_text.split() if w]
    if not words:
        return True
        
    avg_word_len = sum(len(w) for w in words) / len(words)
    gibberish_words = sum(1 for w in words if len(w) > 15 or any(c in w for c in '@#$[]{}|'))
    gibberish_ratio = gibberish_words / len(words)
    
    is_poor_quality = (
        (kw_hits < 3 and len(actual) > 50) or
        (gibberish_ratio > 0.05) or
        (avg_word_len > 12.0) or
        (avg_word_len < 2.5 and len(actual) > 50)
    )
    if is_poor_quality:
        logger.info(
            f"Digital text layer poor quality (hits={kw_hits}, gibberish_ratio={gibberish_ratio:.2f}, len={avg_word_len:.1f}). Triggering OCR fallback."
        )
        return True
        
    return False


def extract_award_amount_from_text(text_lines: list) -> float:
    """Extracts explicit tribunal award amount, bypassing advocate or claimant claims."""
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
            
            # Context window exclusion (skips claim demands)
            start_pos = max(0, match.start() - 60)
            pre_ctx = full_text_lower[start_pos:match.start()]
            
            if any(kw in pre_ctx for kw in ["claim", "claiming", "sought", "demand", "demanded", "prayed", "prayer", "valuation"]):
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
                    continue
                
            candidates.append(val)
            
        if candidates:
            valid_candidates = [c for c in candidates if c >= 5000]
            if valid_candidates:
                return valid_candidates[0]
                
    return 0.0


def apply_ocr_quality_gate(suggestions: dict, ocr_debug: dict) -> dict:
    """Quality safety check to raise warnings if quality score is extremely low."""
    quality = ocr_debug.get("ocr_quality_score", 1.0)
    suggestions["ocr_quality_insufficient"] = quality < OCR_QUALITY_GATE_THRESHOLD

    if quality < OCR_QUALITY_GATE_THRESHOLD:
        suggestions["ocr_warning"] = f"OCR quality low (score: {quality:.2f}). Running in partial recovery mode."
        suggestions["partial_extraction_recovery_mode"] = True

    return suggestions


# ======================================================
# BACKGROUND BATCH INDEXING PIPELINE
# ======================================================

def run_background_pdf_indexing(file_id: str, temp_path: str, filename: str):
    """Background worker indexing PDFs sequentially into Qdrant."""
    try:
        BATCH_QUEUE[file_id]["status"] = "scanning"
        BATCH_QUEUE[file_id]["progress"] = 20

        # 1. Selectable text extraction
        text_lines = extract_digital_pdf_text(temp_path)
        fallback_source = "DigitalPDF"
        ocr_debug = _build_ocr_debug("DigitalPDF", 0, 1.0, [], [], [], "", 0.0)

        # 2. Scanned OCR Escalation (scan_all_pages=True for comprehensive index)
        if is_extracted_text_sparse(text_lines):
            logger.info(f"Selectable text sparse. Running sequential stable OCR for {filename}")

            def report_progress(prog_percent):
                BATCH_QUEUE[file_id]["progress"] = prog_percent

            text_lines, ocr_debug = perform_ocr_on_scanned_pdf(
                temp_path, progress_callback=report_progress, scan_all_pages=True
            )
            fallback_source = "PaddleOCR"

        # 3. Alternate Layout fallback
        if is_extracted_text_sparse(text_lines):
            alt_lines = extract_alternate_pdf_text(temp_path)
            if len(alt_lines) > len(text_lines):
                text_lines = alt_lines
                fallback_source = "AlternateOCR"
                ocr_debug["fallback_ocr_engine"] = "PyMuPDF/pdfplumber"
                ocr_debug["ocr_quality_score"] = 1.0

        BATCH_QUEUE[file_id]["progress"] = 90

        # Heuristic parsing
        suggestions = parse_extracted_text(text_lines)
        suggestions = apply_ocr_quality_gate(suggestions, ocr_debug)

        if suggestions.get("ai_recovery_triggered", False):
            fallback_source = "RealTextRecovery"
        suggestions["fallback_source_used"] = fallback_source

        # Extract true judicial award
        award_amount = extract_award_amount_from_text(text_lines)
        if award_amount > 0:
            suggestions["award_amount"] = award_amount
            suggestions["total_compensation"] = award_amount
            
            from backend.parser_heuristics import deduce_notional_income
            age = suggestions.get("age") or 30
            marital_status = suggestions.get("marital_status") or "married"
            dependents = suggestions.get("dependents") or ""
            future_prospect = suggestions.get("future_prospect") or 25.0
            multiplier = suggestions.get("multiplier") or 15
            
            suggestions["monthly_income"] = deduce_notional_income(
                award_amount, age, marital_status, dependents, future_prospect, multiplier
            )

        BATCH_QUEUE[file_id]["status"] = "indexing"
        success = index_document(filename, text_lines, suggestions)

        from backend.parser_heuristics import format_suggestions_for_calculator
        formatted_suggestions = format_suggestions_for_calculator(suggestions)

        if os.path.exists(temp_path):
            os.unlink(temp_path)

        if success:
            BATCH_QUEUE[file_id]["status"] = "indexed"
            BATCH_QUEUE[file_id]["progress"] = 100
            BATCH_QUEUE[file_id]["suggestions"] = formatted_suggestions
            BATCH_QUEUE[file_id]["raw_text"] = text_lines
            BATCH_QUEUE[file_id]["ocr_debug"] = ocr_debug
        else:
            BATCH_QUEUE[file_id]["status"] = "failed"
            BATCH_QUEUE[file_id]["error"] = "Indexing insertion failed."

    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        BATCH_QUEUE[file_id]["status"] = "failed"
        BATCH_QUEUE[file_id]["error"] = str(e)
        logger.error(f"Background task failed for {filename}: {str(e)}")


# ======================================================
# API ENDPOINTS
# ======================================================

@router.post("/process-ocr")
async def process_single_file(file: UploadFile = File(...)):
    """Synchronous single file handler implementing identical frontend contracts."""
    file_ext = os.path.splitext(file.filename)[1].lower()
    allowed_images = {".png", ".jpg", ".jpeg", ".bmp"}
    allowed_docs = {".pdf"}

    if file_ext not in allowed_images and file_ext not in allowed_docs:
        raise HTTPException(
            status_code=400,
            detail="Only PNG, JPG, BMP and PDF formats are supported."
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Saving upload failed: {str(e)}")

    try:
        fallback_source = "DigitalPDF"
        ocr_debug = _build_ocr_debug("DigitalPDF", 0, 1.0, [], [], [], "", 0.0)

        if file_ext == ".pdf":
            # 1. Digitalselectable check
            text_lines = extract_digital_pdf_text(temp_path)

            # 2. OCR retry escalation
            if is_extracted_text_sparse(text_lines):
                text_lines, ocr_debug = perform_ocr_on_scanned_pdf(temp_path)
                fallback_source = "PaddleOCR"

            # 3. Alternate Layout fallback
            if is_extracted_text_sparse(text_lines):
                alt_lines = extract_alternate_pdf_text(temp_path)
                if len(alt_lines) > len(text_lines):
                    text_lines = alt_lines
                    fallback_source = "AlternateOCR"
                    ocr_debug["fallback_ocr_engine"] = "PyMuPDF/pdfplumber"
                    ocr_debug["ocr_quality_score"] = 1.0
        else:
            text_lines, ocr_debug = perform_ocr_on_image(temp_path)
            fallback_source = "PaddleOCR"

        suggestions = parse_extracted_text(text_lines)
        suggestions = apply_ocr_quality_gate(suggestions, ocr_debug)

        if suggestions.get("ai_recovery_triggered", False):
            fallback_source = "RealTextRecovery"
        suggestions["fallback_source_used"] = fallback_source

        award_amount = extract_award_amount_from_text(text_lines)
        if award_amount > 0:
            suggestions["award_amount"] = award_amount
            suggestions["total_compensation"] = award_amount
            
            from backend.parser_heuristics import deduce_notional_income
            age = suggestions.get("age") or 30
            marital_status = suggestions.get("marital_status") or "married"
            dependents = suggestions.get("dependents") or ""
            future_prospect = suggestions.get("future_prospect") or 25.0
            multiplier = suggestions.get("multiplier") or 15
            
            suggestions["monthly_income"] = deduce_notional_income(
                award_amount, age, marital_status, dependents, future_prospect, multiplier
            )

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
    """Batch PDF upload for background sequential OCR indexing."""
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
    """Returns batch processing queue status updates."""
    return {
        "success": True,
        "queue": list(BATCH_QUEUE.values()),
    }
