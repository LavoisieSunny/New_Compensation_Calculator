# pipeline.py
import os
import sys

# Ensure backend can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.ocr import extract_digital_pdf_text, is_extracted_text_sparse, perform_ocr_on_scanned_pdf, apply_ocr_quality_gate
from backend.parser_heuristics import parse_extracted_text

class SmartOCRPipeline:
    def __init__(self, confidence_threshold=0.75):
        self.confidence_threshold = confidence_threshold
    
    def process_pdf(self, pdf_path):
        """
        Full legal detail extraction pipeline with intelligent fallbacks and multi-language support.
        Processes selectable text, detects digital garble, runs high-DPI scanned OCR when needed,
        and applies the cause-title role-resolution heuristic.
        """
        print(f"Processing PDF: {pdf_path}")
        
        # Step 1: Extract selectable digital text
        text_lines = extract_digital_pdf_text(pdf_path)
        fallback_source = "DigitalPDF"
        ocr_debug = {
            "ocr_engine_used": "DigitalPDF",
            "ocr_quality_score": 1.0,
            "fallback_ocr_engine": "none"
        }
        
        # Step 2: Quality Gate check — Escalate to OCR if sparse or garbled digital text layer is detected
        if is_extracted_text_sparse(text_lines):
            print("Selectable text is sparse or garbled. Running stabilized multi-engine OCR fallback...")
            text_lines, ocr_debug = perform_ocr_on_scanned_pdf(pdf_path, scan_all_pages=True)
            fallback_source = ocr_debug.get("ocr_engine_used", "OCR_Engine")
            
        # Step 3: Run Legal Heuristics / Semantic Parser
        print("Parsing extracted text using legal heuristics...")
        suggestions = parse_extracted_text(text_lines)
        
        # Step 4: Apply Quality Gate
        suggestions = apply_ocr_quality_gate(suggestions, ocr_debug)
        
        # Step 5: Wrap suggestions in final output
        result = {
            "success": len(text_lines) > 0,
            "filename": os.path.basename(pdf_path),
            "fallback_source": fallback_source,
            "ocr_debug": ocr_debug,
            "suggestions": suggestions,
            "raw_text": text_lines
        }
        
        return result

if __name__ == "__main__":
    import argparse
    import pprint
    
    parser = argparse.ArgumentParser(description="Run the Smart OCR Claim Calculator Pipeline.")
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    args = parser.parse_args()
    
    pipeline = SmartOCRPipeline()
    result = pipeline.process_pdf(args.pdf_path)
    
    print("\n--- PIPELINE RESULT ---")
    pprint.pprint(result["suggestions"])
