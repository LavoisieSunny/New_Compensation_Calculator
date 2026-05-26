import os
import sys
from PIL import Image, ImageDraw

# Ensure root folder is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.parser_heuristics import parse_extracted_text

def create_mock_scan(output_path="test_scan.png"):
    """
    Creates a mock image of a legal claims document.
    Draws text lines in black on a white background.
    """
    print(f"Creating mock claim document scan at: {output_path}...")
    
    # 800x800 image, white background to fit more lines cleanly
    img = Image.new('RGB', (800, 800), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    # Write sample lines in high-contrast black
    lines = [
        "BEFORE THE MOTOR ACCIDENTS CLAIMS TRIBUNAL, CHENNAI",
        "M.C.O.P. No. 1205 of 2021",
        "Claimant Name: Shri Rajesh Kumar Sharma",
        "S/o Shri Om Prakash Sharma, Resident of Chennai, Tamil Nadu",
        "Date of Birth of Injured: 12-04-1992 (Age: 32)",
        "Date of Accident: 12-05-2022",
        "Monthly Income: Earns Rs. 25000 per month from private service",
        "Permanent Disability: 40% permanent disability in left leg",
        "Number of dependents: 3 family members",
        "Marital Status: Married",
        "The Tribunal hereby awards a total compensation of Rs. 4,57,240/- as award amount.",
        "Award Section:",
        "1. Disability Compensation : Rs. 2,00,000/-",
        "2. Pain and suffering : Rs. 40,000/-",
        "3. Loss of amenities : Rs. 30,000/-",
        "4. Transportation charges : Rs. 15,000/-",
        "5. Extra nourishment : Rs. 15,000/-",
        "6. Attender charges : Rs. 15,000/-"
    ]
    
    y = 20
    for line in lines:
        d.text((40, y), line, fill=(0, 0, 0))
        y += 38
        
    img.save(output_path)
    print("Mock document scan created successfully!")
    return output_path

def test_ocr_and_parsing():
    print("\n========================================================")
    print("            RUNNING PADDLEOCR SANITY CHECK")
    print("========================================================")
    
    # Create the test image
    img_path = create_mock_scan()
    
    # Try initializing and running PaddleOCR
    try:
        print("\nLoading PaddleOCR (will download model if running for the first time)...")
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(lang='en', enable_mkldnn=False)
        print("PaddleOCR loaded successfully!")
        
        print(f"\nRunning OCR scanning on {img_path}...")
        result = ocr.ocr(img_path)
        
        print("Raw OCR result type:", type(result))
        print("Raw OCR result:")
        import pprint
        pprint.pprint(result)
        
        # We will parse it based on the structure we see
        extracted_lines = []
        if result and len(result) > 0:
            for item in result:
                # 1. Handle PaddleX v3 custom object / dict with 'rec_texts'
                if hasattr(item, 'rec_texts') and item.rec_texts:
                    extracted_lines.extend(item.rec_texts)
                elif isinstance(item, dict) and 'rec_texts' in item:
                    extracted_lines.extend(item['rec_texts'])
                elif hasattr(item, 'get') and item.get('rec_texts'):
                    extracted_lines.extend(item.get('rec_texts'))
                # 2. Handle standard PaddleOCR v2 list structure
                elif isinstance(item, list):
                    for line in item:
                        if isinstance(line, list) and len(line) > 1 and isinstance(line[1], tuple):
                            extracted_lines.append(line[1][0])
                            
        print("\n--- OCR EXTRACTED TEXT LINES ---")
        for i, line in enumerate(extracted_lines):
            print(f"[{i+1:02d}] {line}")
        
        print("\n--- HEURISTIC PARSING RESULTS ---")
        suggestions = parse_extracted_text(extracted_lines)
        for key, val in suggestions.items():
            val_str = str(val).replace('\u20b9', 'Rs.')
            print(f"{key:<20}: {val_str}")
            
    except ImportError:
        print("\n[ERROR] PaddleOCR is not installed in the current environment!")
        print("Please ensure you are running this script inside the virtual environment:")
        print("  .venv\\Scripts\\python test_ocr.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] OCR Execution failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_ocr_and_parsing()
