"""
Prediction API schemas
"""

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """
    input features for accident severity prediction.
    catv remapped from 40 to 7 cats (0-6)
    atm remapped from 9 to bin
    other features are normed/scaled
    """

    # id_usager   : int = Field(..., ge=1, description="usager id")
    place: int = Field(..., ge=1, le=10, description="place took by a usager in a vehicle")
    catu: int = Field(..., ge=1, le=3, description="usager cat, 1:driver, 2:passenger, 3:pedestrian ")
    sexe: int = Field(..., ge=1, le=2, description="sexe, 1:male, 2:female")
    secu1: int = Field(
        ...,
        ge=0,
        le=9,
    )
    year_acc: int = Field(..., ge=2021, le=2024, description="year of the accident, extracted from Num_acc")
    victim_age: float = Field(..., ge=1, description="victim age: year_acc - an_nais")
    nb_victim: int = Field(..., ge=1, description="total of victim in an acc")
    catv: int = Field(..., ge=0, le=6, description="vehicle cat")
    obsm: int = Field(..., ge=0, le=6, description="mobile obstacle")
    motor: int = Field(
        ...,
        ge=0,
        le=6,
    )
    nb_vehicles: int = Field(
        ...,
        ge=1,
    )
    catr: int = Field(..., ge=1, le=9, description="road cat (1-9)")
    circ: int = Field(
        ...,
        ge=1,
        le=4,
    )
    surf: int = Field(
        ...,
        ge=1,
        le=9,
    )
    situ: int = Field(
        ...,
        ge=1,
        le=5,
    )
    vma: int = Field(
        ...,
        ge=1,
    )
    jour: int = Field(
        ...,
        ge=1,
        le=31,
    )
    mois: int = Field(
        ...,
        ge=1,
        le=12,
    )
    lum: int = Field(
        ...,
        ge=1,
        le=5,
    )
    dep: int = Field(
        ...,
        ge=1,
        le=976,
    )
    com: int = Field(
        ...,
        ge=1,
    )
    agg: int = Field(..., ge=1, le=2)
    int_: int = Field(
        ...,
        ge=1,
        le=9,
        alias="int",
    )
    atm: int = Field(
        ...,
        ge=0,
        le=1,
    )
    col: int = Field(
        ...,
        ge=1,
        le=7,
    )
    lat: float = Field(
        ...,
        ge=41.0,
        le=51.0,
    )
    long: float = Field(
        ...,
        ge=-5.0,
        le=10.0,
    )
    hour: int = Field(
        ...,
        ge=0,
        le=23,
    )


class PredictionResponse(BaseModel):
    """prediction result."""

    severity: str = Field(..., description="severity prediction in text")
    severity_code: int = Field(..., ge=0, le=1, description="0=Indemne/Léger, 1=Blessé hosp./Tué")
    probability: float | None = Field(..., description="class probability")
    model_used: str = Field(..., description="model name used")


class HealthResponse(BaseModel):
    """health check response."""

    status: str
    model_loaded: bool
    model_name: str | None = None
