import hashlib

from app.schemas.code_service import Receiver


def generate_unique_code(
    user_id: str,
    estate_id: str,
    visitor_fullname: str = None,
    relationship_with_resident: str = None,
    date: str = None,
    hour: str = None,
    receiver: Receiver = None,
) -> str:
    """
    Generate a unique 6-character alphanumeric code based on input details.

    Arguments:
        user_id (str): The unique identifier for the user (e.g., a UUID).
        visitor_fullname (str): The name of the visitor.
        relationship_with_resident (str): The relationship of the visitor to
            the user.
        date (str): The date of the visit, typically in YYYY-MM-DD
            format.
        hour (str): The hour of the visit.
        recevier (Receiver): The status of the code owner (visitor or resident)
            which determines the logic pathway to execute.

    Returns:
        str: A 6-character alphanumeric code that uniquely represents the
            combination of the input values.
    """

    # Combine the input fields into a single string
    if receiver == Receiver.VISITOR:
        combined = (
            f"{user_id}|{estate_id}|{visitor_fullname}|"
            f"{relationship_with_resident}|{date}|{hour}"
        )
    else:
        combined = f"{user_id}|{estate_id}|{date}|{hour}"

    # Compute the SHA256 hash of the combined string
    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    hash_int = int(hash_obj.hexdigest(), 16)

    # Reduce the hash to a number that fits in 6 base-36 digits
    mod_value = hash_int % (36**6)

    # Convert the number to a 6-character base-36 string
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code = ""
    for _ in range(6):
        mod_value, i = divmod(mod_value, 62)
        code = alphabet[i] + code

    return code


if __name__ == "__main__":
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    estate_id = "123e4567-e89b-12d3-a456-426614174000"
    visitor_fullname = "Michael"
    relationship_with_resident = "friend"
    date = "2025-04-06"
    print(
        generate_unique_code(
            user_id,
            estate_id,
            visitor_fullname,
            relationship_with_resident,
            date,
        )
    )
