import os

import pytest

from ladon.addresses import InvalidAddress, b58decode, b58encode, is_valid_address, parse_address
from helpers import wallet


@pytest.mark.parametrize(
    "address",
    [
        "11111111111111111111111111111111",
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        wallet("anyone"),
    ],
)
def test_accepts_real_public_keys(address):
    assert parse_address(address) == address


def test_trims_surrounding_whitespace():
    address = wallet("pasted")
    assert parse_address(f"  {address}\n") == address


@pytest.mark.parametrize(
    "value",
    [
        "",
        "abc",
        "0" * 44,  # 0 is not in the base58 alphabet
        "O" * 44,
        "I" * 44,
        "l" * 44,
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5D" + "x" * 10,  # too long
        b58encode(bytes(31)),  # 31 bytes is not a public key
        None,
        12345,
        "<script>alert(1)</script>",
    ],
)
def test_rejects_anything_that_is_not_a_public_key(value):
    assert not is_valid_address(value)
    with pytest.raises(InvalidAddress):
        parse_address(value)


def test_base58_round_trip():
    for _ in range(50):
        raw = os.urandom(32)
        assert b58decode(b58encode(raw)) == raw


def test_leading_zero_bytes_survive_round_trip():
    raw = bytes(3) + os.urandom(29)
    assert b58decode(b58encode(raw)) == raw
