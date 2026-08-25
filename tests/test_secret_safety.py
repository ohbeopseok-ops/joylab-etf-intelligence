from pathlib import Path

def test_env_is_gitignored():
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env" in text
