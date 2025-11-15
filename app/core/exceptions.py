from fastapi import HTTPException, status

class BaseHTTPException(HTTPException):
    def __init__(self, status_code: int, detail: str = None):
        super().__init__(status_code=status_code, detail=detail)

class InvalidCredentialsException(BaseHTTPException):
    def __init__(self, detail: str = "Incorrect email or password"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

class InactiveUserException(BaseHTTPException):
    def __init__(self, detail: str = "Inactive user"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

class InvalidTokenException(BaseHTTPException):
    def __init__(self, detail: str = "Invalid or expired token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

class UserAlreadyExistsException(BaseHTTPException):
    def __init__(self, detail: str = "User with this email already exists"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

class PermissionDeniedException(BaseHTTPException):
    def __init__(self, detail: str = "Not enough permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
