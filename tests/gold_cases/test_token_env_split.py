from joylab_etf.kis.token_store_v141 import token_path


def test_paper_and_real_token_paths_are_different():
    assert token_path("paper") != token_path("real")


def test_expected_token_filenames():
    assert token_path("paper").name == "kis_paper_token.json"
    assert token_path("real").name == "kis_real_token.json"
