from enum import Enum


class Relation(str, Enum):
    """
    Enumeration of supported resident-guest relation: family, spouse,
            friend, delivery, taxi, technician
    """

    FAMILY = "family"
    SPOUSE = "spouse"
    FRIEND = "friend"
    TECHNICIAN = "technician"
    TAXI = "taxi"
    DELIVERY = "delivery"
