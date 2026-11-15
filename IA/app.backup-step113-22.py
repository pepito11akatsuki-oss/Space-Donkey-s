"""AgroStake agronomic evaluation API.

Implements the JSON contract documented in base_de_datos/gu_a_de_acoplamiento... .
This service deliberately evaluates only supplied observations; it never invents
sensor, pH, or rainfall measurements when data is missing.
"""
from __future__ import annotations

from typing import Any, Literal
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, model_validator

Variable = Literal["soil_temperature", "soil_moisture", "soil_ph", "rainfall"]
Origin = Literal["estaca", "nasa_power", "simulado", "manual", "laboratorio", "dataset_estimado"]


class ObservedValue(BaseModel):
    model_config = ConfigDict(extra="ignore")
    value: float | None = None
    unit: str
    origin: Origin
    is_simulated: bool = False
    ph_method: str | None = None


class VariableRequirement(BaseModel):
    optimal_min: float
    optimal_max: float
    unit: str | None = None

    @model_validator(mode="after")
    def valid_range(self):
        if self.optimal_min > self.optimal_max:
            raise ValueError("optimal_min no puede ser mayor que optimal_max")
        return self


class CandidateCrop(BaseModel):
    crop_id: int
    common_name_es: str
    requirements: dict[Variable, VariableRequirement]


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    parcel_id: str
    soil_texture: str | None = None
    windows: dict[str, Any] = Field(default_factory=dict)
    observed_variables: dict[Variable, ObservedValue]
    candidate_crops: list[CandidateCrop]

    @model_validator(mode="after")
    def all_observed_variables_present(self):
        expected = {"soil_temperature", "soil_moisture", "soil_ph", "rainfall"}
        missing = expected - set(self.observed_variables)
        if missing:
            raise ValueError(f"Faltan variables observadas: {', '.join(sorted(missing))}")
        return self


app = FastAPI(
    title="AgroStake Agronomy AI Engine",
    version="1.0.0",
    description="Evaluación agronómica determinista con trazabilidad de origen y datos faltantes.",
)


@app.get("/health", tags=["Sistema"])
@app.get("/api/v1/health", tags=["Sistema"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agrostake-ai", "contract": "v1"}


def _evaluate_one(variable: Variable, observed: ObservedValue, requirement: VariableRequirement) -> dict[str, Any]:
    value = observed.value
    simulated = observed.is_simulated or (variable == "soil_ph" and observed.ph_method == "simulado")
    origin = observed.origin

    if variable == "rainfall":
        # The integration guide requires NASA POWER provenance for evaluated rainfall.
        origin = "nasa_power"

    if value is None:
        status = "not_evaluated"
        target = None
    elif value < requirement.optimal_min:
        status = "below"
        target = requirement.optimal_min
    elif value > requirement.optimal_max:
        status = "above"
        target = requirement.optimal_max
    else:
        status = "in_range"
        target = None

    return {
        "variable": variable,
        "measured": value,
        "status": status,
        "origin": origin,
        "is_simulated": simulated,
        "target_value": target,
    }


def evaluate_payload(payload: EvaluationRequest) -> dict[str, Any]:
    evaluations: list[dict[str, Any]] = []
    for crop in payload.candidate_crops:
        checks = []
        for variable in ("soil_temperature", "soil_moisture", "soil_ph", "rainfall"):
            requirement = crop.requirements.get(variable)
            observed = payload.observed_variables[variable]
            if requirement is None:
                # A missing requirement is not permission to assume a range.
                check = {
                    "variable": variable,
                    "measured": None,
                    "status": "not_evaluated",
                    "origin": "nasa_power" if variable == "rainfall" else observed.origin,
                    "is_simulated": observed.is_simulated or (variable == "soil_ph" and observed.ph_method == "simulado"),
                    "target_value": None,
                }
            else:
                check = _evaluate_one(variable, observed, requirement)
            checks.append(check)

        variables_ok = sum(c["status"] == "in_range" for c in checks)
        classification = "recomendado" if variables_ok == 4 else "condicionado" if variables_ok == 3 else "no_recomendado"
        evaluations.append({
            "crop_id": crop.crop_id,
            "variables_ok": variables_ok,
            "classification": classification,
            # The current request contract supplies no validated ML feature vector.
            # Do not mislabel a rule-based score as an ML prediction.
            "ml_suitability_score": None,
            "projected_days": None,
            "future_risk_summary": None,
            "checks": checks,
        })

    return {"evaluations": evaluations}


@app.post("/api/v1/agronomy/evaluate", tags=["Evaluación agronómica"])
def evaluate(request: EvaluationRequest) -> dict[str, Any]:
    return evaluate_payload(request)
