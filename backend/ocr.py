import os
import re
import gc
import time
import shutil
import tempfile
import logging
import uuid
import threading
import psutil
import numpy as np
from PIL import Image
import asyncio
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pypdf import PdfReader
import pypdfium2 as pdfium

# Optimize PaddlePaddle and system memory footprints to prevent OOM process kills on low-RAM VPS servers
os.environ["FLAGS_use_mkldnn"]                       = "0"
os.environ["FLAGS_enable_pir_in_executor"]            = "0"
os.environ["FLAGS_pir_apply_shape_optimization_pass"] = "0"
os.environ["FLAGS_allocator_strategy"]                = "naive_best_fit"


from backend.parser_heuristics import parse_extracted_text
from backend.vector_db import index_document, COLLECTION_NAME

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OCRModule")

router = APIRouter()

# Configurable OCR Options (Phase 1 stabilization)
OCR_PRIMARY_ENGINE = os.getenv("OCR_PRIMARY_ENGINE", "paddle").lower()  # 'paddle' or 'tesseract'
OCR_RENDER_DPI = int(os.getenv("OCR_RENDER_DPI", "180"))
OCR_PAGE_TIMEOUT = float(os.getenv("OCR_PAGE_TIMEOUT", "60"))
OCR_MAX_PAGES_FIRST_PASS = int(os.getenv("OCR_MAX_PAGES_FIRST_PASS", "10"))
OCR_MAX_PARALLEL_WORKERS = int(os.getenv("OCR_MAX_PARALLEL_WORKERS", "5"))
OCR_RETRY_DPI = int(os.getenv("OCR_RETRY_DPI", "216"))
DEBUG_OCR = os.getenv("DEBUG_OCR", "false").lower() == "true"

# Global PaddleOCR instance (lazy initialized cached singleton)
_ocr_lock = threading.Lock()
_ocr_instance = None
OCR_INITIALIZED = False
_paddle_semaphore = threading.Semaphore(1)  # only 1 paddle call at a time

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
    global _ocr_instance, OCR_INITIALIZED
    if _ocr_instance is not None:
        return _ocr_instance
    with _ocr_lock:
        if _ocr_instance is None:  # double-checked locking
            try:
                logger.info("Initializing PaddleOCR Singleton...")
                from paddleocr import PaddleOCR
                _ocr_instance = PaddleOCR(
                    use_textline_orientation=True,
                    text_detection_model_name="PP-OCRv5_mobile_det",
                    text_recognition_model_name="en_PP-OCRv5_mobile_rec",
                )
                OCR_INITIALIZED = True
                logger.info("PaddleOCR Singleton loaded!")
            except Exception as e:
                logger.error(f"PaddleOCR init failed: {e}")
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
        with fitz.open(file_path) as doc:
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
    Intelligent pre-OCR Page Classifier returning: 'blank', 'low-content', 'text-heavy', or 'image-heavy'.
    Bypasses blank pages from OCR entirely to protect memory.
    """
    try:
        import cv2
        open_cv_image = np.array(pil_img)
        if len(open_cv_image.shape) == 3:
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = open_cv_image.copy()

        variance = np.var(gray)
        stddev = np.std(gray)
        logger.info(f"Page Classifier: Grayscale variance = {variance:.2f}, stddev = {stddev:.2f}")

        # Blank/separator detection (extremely low variance or stddev)
        if variance < 50.0 or stddev < 7.0:
            classification = "blank"
        else:
            # Count high-contrast edge/text pixels
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            white_pixels = np.sum(thresh == 255)
            total_pixels = thresh.size
            ratio = white_pixels / total_pixels
            logger.info(f"Page Classifier: Text/Edge pixel ratio = {ratio:.4f}")

            # If less than 0.15% has content, classify as blank
            if ratio < 0.0015:
                classification = "blank"
            # Low-content / minimal text (Tesseract primary)
            elif ratio < 0.03:
                classification = "low-content"
            # Text-heavy page
            elif ratio <= 0.25:
                classification = "text-heavy"
            # Image-heavy page
            else:
                classification = "image-heavy"
            
            del thresh

        del open_cv_image, gray
        gc.collect()
        return classification
    except Exception as e:
        logger.warning(f"Fast page classification failed, defaulting to text-heavy: {str(e)}")
        return "text-heavy"
# ======================================================
# MAX PAGE MEMORY GUARD (DOWNSCALE GUARD)
# ======================================================

def guard_and_downscale_image(pil_img):
    """
    Automatically scales down extremely high-resolution images to prevent OOM.
    Applies if estimated bitmap memory footprint > 80MB.
    """
    width, height = pil_img.size
    est_memory = width * height * 3
    
    if est_memory > 80 * 1024 * 1024:
        logger.info(f"Max Page Memory Guard Triggered: {width}x{height} image (Est memory: {est_memory / (1024*1024):.1f}MB)")
        # Scale down to a safe width max of 1800px preserving aspect ratio
        ratio = min(1800.0 / width, (80.0 * 1024 * 1024 / est_memory) ** 0.5)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        logger.info(f"Downscaling image to {new_width}x{new_height} for stable execution.")
        return pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return pil_img


# ======================================================
# SAFE PREPROCESSING — LIGHTWEIGHT
# ======================================================

def preprocess_image_light(pil_img, binarize=False):
    """
    Minimal and lightweight preprocessing to prevent massive array allocations.
    Applies only: Grayscale conversion, Light Gaussian denoise, CLAHE, Otsu threshold.
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

        # 4. Otsu binarization thresholding
        if binarize:
            _, processed = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            processed = contrast

        result_img = Image.fromarray(processed).convert("RGB")
        
        # Clean up local NumPy allocations
        del open_cv_image, gray, denoised, contrast
        if binarize:
            del processed
        gc.collect()
        
        return result_img
    except Exception as e:
        logger.warning(f"Lightweight preprocessing failed, returning original: {str(e)}")
        return pil_img


# ======================================================
# HIGH-DPI RENDERING & OCR DEBUG UTILITIES
# ======================================================

def render_pdf_page_high_dpi(pdf_path: str, page_idx: int, scale: float = 3.0):
    """
    Renders a specific page of a PDF using pypdfium2.
    """
    try:
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(pdf_path) as doc:
            page = doc[page_idx]
            bitmap = page.render(scale=scale)
            logger.info(f"Page {page_idx+1} rendered at scale {scale} (approx {int(scale * 72)} DPI).")
            pil_img = bitmap.to_pil()
            del page, bitmap
            gc.collect()
            return pil_img
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


def extract_ocr_boxes_from_paddle_result(result) -> list:
    """Normalizes raw PaddleOCR results to extract unified bounding box coordinates."""
    boxes = []
    if not result or len(result) == 0:
        return boxes
    
    for item in result:
        if isinstance(item, list):
            for line in item:
                if isinstance(line, list) and len(line) > 1 and isinstance(line[1], tuple):
                    # line[0] is coordinates [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                    # line[1] is (text, confidence)
                    boxes.append({
                        "box": line[0],
                        "text": line[1][0],
                        "confidence": line[1][1]
                    })
    return boxes


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
    pages: list = None,
    total_ocr_time: float = 0.0
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
        "pages": pages or [],
        "total_ocr_time": round(total_ocr_time, 2)
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


def run_tesseract_fallback(pil_img, extract_boxes=False) -> tuple:
    """
    Lightweight fallback OCR using Tesseract (pytesseract).
    Uses a temporary file inside a try-finally context manager to guarantee cleanup.
    Returns (text_lines, avg_conf, ocr_boxes).
    """
    if not is_tesseract_available():
        return [], 0.0, []
    
    temp_path = None
    try:
        import pytesseract
        
        # Save image to a temporary file safely
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            pil_img.save(temp_path)
            
        try:
            text_str = pytesseract.image_to_string(temp_path, lang="eng+hin", config="--oem 1 --psm 6")
            config_lang = "eng+hin"
        except Exception:
            text_str = pytesseract.image_to_string(temp_path, lang="eng", config="--oem 1 --psm 6")
            config_lang = "eng"
            
        text_lines = [line.strip() for line in text_str.split("\n") if line.strip()]
        
        confidences = []
        ocr_boxes = []
        try:
            if extract_boxes:
                data = pytesseract.image_to_data(temp_path, lang=config_lang, config="--oem 1 --psm 6", output_type=pytesseract.Output.DICT)
                if isinstance(data, dict) and 'text' in data:
                    n_boxes = len(data['text'])
                    for i in range(n_boxes):
                        text = data['text'][i].strip()
                        if not text:
                            continue
                        left = data['left'][i]
                        top = data['top'][i]
                        width = data['width'][i]
                        height = data['height'][i]
                        conf = float(data['conf'][i]) / 100.0 if 'conf' in data else 1.0
                        
                        if conf >= 0.0:
                            confidences.append(conf)
                        
                        # Convert to standard 4-corner box: top-left, top-right, bottom-right, bottom-left
                        box = [
                            [left, top],
                            [left + width, top],
                            [left + width, top + height],
                            [left, top + height]
                        ]
                        ocr_boxes.append({
                            "box": box,
                            "text": text,
                            "confidence": conf
                        })
        except Exception as e:
            logger.warning(f"Failed to extract Tesseract word boxes: {str(e)}")
        
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        return text_lines, avg_conf, ocr_boxes
    except Exception as e:
        logger.warning(f"Tesseract fallback failed: {str(e)}")
        return [], 0.0, []
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete Tesseract temporary file {temp_path}: {str(e)}")


# ======================================================
# STABILIZED SEQUENTIAL PAGE OCR STAGE
# ======================================================

def perform_ocr_page_stable(ocr_engine, page_doc, page_idx: int, total_pages: int, pdf_path: str = None, dpi: int = None, fitz_text_cache: list = None) -> tuple:
    """
    Performs stable single-pass OCR on a page.
    1. PYMUPDF Digital Selectable Text Check (TRUST native text first via fitz_text_cache or opening doc)
    2. Visual Page Classification (Skip blank / separator pages)
    3. Memory downscale guards for extremely large pages
    4. Lightweight preprocessing (Grayscale + Contrast Enhancement, binarize=False)
    5. Single-pass OCR at specified DPI using Direct Numpy Feed and cls=False
    6. Primary / Fallback failover strategy (PaddleOCR -> Tesseract)
    7. Strict page-wise variable deletion and garbage collection
    """
    if dpi is None:
        dpi = OCR_RENDER_DPI

    page_num = page_idx + 1
    logger.info(f"--- START OCR PIPELINE FOR PAGE {page_num}/{total_pages} (DPI={dpi}) ---")
    start_time = time.time()
    
    # 1. Native Selectable Text Check
    page_text = ""
    if fitz_text_cache and page_idx < len(fitz_text_cache):
        page_text = fitz_text_cache[page_idx]
    elif pdf_path:
        try:
            import fitz
            with fitz.open(pdf_path) as fitz_doc:
                if page_idx < len(fitz_doc):
                    page_text = fitz_doc[page_idx].get_text()
        except Exception as e:
            logger.warning(f"PyMuPDF text extraction failed on page {page_num}: {str(e)}")

    if len(page_text.strip()) > 200:
        # Verify text quality
        keywords = ["court", "claimant", "petitioner", "respondent", "accident", "compensation", "tribunal", "judgment", "deceased", "injured"]
        hits = sum(1 for kw in keywords if kw in page_text.lower())
        if hits >= 2:
            elapsed = time.time() - start_time
            try:
                ram_mb = int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
                ram_str = f"{ram_mb}MB"
            except Exception:
                ram_str = "N/A"
            logger.info(f"Page {page_num}: TRUST native PyMuPDF text (len={len(page_text)}, keyword_hits={hits}). Bypassing OCR.")
            logger.info(f"\nPage {page_num}\nEngine=PyMuPDF\nTime={elapsed:.1f}s\nConfidence=1.0\nRAM={ram_str}\n")
            lines = [l.strip() for l in page_text.split("\n") if l.strip()]
            page_meta = {
                "page": page_num,
                "engine": "PyMuPDF",
                "dpi": 72,
                "confidence": 1.0,
                "text_length": len(page_text),
                "quality_score": 1.0,
                "preprocessing_applied": [],
                "lines": len(lines),
                "ocr_boxes": [],  # Native selectable PDF pages don't need overlay boxes
                "render_time": 0.0,
                "ocr_time": elapsed,
                "total_page_time": elapsed
            }
            return lines, page_meta

    # 2. Render Page image at specified DPI
    render_start = time.time()
    pil_img = None
    scale = dpi / 72.0
    try:
        if page_doc:
            bitmap = page_doc.render(scale=scale)
            pil_img = bitmap.to_pil()
            del bitmap
        else:
            pil_img = render_pdf_page_high_dpi(pdf_path, page_idx, scale=scale)
    except Exception as e:
        logger.error(f"Failed to render page {page_num} at DPI {dpi}: {str(e)}")
        return [], {"page": page_num, "engine": "Error", "confidence": 0.0, "lines": 0, "ocr_boxes": [], "render_time": time.time() - render_start, "ocr_time": 0.0, "total_page_time": time.time() - start_time}
    render_time = time.time() - render_start

    # 3. Visual Page Classifier (Skip blank scans)
    classification = classify_scanned_page(pil_img)
    if classification == "blank":
        elapsed = time.time() - start_time
        try:
            ram_mb = int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
            ram_str = f"{ram_mb}MB"
        except Exception:
            ram_str = "N/A"
        logger.info(f"Page {page_num}: Classified as blank. Bypassing OCR entirely.")
        logger.info(f"\nPage {page_num}\nEngine=Skipped-blank\nTime={elapsed:.1f}s\nConfidence=1.0\nRAM={ram_str}\n")
        del pil_img
        gc.collect()
        return [], {
            "page": page_num,
            "engine": "Skipped-blank",
            "dpi": 0,
            "confidence": 1.0,
            "text_length": 0,
            "quality_score": 0.0,
            "preprocessing_applied": [],
            "lines": 0,
            "ocr_boxes": [],
            "render_time": render_time,
            "ocr_time": 0.0,
            "total_page_time": elapsed
        }

    # 4. Max Page Memory Guard (Downscale Guard)
    pil_img = guard_and_downscale_image(pil_img)

    # 5. Lightweight Preprocessing (Apply grayscale + contrast enhancement without hard Otsu binarization)
    processed_img = preprocess_image_light(pil_img, binarize=False)
    
    # Debug image conditional writes
    save_ocr_debug_image(f"debug_original_{page_num}.png", pil_img)
    save_ocr_debug_image(f"debug_processed_{page_num}.png", processed_img)

    lines = []
    conf = 0.0
    ocr_boxes = []
    engine_used = ""
    
    ocr_start = time.time()
    # 6. Primary / Fallback strategy
    if classification == "low-content":
        logger.info(f"Page {page_num}: Classified as low-content. Routing directly to Tesseract.")
        try:
            lines, conf, ocr_boxes = run_tesseract_fallback(processed_img, extract_boxes=False)
            engine_used = "Tesseract"
        except Exception as e:
            logger.error(f"Direct Tesseract run failed on page {page_num}: {str(e)}")
    else:
        logger.info(f"Page {page_num}: Classified as {classification}. Running PaddleOCR primary via Temporary File Path.")
        temp_img_path = None
        paddle_success = False
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_img_path = tmp.name
                processed_img.save(temp_img_path)
            
            def run_paddle():
                with _paddle_semaphore:
                    try:
                        engine = get_ocr_instance()
                        if engine:
                            return engine.ocr(temp_img_path)
                    except Exception as paddle_err:
                        if "ConvertPirAttribute" in str(paddle_err) or "Unimplemented" in str(paddle_err):
                            logger.warning(f"Page {page_num}: PIR error in sequential → Tesseract")
                            return None
                        else:
                            raise
                return None

            try:
                result = run_paddle()
                if result:
                    lines = extract_text_lines_from_paddle_result(result)
                    conf = calculate_paddle_confidence(result)
                    ocr_boxes = extract_ocr_boxes_from_paddle_result(result)
                    if conf == 0.00 and len(lines) >= 15:
                        conf = 0.85
                    
                    # Check confidence threshold and text sparsity
                    non_whitespace_len = sum(len(l.strip()) for l in lines)
                    is_sparse = non_whitespace_len < 15
                    
                    if len(lines) > 0 and conf >= 0.50 and not is_sparse:
                        engine_used = "PaddleOCR"
                        paddle_success = True
                    else:
                        logger.info(f"Page {page_num}: PaddleOCR confidence {conf:.2f} below 0.50 or sparse (non-whitespace length={non_whitespace_len}). Escalating.")
            except Exception as e:
                logger.error(f"PaddleOCR primary failed on page {page_num}: {str(e)}")
        finally:
            if temp_img_path and os.path.exists(temp_img_path):
                try:
                    os.unlink(temp_img_path)
                except Exception as e:
                    logger.warning(f"Failed to delete PaddleOCR temporary image file {temp_img_path}: {e}")

        # 7. Fallback to Tesseract if Paddle failed or low confidence/sparse text
        if not paddle_success:
            logger.info(f"Page {page_num}: Escalating to Tesseract fallback.")
            try:
                lines, conf, ocr_boxes = run_tesseract_fallback(processed_img, extract_boxes=False)
                engine_used = "Tesseract"
            except Exception as tess_err:
                logger.error(f"Tesseract fallback failed on page {page_num}: {str(tess_err)}")
        
        if 'result' in locals():
            del result

    ocr_time = time.time() - ocr_start

    # 8. Page quality check and inline retry at higher DPI
    q_score = score_ocr_page_quality(lines)
    is_poor = (len(lines) == 0 or q_score < 0.15 or conf < 0.30)
    
    if is_poor and classification != "blank" and dpi == OCR_RENDER_DPI and OCR_RETRY_DPI > OCR_RENDER_DPI:
        logger.info(f"Page {page_num}: Poor OCR quality (lines={len(lines)}, conf={conf:.2f}, quality={q_score:.2f}) at default {OCR_RENDER_DPI} DPI. Retrying inline at {OCR_RETRY_DPI} DPI...")
        del pil_img, processed_img
        gc.collect()
        return perform_ocr_page_stable(
            ocr_engine, page_doc, page_idx, total_pages, pdf_path, dpi=OCR_RETRY_DPI, fitz_text_cache=fitz_text_cache
        )

    # 9. Strict page-wise memory cleanup
    del pil_img, processed_img
    gc.collect()
    
    elapsed = time.time() - start_time
    try:
        ram_mb = int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
        ram_str = f"{ram_mb}MB"
    except Exception:
        ram_str = "N/A"
        
    logger.info(f"Page {page_num}: Render = {render_time:.2f}s, OCR = {ocr_time:.2f}s, Total = {elapsed:.2f}s")
    logger.info(f"\nPage {page_num}\nEngine={engine_used}\nTime={elapsed:.1f}s\nConfidence={conf:.2f}\nRAM={ram_str}\n")
    
    page_meta = {
        "page": page_num,
        "engine": engine_used,
        "dpi": dpi,
        "confidence": round(conf, 3),
        "text_length": sum(len(l) for l in lines),
        "quality_score": q_score,
        "preprocessing_applied": ["grayscale", "adaptive_contrast_enhancement", "mild_denoising"],
        "lines": len(lines),
        "ocr_boxes": ocr_boxes,
        "render_time": render_time,
        "ocr_time": ocr_time,
        "total_page_time": elapsed
    }
    
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
# SEARCHABLE OCR PDF GENERATOR
# ======================================================

def generate_searchable_pdf(file_path: str, page_details: list, original_filename: str = None) -> str:
    """
    Generates a searchable PDF by overlaying invisible OCR text (render_mode=3) 
    on top of the original pages and saves it to frontend/uploads/original_filename_ocr.pdf.
    Processes page-by-page to prevent RAM spikes and handles all cleanup properly.
    """
    try:
        import fitz
        
        # Get filename and prepare output path
        filename = original_filename or os.path.basename(file_path)
        base_name, _ = os.path.splitext(filename)
        output_filename = f"{base_name}_ocr.pdf"
        
        # Safe directory paths
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads_dir = os.path.join(root_dir, "frontend", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        output_path = os.path.join(uploads_dir, output_filename)
        
        logger.info(f"Generating searchable PDF at: {output_path}...")
        
        # Map page details by page number (1-based)
        page_meta_map = {item["page"]: item for item in page_details}
        
        with fitz.open(file_path) as doc:
            for page_num in range(1, len(doc) + 1):
                page = doc[page_num - 1]
                meta = page_meta_map.get(page_num)
                if not meta:
                    continue
                
                # If page is native selectable or has no OCR boxes, skip overlaying
                engine = meta.get("engine", "")
                if engine == "PyMuPDF" or engine == "Skipped-blank" or engine == "Error":
                    continue
                
                ocr_boxes = meta.get("ocr_boxes", [])
                if not ocr_boxes:
                    continue
                
                dpi = meta.get("dpi", 180)
                scale = dpi / 72.0
                
                # Overlay each box on the page
                for entry in ocr_boxes:
                    text = entry["text"]
                    # box coordinates in pixels at render DPI
                    box = entry["box"]
                    if not box or len(box) < 4:
                        continue
                    
                    # Convert pixel coordinates to PDF point coordinates (x / scale, y / scale)
                    x = box[0][0] / scale
                    y = box[0][1] / scale
                    
                    # Estimate font size based on box height in PDF points
                    box_height = (box[3][1] - box[0][1]) / scale
                    font_size = max(4.0, min(box_height * 0.8, 48.0))
                    
                    # Insert the text invisibly
                    try:
                        page.insert_text(
                            fitz.Point(x, y),
                            text,
                            fontsize=font_size,
                            render_mode=3
                        )
                    except Exception:
                        try:
                            page.insert_text(
                                (x, y),
                                text,
                                fontsize=font_size,
                                render_mode=3
                            )
                        except Exception:
                            pass
                            
            doc.save(output_path, garbage=3, deflate=True)
            
        logger.info(f"Searchable PDF generated successfully: {output_path}")
        return f"/uploads/{output_filename}"
        
    except Exception as e:
        logger.error(f"Failed to generate searchable PDF: {str(e)}")
        return ""


# ======================================================
# SCANNED PDF OCR PIPELINE
# ======================================================

def perform_ocr_on_scanned_pdf(file_path: str, progress_callback=None, scan_all_pages: bool = False, original_filename: str = None) -> tuple:
    start_time = time.time()
    ocr_engine = get_ocr_instance()

    if ocr_engine is None:
        logger.warning("PaddleOCR offline. Returning empty result.")
        return [], _build_ocr_debug(
            engine_used="unavailable", retry_count=0, quality_score=0.0,
            failed_pages=[], successful_pages=[], preprocessing_applied=[],
            fallback_ocr_engine="none", text_density_score=0.0,
            total_ocr_time=time.time() - start_time
        )

    try:
        # Pre-cache fitz text
        fitz_text_cache = []
        try:
            import fitz
            with fitz.open(file_path) as fitz_doc:
                fitz_text_cache = [page.get_text() for page in fitz_doc]
        except Exception as e:
            logger.warning(f"Failed to pre-extract digital text with PyMuPDF: {e}")

        # Get total pages
        with pdfium.PdfDocument(file_path) as temp_doc:
            total_pages = len(temp_doc)
        gc.collect()

        # Validate fitz cache length
        if len(fitz_text_cache) != total_pages:
            logger.warning(f"fitz_text_cache length {len(fitz_text_cache)} != total_pages {total_pages}. Re-extracting...")
            try:
                import fitz
                with fitz.open(file_path) as fitz_doc:
                    fitz_text_cache = [page.get_text() for page in fitz_doc]
            except Exception as e:
                logger.warning(f"fitz re-extraction failed: {e}")

        logger.info(f"Scanned PDF '{file_path}' ({total_pages} pages): pre-rendering pages sequentially to temp images...")

        # ============================================================
        # CRITICAL FIX: Pre-render ALL pages to temp PNG files
        # sequentially using a SINGLE open pdfium doc.
        # This prevents concurrent pdfium doc opens that cause
        # "Data format error" on large PDFs (>80 pages).
        # ============================================================
        render_dir = tempfile.mkdtemp(prefix="ocr_render_")
        rendered_image_paths = {}  # page_idx -> temp png path

        try:
            scale = OCR_RENDER_DPI / 72.0
            with pdfium.PdfDocument(file_path) as pdf_doc:
                for page_idx in range(total_pages):
                    # Skip pages where fitz already has good text
                    if fitz_text_cache and page_idx < len(fitz_text_cache):
                        page_text = fitz_text_cache[page_idx]
                        keywords = ["court", "claimant", "petitioner", "respondent", "accident",
                                   "compensation", "tribunal", "judgment", "deceased", "injured"]
                        hits = sum(1 for kw in keywords if kw in page_text.lower())
                        if len(page_text.strip()) > 200 and hits >= 2:
                            rendered_image_paths[page_idx] = None  # Signal: use fitz text directly
                            continue

                    try:
                        page = pdf_doc[page_idx]
                        bitmap = page.render(scale=scale)
                        pil_img = bitmap.to_pil()
                        del bitmap, page

                        # Apply memory guard
                        pil_img = guard_and_downscale_image(pil_img)

                        # Save to temp file
                        img_path = os.path.join(render_dir, f"page_{page_idx:04d}.png")
                        pil_img.save(img_path, format="PNG")
                        rendered_image_paths[page_idx] = img_path
                        del pil_img
                        gc.collect()

                    except Exception as e:
                        logger.error(f"Failed to pre-render page {page_idx+1}: {e}")
                        rendered_image_paths[page_idx] = "error"

        except Exception as e:
            logger.error(f"Critical failure during sequential pre-rendering: {e}")

        logger.info(f"Pre-rendering complete. {len(rendered_image_paths)} pages mapped. Starting parallel OCR...")

        # ============================================================
        # NOW run OCR in parallel — reading from pre-rendered PNGs
        # No more concurrent pdfium opens
        # ============================================================
        page_results = {}
        total_ocr_duration = 0.0

        import concurrent.futures

        def process_pre_rendered_page(idx):
            try:
                page_num = idx + 1
                start = time.time()

                img_path = rendered_image_paths.get(idx)

                # Case 1: fitz text is good — return it directly
                if img_path is None:
                    page_text = fitz_text_cache[idx]
                    lines = [l.strip() for l in page_text.split("\n") if l.strip()]
                    elapsed = time.time() - start
                    meta = {
                        "page": page_num, "engine": "PyMuPDF", "dpi": 72,
                        "confidence": 1.0, "text_length": len(page_text),
                        "quality_score": 1.0, "preprocessing_applied": [],
                        "lines": len(lines), "ocr_boxes": [],
                        "render_time": 0.0, "ocr_time": elapsed,
                        "total_page_time": elapsed
                    }
                    return idx, lines, meta

                # Case 2: render failed
                if img_path == "error":
                    meta = {
                        "page": page_num, "engine": "Error", "dpi": OCR_RENDER_DPI,
                        "confidence": 0.0, "text_length": 0, "quality_score": 0.0,
                        "preprocessing_applied": [], "lines": 0, "ocr_boxes": [],
                        "render_time": 0.0, "ocr_time": 0.0, "total_page_time": 0.0
                    }
                    return idx, [], meta

                # Case 3: OCR the pre-rendered image
                ocr_start = time.time()
                pil_img = Image.open(img_path).convert("RGB")

                # Visual classifier
                classification = classify_scanned_page(pil_img)

                if classification == "blank":
                    del pil_img
                    gc.collect()
                    elapsed = time.time() - start
                    meta = {
                        "page": page_num, "engine": "Skipped-blank", "dpi": OCR_RENDER_DPI,
                        "confidence": 1.0, "text_length": 0, "quality_score": 0.0,
                        "preprocessing_applied": [], "lines": 0, "ocr_boxes": [],
                        "render_time": 0.0, "ocr_time": 0.0, "total_page_time": elapsed
                    }
                    return idx, [], meta

                # Lightweight preprocessing
                processed_img = preprocess_image_light(pil_img, binarize=False)
                del pil_img
                gc.collect()

                lines = []
                conf = 0.0
                ocr_boxes = []
                engine_used = ""

                if classification == "low-content":
                    lines, conf, ocr_boxes = run_tesseract_fallback(processed_img, extract_boxes=False)
                    engine_used = "Tesseract"
                else:
                    # PaddleOCR via temp file — serialized
                    temp_img_path = None
                    paddle_success = False
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                            temp_img_path = tmp.name
                            processed_img.save(temp_img_path)

                        with _paddle_semaphore:   # ← serialize paddle calls, threads queue here
                            try:
                                instance = get_ocr_instance()
                                result = instance.ocr(temp_img_path) if instance else None
                            except Exception as paddle_err:
                                if "ConvertPirAttribute" in str(paddle_err) or "Unimplemented" in str(paddle_err):
                                    logger.warning(f"Page {page_num}: PIR error → Tesseract")
                                    result = None
                                else:
                                    raise

                        if result:
                            lines = extract_text_lines_from_paddle_result(result)
                            conf = calculate_paddle_confidence(result)
                            ocr_boxes = extract_ocr_boxes_from_paddle_result(result)
                            if conf == 0.0 and len(lines) >= 15:
                                conf = 0.85
                            non_ws = sum(len(l.strip()) for l in lines)
                            if len(lines) > 0 and conf >= 0.50 and non_ws >= 15:
                                engine_used = "PaddleOCR"
                                paddle_success = True
                    finally:
                        if temp_img_path and os.path.exists(temp_img_path):
                            try:
                                os.unlink(temp_img_path)
                            except Exception:
                                pass

                    if not paddle_success:
                        lines, conf, ocr_boxes = run_tesseract_fallback(processed_img, extract_boxes=False)
                        engine_used = "Tesseract"

                del processed_img
                gc.collect()

                ocr_time = time.time() - ocr_start
                q_score = score_ocr_page_quality(lines)
                is_poor = (len(lines) == 0 or q_score < 0.15 or conf < 0.30)

                # Inline retry at higher DPI if poor quality
                if is_poor and classification != "blank" and OCR_RETRY_DPI > OCR_RENDER_DPI:
                    logger.info(f"Page {page_num}: Poor quality, retrying at {OCR_RETRY_DPI} DPI...")
                    try:
                        retry_img_path = os.path.join(render_dir, f"page_{idx:04d}_retry.png")
                        if not os.path.exists(retry_img_path):
                            # Re-render at higher DPI using fitz (safe, single page)
                            import fitz
                            with fitz.open(file_path) as retry_doc:
                                retry_page = retry_doc[idx]
                                retry_mat = fitz.Matrix(OCR_RETRY_DPI / 72.0, OCR_RETRY_DPI / 72.0)
                                retry_pix = retry_page.get_pixmap(matrix=retry_mat, alpha=False)
                                retry_img = Image.frombytes("RGB", [retry_pix.width, retry_pix.height], retry_pix.samples)
                                retry_img = guard_and_downscale_image(retry_img)
                                retry_img.save(retry_img_path)
                                del retry_pix, retry_page, retry_img

                        retry_pil = Image.open(retry_img_path).convert("RGB")
                        retry_processed = preprocess_image_light(retry_pil, binarize=False)
                        del retry_pil

                        retry_temp = None
                        try:
                            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                                retry_temp = tmp.name
                                retry_processed.save(retry_temp)
                            with _paddle_semaphore:
                                try:
                                    instance = get_ocr_instance()
                                    retry_result = instance.ocr(retry_temp) if instance else None
                                except Exception as paddle_err:
                                    if "ConvertPirAttribute" in str(paddle_err) or "Unimplemented" in str(paddle_err):
                                        logger.warning(f"Page {page_num}: PIR error in retry")
                                        retry_result = None
                                    else:
                                        raise
                            if retry_result:
                                retry_lines = extract_text_lines_from_paddle_result(retry_result)
                                retry_conf = calculate_paddle_confidence(retry_result)
                                if len(retry_lines) > len(lines) or retry_conf > conf:
                                    lines = retry_lines
                                    conf = retry_conf
                                    ocr_boxes = extract_ocr_boxes_from_paddle_result(retry_result)
                                    engine_used = "PaddleOCR-Retry"
                                    q_score = score_ocr_page_quality(lines)
                        finally:
                            if retry_temp and os.path.exists(retry_temp):
                                os.unlink(retry_temp)
                            del retry_processed
                            gc.collect()
                    except Exception as retry_err:
                        logger.warning(f"Retry at higher DPI failed for page {page_num}: {retry_err}")

                elapsed = time.time() - start
                try:
                    ram_mb = int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
                    ram_str = f"{ram_mb}MB"
                except Exception:
                    ram_str = "N/A"
                logger.info(f"Page {page_num}: Engine={engine_used}, OCR={ocr_time:.2f}s, Total={elapsed:.2f}s, RAM={ram_str}")

                meta = {
                    "page": page_num, "engine": engine_used, "dpi": OCR_RENDER_DPI,
                    "confidence": round(conf, 3), "text_length": sum(len(l) for l in lines),
                    "quality_score": q_score,
                    "preprocessing_applied": ["grayscale", "adaptive_contrast_enhancement", "mild_denoising"],
                    "lines": len(lines), "ocr_boxes": ocr_boxes,
                    "render_time": 0.0, "ocr_time": ocr_time, "total_page_time": elapsed
                }
                return idx, lines, meta

            except Exception as ex:
                logger.error(f"Error during parallel OCR on page {idx+1}: {ex}")
                meta = {
                    "page": idx+1, "engine": "Error", "dpi": OCR_RENDER_DPI,
                    "confidence": 0.0, "text_length": 0, "quality_score": 0.0,
                    "preprocessing_applied": [], "lines": 0, "ocr_boxes": [],
                    "render_time": 0.0, "ocr_time": 0.0, "total_page_time": 0.0
                }
                return idx, [], meta

        with concurrent.futures.ThreadPoolExecutor(max_workers=OCR_MAX_PARALLEL_WORKERS) as executor:
            futures = [executor.submit(process_pre_rendered_page, idx) for idx in range(total_pages)]
            for future in concurrent.futures.as_completed(futures):
                idx, page_lines, page_meta = future.result()
                page_results[idx] = (page_lines, page_meta)
                if "ocr_time" in page_meta:
                    total_ocr_duration += page_meta["ocr_time"]
                if progress_callback:
                    progress_callback(int((len(page_results) / total_pages) * 95))

        # Cleanup pre-rendered images
        try:
            shutil.rmtree(render_dir)
            logger.info(f"Cleaned up pre-render temp dir: {render_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up render dir {render_dir}: {e}")

        # --- COMPILE RESULTS (unchanged from original) ---
        avg_ocr_time = total_ocr_duration / total_pages if total_pages else 0.0
        logger.info(f"PDF Total: OCR = {total_ocr_duration:.2f}s, Average OCR Per Page = {avg_ocr_time:.2f}s")

        text_lines = []
        failed_pages = []
        successful_pages = []
        all_preprocessing_steps = []
        page_qualities = []
        page_confidences = []
        fallback_engine_used = ""
        page_details = []
        total_retry_count = 0

        for idx in range(total_pages):
            page_num = idx + 1
            page_lines, page_meta = page_results[idx]
            q = page_meta.get("quality_score", 0.0)
            conf = page_meta.get("confidence", 0.0)
            engine = page_meta.get("engine", "PaddleOCR")

            if page_meta.get("dpi") == OCR_RETRY_DPI:
                total_retry_count += 1

            page_qualities.append(q)
            page_confidences.append(conf)
            page_details.append(page_meta)

            if engine == "Tesseract":
                fallback_engine_used = "Tesseract"

            for step in page_meta.get("preprocessing_applied", []):
                if step not in all_preprocessing_steps:
                    all_preprocessing_steps.append(step)

            if page_lines:
                successful_pages.append(page_num)
            else:
                failed_pages.append(page_num)

            text_lines.append(f"--- PAGE {page_num} ---")
            text_lines.extend(page_lines)

        overall_quality = round(sum(page_qualities) / len(page_qualities), 4) if page_qualities else 0.0
        overall_conf = round(sum(page_confidences) / len(page_confidences), 4) if page_confidences else 0.0
        real_lines = [l for l in text_lines if not l.startswith("--- PAGE")]
        text_density = round(
            sum(len(l) for l in real_lines) / max(len(real_lines), 1) / 80.0, 3
        ) if real_lines else 0.0

        elapsed_time = time.time() - start_time
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
            pages=page_details,
            total_ocr_time=elapsed_time
        )

        # Background searchable PDF generation (unchanged)
        filename = original_filename or os.path.basename(file_path)
        base_name, _ = os.path.splitext(filename)
        output_filename = f"{base_name}_ocr.pdf"
        searchable_pdf_url = f"/uploads/{output_filename}"
        ocr_debug["searchable_pdf_url"] = searchable_pdf_url

        bg_temp_dir = tempfile.mkdtemp()
        bg_temp_path = os.path.join(bg_temp_dir, os.path.basename(file_path))
        try:
            shutil.copy(file_path, bg_temp_path)

            def bg_pdf_worker(src_path, pg_details, orig_name, temp_dir):
                try:
                    logger.info(f"Background thread starting searchable PDF generation for {orig_name}...")
                    generate_searchable_pdf(src_path, pg_details, original_filename=orig_name)
                except Exception as ex:
                    logger.error(f"Background searchable PDF generation failed: {ex}")
                finally:
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception:
                        pass

            threading.Thread(
                target=bg_pdf_worker,
                args=(bg_temp_path, page_details, filename, bg_temp_dir),
                daemon=True
            ).start()

        except Exception as e:
            logger.error(f"Failed to setup background searchable PDF copy task: {e}")
            try:
                shutil.rmtree(bg_temp_dir)
            except Exception:
                pass

        return text_lines, ocr_debug

    except Exception as e:
        logger.error(f"Critical error during scanned PDF OCR: {str(e)}")
        elapsed_time = time.time() - start_time if 'start_time' in locals() else 0.0
        return [], _build_ocr_debug(
            engine_used="PaddleOCR", retry_count=0, quality_score=0.0,
            failed_pages=[], successful_pages=[], preprocessing_applied=[],
            fallback_ocr_engine="none", text_density_score=0.0,
            total_ocr_time=elapsed_time
        )


def perform_ocr_on_image(file_path: str) -> tuple:
    """Runs the stable single-page OCR pipeline directly on uploaded image (PNG, JPG, BMP)."""
    start_time = time.time()
    ocr_engine = get_ocr_instance()

    if ocr_engine is None:
        logger.warning("PaddleOCR offline. Returning empty result.")
        return [], _build_ocr_debug(
            engine_used="unavailable", retry_count=0, quality_score=0.0,
            failed_pages=[1], successful_pages=[], preprocessing_applied=[],
            fallback_ocr_engine="none", text_density_score=0.0,
            total_ocr_time=time.time() - start_time
        )

    try:
        original_pil = Image.open(file_path)
        logger.info(f"Image upload '{file_path}': starting OCR pipeline...")
        
        # Max Page Memory Guard (Downscale Guard)
        original_pil = guard_and_downscale_image(original_pil)
        
        # Lightweight Preprocessing
        processed_img = preprocess_image_light(original_pil, binarize=False)
        
        save_ocr_debug_image("debug_original_1.png", original_pil)
        save_ocr_debug_image("debug_processed_1.png", processed_img)
        
        lines = []
        conf = 0.0
        ocr_boxes = []
        engine_used = "PaddleOCR"
        
        temp_img_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_img_path = tmp.name
                processed_img.save(temp_img_path)
            
            def run_paddle():
                with _paddle_semaphore:
                    try:
                        engine = get_ocr_instance()
                        if engine:
                            return engine.ocr(temp_img_path)
                    except Exception as paddle_err:
                        if "ConvertPirAttribute" in str(paddle_err) or "Unimplemented" in str(paddle_err):
                            logger.warning("Image OCR: PIR error → Tesseract")
                            return None
                        else:
                            raise
                return None
                
            try:
                result = run_paddle()
                if result:
                    lines = extract_text_lines_from_paddle_result(result)
                    conf = calculate_paddle_confidence(result)
                    ocr_boxes = extract_ocr_boxes_from_paddle_result(result)
                    if conf == 0.00 and len(lines) >= 15:
                        conf = 0.85
            except Exception as e:
                logger.error(f"Image PaddleOCR failed: {str(e)}")
        finally:
            if temp_img_path and os.path.exists(temp_img_path):
                try:
                    os.unlink(temp_img_path)
                except Exception as e:
                    logger.warning(f"Failed to delete PaddleOCR temporary image file {temp_img_path}: {e}")

        # Last-resort Tesseract Fallback
        if (len(lines) == 0 or conf < 0.15) and is_tesseract_available():
            logger.info("Image PaddleOCR returned empty or low confidence. Running last-resort Tesseract fallback.")
            try:
                lines, conf, ocr_boxes = run_tesseract_fallback(processed_img)
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
            "preprocessing_applied": ["grayscale", "adaptive_contrast_enhancement", "mild_denoising"],
            "lines": len(lines),
            "ocr_boxes": ocr_boxes
        }]

        elapsed_time = time.time() - start_time
        ocr_debug = _build_ocr_debug(
            engine_used="PaddleOCR",
            retry_count=1 if engine_used == "Tesseract" else 0,
            quality_score=score_ocr_page_quality(lines),
            failed_pages=failed_pages,
            successful_pages=successful_pages,
            preprocessing_applied=["grayscale", "adaptive_contrast_enhancement", "mild_denoising"],
            fallback_ocr_engine=engine_used if engine_used != "PaddleOCR" else "",
            text_density_score=min(len(lines) / 30.0, 1.0),
            average_page_confidence=conf,
            raw_ocr_preview="\n".join(lines)[:3000],
            pages=page_details,
            total_ocr_time=elapsed_time
        )

        return lines, ocr_debug

    except Exception as e:
        logger.error(f"Error running OCR on image: {str(e)}")
        elapsed_time = time.time() - start_time if 'start_time' in locals() else 0.0
        return [], _build_ocr_debug(
            "PaddleOCR", 0, 0.0, [1], [], [], "none", 0.0,
            total_ocr_time=elapsed_time
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
    start_time = time.time()
    try:
        BATCH_QUEUE[file_id]["status"] = "scanning"
        BATCH_QUEUE[file_id]["progress"] = 20

        # 1. Selectable text extraction
        text_lines = extract_digital_pdf_text(temp_path)
        fallback_source = "DigitalPDF"
        ocr_debug = _build_ocr_debug("DigitalPDF", 0, 1.0, [], [], [], "", 0.0, total_ocr_time=time.time() - start_time)

        # 2. Scanned OCR Escalation (scan_all_pages=True for comprehensive index)
        if is_extracted_text_sparse(text_lines):
            logger.info(f"Selectable text sparse. Running sequential stable OCR for {filename}")

            def report_progress(prog_percent):
                BATCH_QUEUE[file_id]["progress"] = prog_percent

            text_lines, ocr_debug = perform_ocr_on_scanned_pdf(
                temp_path, progress_callback=report_progress, scan_all_pages=True, original_filename=filename
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
                ocr_debug["total_ocr_time"] = round(time.time() - start_time, 2)

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
    """Synchronous single file handler implementing identical frontend contracts, refactored to stream SSE updates."""
    file_ext = os.path.splitext(file.filename)[1].lower()
    allowed_images = {".png", ".jpg", ".jpeg", ".bmp"}
    allowed_docs = {".pdf"}

    if file_ext not in allowed_images and file_ext not in allowed_docs:
        raise HTTPException(
            status_code=400,
            detail="Only PNG, JPG, BMP and PDF formats are supported."
        )

    async def event_generator():
        temp_path = None
        try:
            # Phase 1: Saving upload
            yield f"data: {json.dumps({'status': 'saving', 'progress': 5, 'message': 'Saving upload to temp file...'})}\n\n"
            await asyncio.sleep(0.01)

            def save_to_temp():
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                    shutil.copyfileobj(file.file, tmp)
                    return tmp.name
            
            temp_path = await asyncio.to_thread(save_to_temp)

            start_time = time.time()
            fallback_source = "DigitalPDF"
            ocr_debug = _build_ocr_debug("DigitalPDF", 0, 1.0, [], [], [], "", 0.0, total_ocr_time=0.0)

            if file_ext == ".pdf":
                # Phase 2: Extracting digital PDF text
                yield f"data: {json.dumps({'status': 'extracting', 'progress': 15, 'message': 'Extracting digital PDF text...'})}\n\n"
                await asyncio.sleep(0.01)
                
                text_lines = await asyncio.to_thread(extract_digital_pdf_text, temp_path)

                # Phase 3: Checking text quality
                yield f"data: {json.dumps({'status': 'checking', 'progress': 35, 'message': 'Checking text quality...'})}\n\n"
                await asyncio.sleep(0.01)

                if is_extracted_text_sparse(text_lines):
                    # Escalating to Scanned PDF OCR
                    yield f"data: {json.dumps({'status': 'ocr', 'progress': 50, 'message': 'Scanned PDF detected — running PaddleOCR...'})}\n\n"
                    await asyncio.sleep(0.01)
                    
                    text_lines, ocr_debug = await asyncio.to_thread(
                        perform_ocr_on_scanned_pdf, temp_path, original_filename=file.filename
                    )
                    fallback_source = "PaddleOCR"

                if is_extracted_text_sparse(text_lines):
                    # Escalating to Alternate layouts
                    yield f"data: {json.dumps({'status': 'checking_alternate', 'progress': 65, 'message': 'Sparse text — running PyMuPDF/pdfplumber fallback...'})}\n\n"
                    await asyncio.sleep(0.01)
                    
                    alt_lines = await asyncio.to_thread(extract_alternate_pdf_text, temp_path)
                    if len(alt_lines) > len(text_lines):
                        text_lines = alt_lines
                        fallback_source = "AlternateOCR"
                        ocr_debug["fallback_ocr_engine"] = "PyMuPDF/pdfplumber"
                        ocr_debug["ocr_quality_score"] = 1.0
                        ocr_debug["total_ocr_time"] = round(time.time() - start_time, 2)
            else:
                # Running Image OCR
                yield f"data: {json.dumps({'status': 'ocr', 'progress': 40, 'message': 'Running PaddleOCR on image...'})}\n\n"
                await asyncio.sleep(0.01)
                
                text_lines, ocr_debug = await asyncio.to_thread(perform_ocr_on_image, temp_path)
                fallback_source = "PaddleOCR"

            # Phase 4: Parsing legal fields
            yield f"data: {json.dumps({'status': 'parsing', 'progress': 75, 'message': 'Parsing legal fields...'})}\n\n"
            await asyncio.sleep(0.01)

            suggestions = await asyncio.to_thread(parse_extracted_text, text_lines)
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

            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
                temp_path = None

            # Yield done message
            done_payload = {
                "status": "done",
                "progress": 100,
                "success": True,
                "filename": file.filename,
                "ocr_status": "loaded",
                "fallback_source": fallback_source,
                "suggestions": formatted_suggestions,
                "raw_text": text_lines,
                "ocr_debug": ocr_debug
            }
            yield f"data: {json.dumps(done_payload)}\n\n"

        except Exception as e:
            logger.error(f"Streaming OCR error: {str(e)}")
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            yield f"data: {json.dumps({'status': 'failed', 'progress': 100, 'success': False, 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


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
    """Returns batch processing queue status updates with heavy payloads sanitized."""
    sanitized_queue = []
    for file_id, item in BATCH_QUEUE.items():
        sanitized_item = {
            "file_id": item.get("file_id"),
            "filename": item.get("filename"),
            "status": item.get("status"),
            "progress": item.get("progress"),
            "error": item.get("error"),
            "suggestions": item.get("suggestions"),
            "raw_text": item.get("raw_text", []),
        }
        ocr_debug = item.get("ocr_debug")
        if ocr_debug:
            sanitized_pages = []
            for p in ocr_debug.get("pages", []):
                sanitized_pages.append({
                    "page": p.get("page"),
                    "engine": p.get("engine"),
                    "dpi": p.get("dpi"),
                    "total_page_time": p.get("total_page_time"),
                    "confidence": p.get("confidence"),
                    "quality_score": p.get("quality_score"),
                })
            sanitized_ocr_debug = {
                "ocr_engine_used": ocr_debug.get("ocr_engine_used"),
                "ocr_retry_count": ocr_debug.get("ocr_retry_count"),
                "ocr_quality_score": ocr_debug.get("ocr_quality_score"),
                "fallback_ocr_engine": ocr_debug.get("fallback_ocr_engine"),
                "preprocessing_applied": ocr_debug.get("preprocessing_applied"),
                "text_density_score": ocr_debug.get("text_density_score"),
                "average_page_confidence": ocr_debug.get("average_page_confidence"),
                "searchable_pdf_url": ocr_debug.get("searchable_pdf_url"),
                "total_ocr_time": ocr_debug.get("total_ocr_time"),
                "pages": sanitized_pages
            }
            sanitized_item["ocr_debug"] = sanitized_ocr_debug
        sanitized_queue.append(sanitized_item)
        
    return {
        "success": True,
        "queue": sanitized_queue,
    }


@router.post("/clear-queue")
async def clear_queue():
    """Clears completed or failed items from the batch processing queue to free RAM."""
    global BATCH_QUEUE
    to_remove = [file_id for file_id, item in BATCH_QUEUE.items() if item["status"] in ("indexed", "failed")]
    for file_id in to_remove:
        del BATCH_QUEUE[file_id]
    gc.collect()
    return {
        "success": True,
        "message": f"Successfully cleared {len(to_remove)} completed/failed entries from BATCH_QUEUE.",
        "active_items": len(BATCH_QUEUE)
    }


from pydantic import BaseModel

class AIRecoverRequest(BaseModel):
    raw_text: list[str]

@router.post("/ai-recover")
async def ai_recover_fields(request: AIRecoverRequest):
    """
    Receives raw OCR'd text lines and executes the LLM parser to extract 
    accurate structured legal entities.
    """
    try:
        from backend.llm_client import ai_data_recovery
        full_text = "\n".join(request.raw_text)
        
        # Invoke LLM parsing
        recovered_data = ai_data_recovery(full_text)
        
        # Re-format output compatibility with calculator formatting
        from backend.parser_heuristics import format_suggestions_for_calculator
        formatted = format_suggestions_for_calculator(recovered_data)
        
        return {
            "success": True,
            "suggestions": formatted,
            "raw_recovered": recovered_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SuggestCaseTypeRequest(BaseModel):
    raw_text: str
    selected_case_type: str

@router.post("/suggest-case-type")
async def suggest_case_type(request: SuggestCaseTypeRequest):
    """
    Suggests workers' compensation case type probabilities based on raw document text.
    Uses the project's configured LLM provider and parses the JSON response.
    """
    raw_text = request.raw_text[:8000]  # Allow up to 8k characters for good context
    selected = request.selected_case_type

    CASE_TYPES = [
        "Death", 
        "Permanent Total Disability", 
        "Permanent Partial Disability",
        "Temporary Total Disability", 
        "Medical Only", 
        "Vocational Rehabilitation"
    ]

    system_prompt = (
        "You are a legal document analyst for workers' compensation claims.\n"
        "Given extracted text from a claim document, return ONLY a JSON array (no markdown, no explanation, no backticks) of case type probabilities.\n"
        "Format: [{\"case_type\": \"Death\", \"confidence\": 0.82}, ...]\n"
        "All confidences must sum to 1.0. Include all possible case types even if confidence is near 0."
    )

    user_prompt = (
        f"Document text:\n{raw_text}\n\n"
        f"The user selected: \"{selected}\"\n"
        f"Analyze the document and return confidence scores for each case type:\n"
        f"{', '.join(CASE_TYPES)}"
    )

    try:
        from backend.llm_client import generate_response
        response_text = await asyncio.to_thread(generate_response, user_prompt, system_prompt)
        
        # Extract JSON array block using regex
        json_match = re.search(r"\[\s*\{.*\}\s*\]", response_text, re.DOTALL)
        if json_match:
            suggestions = json.loads(json_match.group(0))
        else:
            suggestions = json.loads(response_text)
            
        # Guarantee all CASE_TYPES are included
        existing_types = {s.get("case_type") for s in suggestions if isinstance(s, dict)}
        for ct in CASE_TYPES:
            if ct not in existing_types:
                suggestions.append({"case_type": ct, "confidence": 0.0})
                
        suggestions.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
        return {"suggestions": suggestions, "selected": selected}
        
    except Exception as e:
        logger.error(f"Failed to parse case type suggestions JSON: {str(e)}. Raw response: {response_text if 'response_text' in locals() else 'None'}")
        fallback_suggestions = [{"case_type": ct, "confidence": 1.0 / len(CASE_TYPES)} for ct in CASE_TYPES]
        # Soft-boost selected category or Death
        for fs in fallback_suggestions:
            if fs["case_type"].lower() == selected.lower():
                fs["confidence"] = 0.5
            else:
                fs["confidence"] = 0.5 / (len(CASE_TYPES) - 1)
        fallback_suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        return {"suggestions": fallback_suggestions, "selected": selected, "error": str(e)}
