import os
import json
import textwrap

from typing import List, Dict
from groq import Groq, APIError # CRITICAL: Import Groq and APIError

# agents/llm.py (top of file)
# Disable telemetry for Groq & Chroma for this process
os.environ.setdefault("GROQ_DISABLE_TELEMETRY", "1")
os.environ.setdefault("CHROMADB_ALLOW_TELEMETRY", "false")
os.environ.setdefault("CHROMA_TELEMETRY_DISABLED", "1")

def build_messages(system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

def call_llm(messages, model: str, temperature: float = 0.2, max_tokens: int = 600) -> str:
    
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        # Check for the environment variable being completely missing.
        # NOTE: Print statement will appear in stderr, but the refusal text is returned.
        print("--- LLM ERROR: GROQ_API_KEY environment variable is NOT set. ---")
        return "Refusal: Access Denied. LLM API Key Missing."
        
    try:
        # CRITICAL FIX: Instantiate the Groq client
        client = Groq(api_key=api_key) 
        
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        llm_output = (resp.choices[0].message.content or "").strip()
        
        # --- VERIFICATION PRINTS REMOVED ---
        
        return llm_output

    except APIError as e:
        # This catches Groq-specific authentication or API errors (e.g., 401 Unauthorized)
        print(f"--- LLM API ERROR (Groq) ---")
        print(f"Status: {e.status_code}. Message: {e.message}")
        print("---------------------------")
        return "Refusal: Access Denied. LLM API Error."

    except Exception as e:
        # Catch all other errors (e.g., network issues)
        print(f"--- LLM GENERAL ERROR ---")
        print(f"Error: {e}")
        print("-------------------------")
        return "Refusal: Access Denied. LLM General Error."