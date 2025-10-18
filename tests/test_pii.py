import os, re
from agents.controller import agent

def test_pii_masking():
    base = os.path.dirname(os.path.dirname(__file__))
    out = agent(base, "U3", "Summarize Robotics internal memos")
    assert not re.search(r"\b\d{5}-\d{7}-\d\b", out)
    assert not re.search(r"\+?92-?\d{3}-?\d{7}", out)
