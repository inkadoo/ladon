ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INDEX = {c: i for i, c in enumerate(ALPHABET)}


class InvalidAddress(ValueError):
    pass


def b58decode(value: str) -> bytes:
    num = 0
    for char in value:
        if char not in _INDEX:
            raise InvalidAddress(f"invalid base58 character {char!r}")
        num = num * 58 + _INDEX[char]
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    leading_zeros = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeros + body


def b58encode(raw: bytes) -> str:
    num = int.from_bytes(raw, "big")
    out = ""
    while num:
        num, rem = divmod(num, 58)
        out = ALPHABET[rem] + out
    leading_zeros = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * leading_zeros + out


def parse_address(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidAddress("address must be a string")
    candidate = value.strip()
    if not 32 <= len(candidate) <= 44:
        raise InvalidAddress("address must be 32 to 44 characters")
    if len(b58decode(candidate)) != 32:
        raise InvalidAddress("address must decode to 32 bytes")
    return candidate


def parse_signature(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidAddress("signature must be a string")
    candidate = value.strip()
    if not 64 <= len(candidate) <= 88 or len(b58decode(candidate)) != 64:
        raise InvalidAddress("not a transaction signature")
    return candidate


def is_valid_address(value: object) -> bool:
    try:
        parse_address(value)
    except InvalidAddress:
        return False
    return True
