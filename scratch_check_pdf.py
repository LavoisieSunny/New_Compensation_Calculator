import os
import sys
import pypdfium2 as pdfium

# Add backend folder to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.ocr import perform_ocr_page_with_retry, get_ocr_instance
from backend.parser_heuristics import parse_extracted_text
from backend.vector_db import chunk_text

pdf_path = r"C:\Users\lavoi\Desktop\Miracle\pdfs\compensation\MA_9824_2025.pdf"

print("Initializing PaddleOCR...")
ocr_engine = get_ocr_instance()
print("OCR Engine loaded:", ocr_engine is not None)

if ocr_engine:
    print("\nOpening PDF Document...")
    doc = pdfium.PdfDocument(pdf_path)
    total_pages = len(doc)
    print(f"Total Pages in PDF: {total_pages}")
    
    # We will scan page 0 (Page 1) and the last page (Page 42)
    pages_to_scan = [0, total_pages - 1]
    text_lines = []
    
    for page_idx in pages_to_scan:
        print(f"\n--- Running OCR on Page {page_idx + 1}... ---")
        page_lines, page_meta = perform_ocr_page_with_retry(
            ocr_engine, doc[page_idx], page_idx, total_pages, pdf_path=pdf_path
        )
        print(f"Page {page_idx + 1} completed: {len(page_lines)} lines, quality score: {page_meta['quality_score']}, confidence: {page_meta['confidence']}")
        text_lines.append(f"--- PAGE {page_idx + 1} ---")
        text_lines.extend(page_lines)
        
    # Write raw text to a scratch file
    with open("extracted_raw_text.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(text_lines))
    print("\nSaved extracted text to extracted_raw_text.txt")
    
    # 1. Parse Suggestions JSON
    print("\n--- RUNNING HEURISTIC SUGGESTION PARSING ---")
    sug = parse_extracted_text(text_lines)
    for k, v in sug.items():
        if k in ["name", "deceased_name", "claimant_name", "father_name", "date_of_accident", "age", "monthly_income", "total_compensation", "award_amount", "consortium", "funeral_expenses", "loss_estate", "ocr_warning"]:
            print(f"  {k}: {v}")
            
    # 2. Verify optimized Chunking
    print("\n--- RUNNING SEMANTIC CHUNKING VERIFICATION ---")
    from backend.parser_heuristics import merge_ocr_lines_to_paragraphs
    paragraphs = merge_ocr_lines_to_paragraphs(text_lines)
    full_text = "\n\n".join(paragraphs)
    chunks = chunk_text(full_text)
    print(f"Total paragraphs reconstructed: {len(paragraphs)}")
    print(f"Total chunks generated: {len(chunks)}")
    
    # Print the first chunk to inspect boundaries
    if chunks:
        print("\n--- FIRST CHUNK PREVIEW ---")
        print(chunks[0][:800] + "...")
        print("---------------------------")
