class NotFoundError(Exception):
    """Exception raised when a resource is not found."""

    pass


class DatabaseError(Exception):
    """Exception raised when a database error occurs."""

    pass


class ValidationError(Exception):
    """Exception raised when a validation error occurs."""

    pass
