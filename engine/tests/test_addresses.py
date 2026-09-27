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
        "0" * 44,
        "O" * 44,
        "I" * 44,
        "l" * 44,
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5D" + "x" * 10,
        b58encode(bytes(31)),
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


def test_wallets_are_on_the_curve_and_program_addresses_are_not():
    from ladon.addresses import is_on_curve

    assert is_on_curve("9AhKqLR67hwapvG8SA2JFXaCshXc9nALJjpKaHZrsbkw")
    assert is_on_curve("3q13J4n4sgzKCQsmabdXfphaFAgUja16jNZqqHp2gbmw")
    assert not is_on_curve("8WWGEGBdkwzuENVS3ihUHsKVFGsiLbU5ow83cF8w9kYd")
    assert not is_on_curve("FhVo3mqL8PW5pH5U2CN4XE33DokiyZnUwuGpH2hmHLuM")
