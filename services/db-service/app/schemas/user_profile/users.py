from enum import Enum


class UserRole(str, Enum):
    """
    Enumeration of supported user roles:: root, primary_admin, admin, resident,
            security
    """

    ROOT = "root"
    PRIMARY_ADMIN = "primary_admin"
    ADMIN = "admin"
    RESIDENT = "resident"
    SECURITY = "security"
