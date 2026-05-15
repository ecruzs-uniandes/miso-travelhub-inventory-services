from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TarifaCreate(BaseModel):
    habitacionId: str
    precioBase: float = Field(gt=0)
    fechaInicio: datetime
    fechaFin: datetime
    descuento: float = Field(default=0.0, ge=0, le=1)

    @model_validator(mode="after")
    def _check_dates(self) -> "TarifaCreate":
        if self.fechaInicio > self.fechaFin:
            raise ValueError("fechaInicio must be <= fechaFin")
        return self


class TarifaUpdate(BaseModel):
    precioBase: float | None = Field(default=None, gt=0)
    fechaInicio: datetime | None = None
    fechaFin: datetime | None = None
    descuento: float | None = Field(default=None, ge=0, le=1)


class TarifaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    habitacionId: str
    precioBase: float
    moneda: str
    fechaInicio: datetime
    fechaFin: datetime
    descuento: float


class TarifaVigente(BaseModel):
    """Tarifa que aplica para una fecha consultada, con precio final calculado."""

    model_config = ConfigDict(from_attributes=True)

    tarifaId: str
    habitacionId: str
    precioBase: float
    moneda: str
    descuento: float
    precioFinal: float
    fechaInicio: datetime
    fechaFin: datetime
