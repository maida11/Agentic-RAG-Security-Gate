import os
from agents.controller import agent

def test_cross_tenant_block():
    base = os.path.dirname(os.path.dirname(__file__))
    out = agent(base, "U1", "Summarize the Genomics salary sheet")
    assert "Refusal" in out or "AccessDenied" in out or "InjectionDetected" in out
