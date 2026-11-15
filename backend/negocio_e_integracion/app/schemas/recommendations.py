from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

VariableCode = Literal["soil_temperature", "soil_moisture", "soil_ph", "rainfall"]
CheckStatus = Literal["in_range", "below", "above", "not_evaluated"]
ViabilityClass = Literal["recomendado", "condicionado", "no_recomendado"]
OriginKind = Literal[
    "estaca", "nasa_power", "simulado", "manual", "laboratorio", "dataset_estimado"
]


class RecommendationRunRequest(BaseModel):
    parcel_id: UUID
    crop_ids: list[int] | None = None
    soil_window_days: int = Field(default=7, ge=1, le=90)
    rainfall_window_days: int = Field(default=30, ge=7, le=365)
    include_simulated_soil: bool = False


class AICheckOutput(BaseModel):
    variable: VariableCode
    measured: Decimal | None = None
    status: CheckStatus
    origin: OriginKind
    is_simulated: bool = False
    target_value: Decimal | None = None

    @model_validator(mode="after")
    def validate_invariants(self) -> "AICheckOutput":
        if self.status == "not_evaluated" and self.measured is not None:
            raise ValueError(f"{self.variable}: 'not_evaluated' exige measured=None.")
        if self.status != "not_evaluated" and self.measured is None:
            raise ValueError(f"{self.variable}: '{self.status}' exige un valor medido.")
        if self.variable == "soil_ph" and self.origin == "simulado":
            self.is_simulated = True
        if self.variable == "rainfall" and self.status != "not_evaluated":
            if self.origin != "nasa_power":
                raise ValueError("La lluvia evaluada debe tener origin='nasa_power'.")
        return self


class AICropEvaluationOutput(BaseModel):
    crop_id: int
    variables_ok: int = Field(ge=0, le=4)
    classification: ViabilityClass
    ml_suitability_score: Decimal | None = Field(default=None, ge=0, le=100)
    projected_days: int | None = Field(default=None, gt=0)
    future_risk_summary: str | None = None
    checks: list[AICheckOutput]

    @model_validator(mode="after")
    def validate_viability_rules(self) -> "AICropEvaluationOutput":
        expected_vars = {"soil_temperature", "soil_moisture", "soil_ph", "rainfall"}
        if {c.variable for c in self.checks} != expected_vars or len(self.checks) != 4:
            raise ValueError("Cada evaluación debe incluir exactamente las 4 variables.")
        in_range = sum(1 for c in self.checks if c.status == "in_range")
        if self.variables_ok != in_range:
            raise ValueError("variables_ok no coincide con los checks en 'in_range'.")
        expected_class: ViabilityClass = (
            "recomendado"
            if self.variables_ok == 4
            else "condicionado"
            if self.variables_ok == 3
            else "no_recomendado"
        )
        if self.classification != expected_class:
            raise ValueError(
                f"Clasificación '{self.classification}' inválida para {self.variables_ok}/4."
            )
        return self


class AIEngineResponse(BaseModel):
    evaluations: list[AICropEvaluationOutput]