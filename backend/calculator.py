import logging
from typing import Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel, model_validator

logger = logging.getLogger("backend.calculator")
router = APIRouter()

# ======================================================
# SAFE NUMERIC PARSING HELPERS (Task 4)
# ======================================================

def safe_float(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

# ======================================================
# REQUEST MODEL
# ======================================================

class CompensationRequest(BaseModel):

    # ==================================================
    # COMMON
    # ==================================================

    case_type: str = "injury"

    age: int = 30

    monthly_income: float = 0.0

    # ==================================================
    # DEATH CASE
    # ==================================================

    dependents: int = 0

    marital_status: str = "married"

    future_type: int = 2

    consortium: float = 40000.0

    funeral_expenses: float = 15000.0

    loss_estate: float = 15000.0

    # Consortium Breakdown Subheadings (from PHP claim calculator)
    conlum: float = 0.0
    conspo: float = 0.0
    conpar: float = 0.0
    conchil: float = 0.0
    conwif: float = 0.0
    conmo: float = 0.0
    confath: float = 0.0
    conhus: float = 0.0
    conbro: float = 0.0
    consis: float = 0.0

    # ==================================================
    # INJURY CASE
    # ==================================================

    disability: float = 0.0

    medical_expenses: float = 0.0

    future_medical_expenses: float = 0.0

    pain_and_suffering: float = 0.0

    transportation: float = 0.0

    special_diet: float = 0.0

    attender_charges: float = 0.0

    loss_of_income: float = 0.0

    # Additional pecuniary/non-pecuniary heads (from PHP claim calculator)
    coliti: float = 0.0
    misex: float = 0.0
    loamiti: float = 0.0
    lopmarri: float = 0.0
    loexlife: float = 0.0
    loveaff: float = 0.0
    lossofenjoy: float = 0.0

    @model_validator(mode='before')
    @classmethod
    def clean_empty_strings(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        
        cleaned = {}
        for k, v in data.items():
            # If the value is empty string, string 'null', string 'NaN', or None
            if v == "" or v == "NaN" or v == "null" or v is None:
                # Provide safe defaults if the value is empty
                if k == "case_type":
                    cleaned[k] = "injury"
                elif k == "marital_status":
                    cleaned[k] = "married"
                elif k in ["age", "future_type"]:
                    cleaned[k] = 30 if k == "age" else 2
                elif k in ["monthly_income", "consortium", "funeral_expenses", "loss_estate", "disability"]:
                    if k == "consortium":
                        cleaned[k] = 40000.0
                    elif k in ["funeral_expenses", "loss_estate"]:
                        cleaned[k] = 15000.0
                    else:
                        cleaned[k] = 0.0
                else:
                    cleaned[k] = 0.0 if k in [
                        "medical_expenses", "future_medical_expenses", "pain_and_suffering",
                        "transportation", "special_diet", "attender_charges", "loss_of_income",
                        "conlum", "conspo", "conpar", "conchil", "conwif", "conmo", "confath",
                        "conhus", "conbro", "consis", "coliti", "misex", "loamiti", "lopmarri",
                        "loexlife", "loveaff", "lossofenjoy"
                    ] else 0
            else:
                # Coerce numeric values if passed as string but non-empty
                if k in ["age", "dependents", "future_type"]:
                    cleaned[k] = safe_int(v)
                elif k in [
                    "monthly_income", "consortium", "funeral_expenses", "loss_estate", "disability",
                    "medical_expenses", "future_medical_expenses", "pain_and_suffering",
                    "transportation", "special_diet", "attender_charges", "loss_of_income",
                    "conlum", "conspo", "conpar", "conchil", "conwif", "conmo", "confath",
                    "conhus", "conbro", "consis", "coliti", "misex", "loamiti", "lopmarri",
                    "loexlife", "loveaff", "lossofenjoy"
                ]:
                    cleaned[k] = safe_float(v)
                else:
                    cleaned[k] = v
        return cleaned


# ======================================================
# SARLA VERMA MULTIPLIER
# ======================================================

def get_multiplier(age: int):

    if age <= 15:
        return 15  # Corrected to match MPHC PHP formula exactly

    elif age <= 20:
        return 18

    elif age <= 25:
        return 18

    elif age <= 30:
        return 17

    elif age <= 35:
        return 16

    elif age <= 40:
        return 15

    elif age <= 45:
        return 14

    elif age <= 50:
        return 13

    elif age <= 55:
        return 11

    elif age <= 60:
        return 9

    elif age <= 65:
        return 7

    return 5


# ======================================================
# FUTURE PROSPECTS
# ======================================================

def get_future_prospect(
    age: int,
    future_type: int
):

    # permanent job

    if future_type == 1:

        if age < 40:
            return 0.50

        elif age <= 50:
            return 0.30

        elif age <= 60:
            return 0.15

        return 0.0

    # self employed / fixed salary / daily wage

    else:

        if age < 40:
            return 0.40

        elif age <= 50:
            return 0.25

        elif age <= 60:
            return 0.10

        return 0.0


# ======================================================
# DEDUCTION
# ======================================================

def get_deduction(
    dependents: int,
    marital_status: str
):
    if not marital_status:
        marital_status = "married"
        
    dependents = safe_int(dependents, 0)

    if marital_status.lower() == "single":
        return 0.50

    if dependents <= 1:
        return 0.50

    elif dependents <= 3:
        return 0.33

    elif dependents <= 6:
        return 0.25

    return 0.20


# ======================================================
# DEATH CASE CALCULATION
# ======================================================

def calculate_death_compensation(
    data: CompensationRequest
):
    age = safe_int(data.age, 30)
    monthly_income = safe_float(data.monthly_income, 0.0)
    dependents = safe_int(data.dependents, 0)
    marital_status = data.marital_status or "married"
    future_type = safe_int(data.future_type, 2)

    multiplier = get_multiplier(age)
    future_percent = get_future_prospect(age, future_type)
    future_prospect_percentage = round(future_percent * 100)

    annual_income = monthly_income * 12
    future_income = annual_income + (annual_income * future_prospect_percentage / 100)

    deduction_ratio = get_deduction(dependents, marital_status)
    deduction_percentage = round(deduction_ratio * 100)
    deduction_amount = future_income * (deduction_percentage / 100)

    dependency_income = future_income - deduction_amount
    loss_of_dependency = dependency_income * multiplier

    # Conventional heads with safe_float
    consortium = safe_float(data.consortium, 40000.0)
    funeral_expenses = safe_float(data.funeral_expenses, 15000.0)
    loss_estate = safe_float(data.loss_estate, 15000.0)

    final_compensation = (
        loss_of_dependency +
        consortium +
        funeral_expenses +
        loss_estate
    )

    return {
        "case_type": "death",
        "annual_income": round(annual_income),
        "future_income": round(future_income),
        "future_prospect_percentage": future_prospect_percentage,
        "deduction_percentage": deduction_percentage,
        "deduction_amount": round(deduction_amount),
        "dependency_income": round(dependency_income),
        "multiplier": multiplier,
        "loss_of_dependency": round(loss_of_dependency),
        "consortium": consortium,
        "funeral_expenses": funeral_expenses,
        "loss_estate": loss_estate,
        "final_compensation": round(final_compensation),
        "final_amount": round(final_compensation)
    }



# ======================================================
# INJURY CASE CALCULATION
# ======================================================

def calculate_injury_compensation(
    data: CompensationRequest
):
    age = safe_int(data.age, 30)
    monthly_income = safe_float(data.monthly_income, 0.0)
    disability = safe_float(data.disability, 0.0)

    multiplier = get_multiplier(age)
    annual_income = monthly_income * 12
    future_income_loss = annual_income * (disability / 100.0) * multiplier

    medical_expenses = safe_float(data.medical_expenses, 0.0)
    future_medical_expenses = safe_float(data.future_medical_expenses, 0.0)
    pain_and_suffering = safe_float(data.pain_and_suffering, 0.0)
    transportation = safe_float(data.transportation, 0.0)
    special_diet = safe_float(data.special_diet, 0.0)
    attender_charges = safe_float(data.attender_charges, 0.0)
    loss_of_income = safe_float(data.loss_of_income, 0.0)

    coliti = safe_float(data.coliti, 0.0)
    misex = safe_float(data.misex, 0.0)
    loamiti = safe_float(data.loamiti, 0.0)
    lopmarri = safe_float(data.lopmarri, 0.0)
    loexlife = safe_float(data.loexlife, 0.0)
    loveaff = safe_float(data.loveaff, 0.0)
    lossofenjoy = safe_float(data.lossofenjoy, 0.0)

    final_amount = (
        future_income_loss +
        medical_expenses +
        future_medical_expenses +
        pain_and_suffering +
        transportation +
        special_diet +
        attender_charges +
        loss_of_income +
        coliti +
        misex +
        loamiti +
        lopmarri +
        loexlife +
        loveaff +
        lossofenjoy
    )

    return {
        "case_type": "injury",
        "multiplier": multiplier,
        "annual_income": round(annual_income),
        "future_income_loss": round(future_income_loss),
        "medical_expenses": medical_expenses,
        "future_medical_expenses": future_medical_expenses,
        "pain_and_suffering": pain_and_suffering,
        "transportation": transportation,
        "special_diet": special_diet,
        "attender_charges": attender_charges,
        "loss_of_income": loss_of_income,
        "coliti": coliti,
        "misex": misex,
        "loamiti": loamiti,
        "lopmarri": lopmarri,
        "loexlife": loamiti,
        "loveaff": loveaff,
        "lossofenjoy": lossofenjoy,
        "final_amount": round(final_amount),
    }


# ======================================================
# MAIN API
# ======================================================

@router.post("/")
async def calculate_compensation(
    data: CompensationRequest
):
    logger.info(f"Incoming calculation request payload: {data.dict() if data else 'None'}")
    try:
        case_type = str(data.case_type).strip().lower()
        logger.info(f"Parsed calculation case_type: {case_type}")
        
        if case_type == "death":
            breakdown = calculate_death_compensation(data)
        else:
            breakdown = calculate_injury_compensation(data)

        # Log formula inputs & parsed parameters as requested
        logger.info(f"Formula inputs & parsed parameters: {breakdown}")
        
        final_amount = breakdown.get("final_amount", 0)
        
        # Build standard Step 7 stable nested output schema
        response = {
            "success": True,
            "calculation_type": case_type,
            "total_compensation": final_amount,
            "breakdown": breakdown
        }
        # Merge breakdown keys into root for backwards compatibility with any flat-keyed expectations
        response.update(breakdown)

        logger.info(f"Successfully computed compensation. Total: {final_amount}")
        return response

    except Exception as e:
        logger.exception("CRITICAL EXCEPTION IN SERVER COMPENSATION CALCULATION PIPELINE:")
        # Return stable schema even on failures to prevent frontend crash
        return {
            "success": False,
            "calculation_type": data.case_type if data else "unknown",
            "total_compensation": 0,
            "breakdown": {},
            "error": str(e)
        }
