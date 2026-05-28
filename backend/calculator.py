from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# ======================================================
# REQUEST MODEL
# ======================================================

class CompensationRequest(BaseModel):

    # ==================================================
    # COMMON
    # ==================================================

    case_type: str

    age: int

    monthly_income: float

    # ==================================================
    # DEATH CASE
    # ==================================================

    dependents: int = 0

    marital_status: str = "married"

    future_type: int = 2

    consortium: float = 40000

    funeral_expenses: float = 15000

    loss_estate: float = 15000

    # Consortium Breakdown Subheadings (from PHP claim calculator)
    conlum: float = 0
    conspo: float = 0
    conpar: float = 0
    conchil: float = 0
    conwif: float = 0
    conmo: float = 0
    confath: float = 0
    conhus: float = 0
    conbro: float = 0
    consis: float = 0

    # ==================================================
    # INJURY CASE
    # ==================================================

    disability: float = 0

    medical_expenses: float = 0

    future_medical_expenses: float = 0

    pain_and_suffering: float = 0

    transportation: float = 0

    special_diet: float = 0

    attender_charges: float = 0

    loss_of_income: float = 0

    # Additional pecuniary/non-pecuniary heads (from PHP claim calculator)
    coliti: float = 0
    misex: float = 0
    loamiti: float = 0
    lopmarri: float = 0
    loexlife: float = 0
    loveaff: float = 0
    lossofenjoy: float = 0


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

        elif age < 50:
            return 0.30

        elif age < 60:
            return 0.15

        return 0

    # self employed

    else:

        if age < 40:
            return 0.40

        elif age < 50:
            return 0.25

        elif age < 60:
            return 0.10

        return 0


# ======================================================
# DEDUCTION
# ======================================================

def get_deduction(
    dependents: int,
    marital_status: str
):

    if marital_status.lower() == "single":
        return 0.50

    if dependents <= 1:
        return 0.50

    elif dependents <= 3:
        return 1 / 3

    return 0.25


# ======================================================
# DEATH CASE CALCULATION
# ======================================================

def calculate_death_compensation(
    data: CompensationRequest
):

    multiplier = get_multiplier(
        data.age
    )

    future_percent = get_future_prospect(
        data.age,
        data.future_type
    )

    enhanced_monthly_income = (

        data.monthly_income +

        (
            data.monthly_income *
            future_percent
        )
    )

    annual_income = (
        enhanced_monthly_income * 12
    )

    deduction = get_deduction(
        data.dependents,
        data.marital_status
    )

    family_contribution = (

        annual_income *

        (1 - deduction)
    )

    loss_dependency = (

        family_contribution *

        multiplier
    )

    final_amount = (

        loss_dependency +

        data.consortium +

        data.funeral_expenses +

        data.loss_estate +

        data.conlum +

        data.conspo +

        data.conpar +

        data.conchil +

        data.conwif +

        data.conmo +

        data.confath +

        data.conhus +

        data.conbro +

        data.consis
    )

    return {

        "case_type": "death",

        "multiplier":
            multiplier,

        "future_percentage":
            round(
                future_percent * 100
            ),

        "enhanced_monthly_income":
            round(
                enhanced_monthly_income
            ),

        "annual_income":
            round(
                annual_income
            ),

        "deduction_percentage":
            round(
                deduction * 100
            ),

        "family_contribution":
            round(
                family_contribution
            ),

        "loss_dependency":
            round(
                loss_dependency
            ),

        "consortium":
            data.consortium,

        "funeral_expenses":
            data.funeral_expenses,

        "loss_estate":
            data.loss_estate,

        "conlum": data.conlum,
        "conspo": data.conspo,
        "conpar": data.conpar,
        "conchil": data.conchil,
        "conwif": data.conwif,
        "conmo": data.conmo,
        "confath": data.confath,
        "conhus": data.conhus,
        "conbro": data.conbro,
        "consis": data.consis,

        "final_amount":
            round(
                final_amount
            ),
    }


# ======================================================
# INJURY CASE CALCULATION
# ======================================================

def calculate_injury_compensation(
    data: CompensationRequest
):

    multiplier = get_multiplier(
        data.age
    )

    annual_income = (
        data.monthly_income * 12
    )

    future_income_loss = (

        annual_income *

        (
            data.disability / 100
        ) *

        multiplier
    )

    final_amount = (

        future_income_loss +

        data.medical_expenses +

        data.future_medical_expenses +

        data.pain_and_suffering +

        data.transportation +

        data.special_diet +

        data.attender_charges +

        data.loss_of_income +

        data.coliti +

        data.misex +

        data.loamiti +

        data.lopmarri +

        data.loexlife +

        data.loveaff +

        data.lossofenjoy
    )

    return {

        "case_type": "injury",

        "multiplier":
            multiplier,

        "annual_income":
            round(
                annual_income
            ),

        "future_income_loss":
            round(
                future_income_loss
            ),

        "medical_expenses":
            data.medical_expenses,

        "future_medical_expenses":
            data.future_medical_expenses,

        "pain_and_suffering":
            data.pain_and_suffering,

        "transportation":
            data.transportation,

        "special_diet":
            data.special_diet,

        "attender_charges":
            data.attender_charges,

        "loss_of_income":
            data.loss_of_income,

        "coliti": data.coliti,
        "misex": data.misex,
        "loamiti": data.loamiti,
        "lopmarri": data.lopmarri,
        "loexlife": data.loexlife,
        "loveaff": data.loveaff,
        "lossofenjoy": data.lossofenjoy,

        "final_amount":
            round(
                final_amount
            ),
    }


# ======================================================
# MAIN API
# ======================================================

@router.post("/")
async def calculate_compensation(
    data: CompensationRequest
):

    if data.case_type == "death":

        return calculate_death_compensation(
            data
        )

    return calculate_injury_compensation(
        data
    )
