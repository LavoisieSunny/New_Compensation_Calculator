import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.parser_heuristics import (
    clean_legal_name,
    fuzzy_match_heading,
    classify_page_fallback,
    detect_document_sections,
    score_page_importance,
    parse_chronological_events,
    extract_compensation_table_fields,
    parse_extracted_text
)

class TestParserHeuristics(unittest.TestCase):

    def test_clean_legal_name_contamination_filters(self):
        """Verify that name candidates containing contamination keywords are discarded."""
        # Standard good names should pass
        self.assertEqual(clean_legal_name("Shri Rajesh Kumar"), "Rajesh Kumar")
        self.assertEqual(clean_legal_name("Smt. Sunita Devi"), "Sunita Devi")
        self.assertEqual(clean_legal_name("Late Shri Ramesh Chand"), "Ramesh Chand")
        
        # Contaminated names should be rejected (return empty string)
        self.assertEqual(clean_legal_name("Shri Ajay Kumar, Advocate"), "")
        self.assertEqual(clean_legal_name("Justice Ranjan Gogoi"), "")
        self.assertEqual(clean_legal_name("Hon'ble Judge Saxena"), "")
        self.assertEqual(clean_legal_name("Appellant Rajesh Kumar"), "")
        self.assertEqual(clean_legal_name("Respondent Om Prakash"), "")
        self.assertEqual(clean_legal_name("versus Insurance Co"), "")
        self.assertEqual(clean_legal_name("Vakalatnama of Claimant"), "")
        self.assertEqual(clean_legal_name("Citation: 2021 SCC 54"), "")

    def test_fuzzy_heading_matching(self):
        """Verify heading matches with fuzzy patterns and digits/bullets removed."""
        keywords = ["Index", "Description of Documents", "Annexure"]
        
        # Exact and minor cases
        self.assertTrue(fuzzy_match_heading("Index", keywords))
        self.assertTrue(fuzzy_match_heading("index", keywords))
        self.assertTrue(fuzzy_match_heading("1. Index", keywords))
        self.assertTrue(fuzzy_match_heading("Annexure - A", keywords))
        
        # Spacing/fuzzy sequences
        self.assertTrue(fuzzy_match_heading("Description  of  Documents", keywords))
        self.assertTrue(fuzzy_match_heading("Description of Documents", keywords))
        
        # Non-matching headings
        self.assertFalse(fuzzy_match_heading("Introduction to Case", keywords))

    def test_score_page_importance_citation_suppression(self):
        """Verify page importance calculation and legal citation suppression."""
        # 1. High importance: claimant details + tables
        high_page = "Claimant details: Shri Rajesh, aged about 30, S/o Shri Om Prakash. Table of dependents: 3 children."
        self.assertGreaterEqual(score_page_importance(high_page, 1), 0.70)
        
        # 2. Page containing a compensation table
        comp_page = "Compensation heads: Loss of dependency: Rs. 10,00,000/-. Funeral expenses: Rs. 15,000/-."
        self.assertGreaterEqual(score_page_importance(comp_page, 4), 0.75)
        
        # 3. Citation suppressed page (precedents/heavy reasoning)
        citation_page = "It was held in the case of Sarla Verma reported in (2009) 6 SCC 121 versus Delhi Transport Corporation..."
        self.assertEqual(score_page_importance(citation_page, 5), 0.10) # strictly clamped to 0.10

    def test_chronological_event_extraction(self):
        """Verify chronological extraction for Date -> Event structures."""
        timeline = (
            "25.12.2021 -> Date of accident collision took place\n"
            "12-09-2022 -> M.C.O.P. Claim petition filed in tribunal\n"
            "27/09/2025 -> Final award passed by court\n"
        )
        
        events = parse_chronological_events(timeline)
        self.assertEqual(events["date_of_accident"], "25-12-2021")
        self.assertEqual(events["claim_petition_date"], "12-09-2022")
        self.assertEqual(events["award_date"], "27-09-2025")

    def test_compensation_table_extraction(self):
        """Verify table parsing from isolated compensation block."""
        table_text = (
            "Assessment of quantum:\n"
            "Heads of Claim | Amount (Rs.)\n"
            "1. Loss of dependency: Rs. 12,00,000/-\n"
            "2. Future prospects: 40%\n"
            "3. Multiplier: 18\n"
            "4. Funeral expenses: Rs. 15,000/-\n"
            "5. Loss of consortium: Rs. 40,000/-\n"
            "Total Compensation: Rs. 12,55,000/-\n"
            "The claimant shall be entitled to interest..."
        )
        
        fields = extract_compensation_table_fields(table_text)
        self.assertEqual(fields["monthly_income"], None) # not explicitly in table rows
        self.assertEqual(fields["annual_loss_dependency"], 1200000.0)
        self.assertEqual(fields["multiplier"], 18)
        self.assertEqual(fields["future_prospect"], 40.0)
        self.assertEqual(fields["funeral_expenses"], 15000.0)
        self.assertEqual(fields["consortium"], 40000.0)
        self.assertEqual(fields["total_compensation"], 1255000.0)

    def test_dynamic_section_detection_and_fallback(self):
        """Verify dynamic sections are detected by headings, and fall back correctly when missing."""
        mock_pages = [
            {
                "page_number": 1,
                "lines": [
                    "--- PAGE 1 ---",
                    "CLAIM PETITION BEFORE THE TRIBUNAL",
                    "Claimant Name: Shri Rajesh Kumar S/o Shri Om Prakash",
                    "Aged about 30 years, resident of Chennai"
                ],
                "text": "CLAIM PETITION BEFORE THE TRIBUNAL\nClaimant Name: Shri Rajesh Kumar S/o Shri Om Prakash\nAged about 30 years, resident of Chennai"
            },
            {
                "page_number": 2,
                "lines": [
                    "--- PAGE 2 ---",
                    "CHRONOLOGICAL EVENTS",
                    "25.12.2021 -> Date of accident",
                    "12.09.2022 -> Petition filed"
                ],
                "text": "CHRONOLOGICAL EVENTS\n25.12.2021 -> Date of accident\n12.09.2022 -> Petition filed"
            },
            {
                "page_number": 3,
                "lines": [
                    "--- PAGE 3 ---",
                    "This is page 3 text which has no explicit heading.",
                    "But it contains compensation figures:",
                    "Disability Compensation: Rs. 2,00,000/-",
                    "Total awarded sum: Rs. 2,40,000/-"
                ],
                "text": "This is page 3 text which has no explicit heading.\nBut it contains compensation figures:\nDisability Compensation: Rs. 2,00,000/-\nTotal awarded sum: Rs. 2,40,000/-"
            }
        ]
        
        full_text = "\n".join(p["text"] for p in mock_pages)
        sections = detect_document_sections(full_text, mock_pages)
        
        # Chronological Events Section should be detected via heading on Page 2
        self.assertIn("chronological_events_section", sections)
        self.assertEqual(sections["chronological_events_section"]["start_page"], 2)
        self.assertTrue(sections["chronological_events_section"]["strong_match"])
        
        # Compensation Section has no heading, but Page 3 matches its fallback cues
        self.assertIn("compensation_section", sections)
        self.assertEqual(sections["compensation_section"]["start_page"], 3)
        self.assertFalse(sections["compensation_section"]["strong_match"]) # fallback layout match

    def test_parse_extracted_text_end_to_end(self):
        """Verify full parsing suggestion output and confidence scores block."""
        ocr_lines = [
            "--- PAGE 1 ---",
            "BEFORE THE MOTOR ACCIDENTS CLAIMS TRIBUNAL",
            "Claimants: Shri Rajesh Kumar",
            "S/o Shri Om Prakash Sharma, Resident of Chennai",
            "Date of Birth: 12-04-1992 (Age: 30)",
            "--- PAGE 2 ---",
            "CHRONOLOGICAL EVENTS",
            "25.12.2021 -> Date of accident took place",
            "12.09.2022 -> Claim Petition filed in Chennai",
            "--- PAGE 3 ---",
            "AWARD COPY",
            "1. Monthly income: Rs. 25,000/-",
            "2. Multiplier: 17",
            "3. Total Compensation: Rs. 4,50,000/-"
        ]
        
        suggestions = parse_extracted_text(ocr_lines)
        
        # Verify flat keys
        self.assertEqual(suggestions["name"], "Rajesh Kumar")
        self.assertEqual(suggestions["father_name"], "Om Prakash Sharma")
        self.assertEqual(suggestions["date_of_accident"], "25-12-2021")
        self.assertEqual(suggestions["monthly_income"], 25000.0)
        self.assertEqual(suggestions["multiplier"], 17)
        self.assertEqual(suggestions["total_compensation"], 450000.0)
        
        # Verify detailed tracking under confidence_scores
        scores = suggestions["confidence_scores"]
        
        # 1. Claimant Name
        self.assertEqual(scores["claimant_name"]["value"], "Rajesh Kumar")
        self.assertEqual(scores["claimant_name"]["source_section"], "claimant_section")
        self.assertEqual(scores["claimant_name"]["source_page"], 1)
        self.assertIn("extraction_method", scores["claimant_name"])
        
        # 2. Date of accident
        self.assertEqual(scores["date_of_accident"]["value"], "25-12-2021")
        self.assertEqual(scores["date_of_accident"]["source_section"], "chronological_events_section")
        self.assertEqual(scores["date_of_accident"]["source_page"], 2)
        
        # 3. Monthly Income
        self.assertEqual(scores["monthly_income"]["value"], 25000.0)
        self.assertEqual(scores["monthly_income"]["source_section"], "compensation_section")
        self.assertEqual(scores["monthly_income"]["source_page"], 3)

    def test_parse_extracted_text_injury_table_flat_keys(self):
        """Verify that the parser correctly extracts and maps complex table parameters into flat suggestion keys."""
        ocr_lines = [
            "--- PAGE 1 ---",
            "CLAIM PETITION BEFORE THE TRIBUNAL",
            "Claimants: Shri Suresh Kumar S/o Shri Ram Lal",
            "Date of Birth: 01-01-1970 (Age: 55)",
            "--- PAGE 2 ---",
            "CHRONOLOGICAL EVENTS",
            "25.12.2021 -> Date of accident",
            "--- PAGE 3 ---",
            "COMPENSATION AWARD COPY",
            "Disability is assessed as 10%",
            "We award the following compensation:",
            "1. Medical Expenses: Rs. 50,000/-",
            "2. Pain and Suffering: Rs. 40,000/-",
            "3. Transportation: Rs. 15,000/-",
            "4. Special Diet / Extra Nourishment: Rs. 10,000/-",
            "5. Attender Charges: Rs. 12,000/-",
            "6. Loss Of Earnings: Rs. 30,000/-",
            "7. Future Medical Treatment: Rs. 20,000/-",
            "Total Compensation awarded: Rs. 1,77,000/-"
        ]
        
        suggestions = parse_extracted_text(ocr_lines)
        
        # Verify custom flat keys for injury table
        self.assertEqual(suggestions["medical_expenses"], 50000.0)
        self.assertEqual(suggestions["pain_and_suffering"], 40000.0)
        self.assertEqual(suggestions["transportation"], 15000.0)
        self.assertEqual(suggestions["special_diet"], 10000.0)
        self.assertEqual(suggestions["attender_charges"], 12000.0)
        self.assertEqual(suggestions["loss_of_income"], 30000.0)
        self.assertEqual(suggestions["future_medical_expenses"], 20000.0)


if __name__ == "__main__":
    unittest.main()
