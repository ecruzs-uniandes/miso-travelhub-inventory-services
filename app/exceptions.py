from fastapi import HTTPException, status


class RateOverlapError(HTTPException):
    """409: dos tarifas no pueden cubrir rangos solapados para la misma habitacion."""

    def __init__(self, detail: str = "La tarifa solapa con otra existente"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class RateNotFoundError(HTTPException):
    """404: tarifa o habitacion no encontrada."""

    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Tarifa no encontrada")


class ForbiddenHotelError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puede operar sobre tarifas de un hotel ajeno",
        )


class InvalidJWTError(HTTPException):
    def __init__(self, detail: str = "Invalid or missing JWT"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
