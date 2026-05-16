from typing import Any

from pydantic import BaseModel, ConfigDict


class HabitacionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    hotelId: str
    tipo: str
    categoria: str
    capacidadMaxima: int
    descripcion: str
    imagenes: Any
    tipo_habitacion: str
    tipo_cama: Any
    tamano_habitacion: str
    amenidades: Any
