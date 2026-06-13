from epayroll.db.repositories import _decimo_trimestre


def test_decimo_trimestre_mapping():
    assert _decimo_trimestre(12) == 1
    assert _decimo_trimestre(3) == 1
    assert _decimo_trimestre(4) == 2
    assert _decimo_trimestre(7) == 2
    assert _decimo_trimestre(8) == 3
    assert _decimo_trimestre(11) == 3
