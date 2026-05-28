import unittest
from backend.calculator import (
    get_multiplier,
    get_future_prospect,
    get_deduction,
    calculate_death_compensation,
    CompensationRequest
)

class TestMPHCCalculator(unittest.TestCase):

    def test_mphc_death_compensation_validation_profile(self):
        """
        Verify the exact MPHC judicial example from the user request:
        - Monthly Income = 23,000
        - Future Prospects = 50% (Permanent job, age 25 < 40)
        - Dependents = 3 (deduction = 1/3)
        - Multiplier = 18 (age 25)
        - Conventional heads: consortium = 40,000, funeral = 15,000, estate = 15,000
        """
        # Age 25 yields a multiplier of 18
        # future_type 1 (permanent job) at age 25 yields 50% prospects
        req = CompensationRequest(
            case_type="death",
            age=25,
            monthly_income=23000.0,
            dependents=3,
            marital_status="married",
            future_type=1,
            consortium=40000.0,
            funeral_expenses=15000.0,
            loss_estate=15000.0
        )
        
        res = calculate_death_compensation(req)
        
        # Verify step-by-step intermediate and final values against expectations
        self.assertEqual(res["future_prospect_percentage"], 50)
        self.assertEqual(res["future_prospect_amount"], 11500)
        self.assertEqual(res["enhanced_monthly_income"], 34500)
        self.assertEqual(res["annual_income"], 414000)
        self.assertEqual(res["deduction_percentage"], 33)
        self.assertEqual(res["deduction_amount"], 138000)
        self.assertEqual(res["dependency_income"], 276000)
        self.assertEqual(res["multiplier"], 18)
        self.assertEqual(res["loss_of_dependency"], 4968000)
        
        # Final compensation: 4968000 + 40000 + 15000 + 15000 = 5038000
        self.assertEqual(res["final_compensation"], 5038000)
        self.assertEqual(res["final_amount"], 5038000)

        print("\n[SUCCESS] MPHC death compensation test passed with 100% mathematical precision!")
        print(f"  Enhanced Monthly Income: {res['enhanced_monthly_income']}")
        print(f"  Annual Income:           {res['annual_income']}")
        print(f"  Deduction Amount:        {res['deduction_amount']}")
        print(f"  Dependency Income:       {res['dependency_income']}")
        print(f"  Loss of Dependency:      {res['loss_of_dependency']}")
        print(f"  Final Settlement Value:  {res['final_compensation']}")

if __name__ == "__main__":
    unittest.main()
