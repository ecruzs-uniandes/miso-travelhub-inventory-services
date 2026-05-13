from fastapi import HTTPException, status


class RateOverlapError(HTTPException):
    def __init__(self, detail: str = "Rate overlaps with existing active rate"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class RateNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Rate not found")


class ForbiddenHotelError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot operate on rates of a hotel you don't belong to",
        )


class InvalidJWTError(HTTPException):
    def __init__(self, detail: str = "Invalid or missing JWT"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
