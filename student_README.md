# Student Quickstart — Multi-Project Research Lab Knowledge Base

This quick README is for students using the starter project in the assignment.

## 1. Unzip & enter project

unzip lab_knowledge_ops_complete.zip -d lab_knowledge_ops_complete
cd lab_knowledge_ops_complete
```

## 2. Create & activate virtual environment

python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
```

## 3. Set API key (Groq)

export GROQ_API_KEY="sk-..."


## 4. Disable telemetry for clean output (process-level)

export GROQ_DISABLE_TELEMETRY=1
export CHROMADB_ALLOW_TELEMETRY=false
export CHROMA_TELEMETRY_DISABLED=1

(These are set per-process in the project code too.)

## 5. Run a smoke test (index + query)

python -m app.main --tenant U1 --query "What PPE is required in wet labs?"


## 6. Run red-team checks

python -m tools.run_redteam --config config.yaml
sed -n '1,200p' eval/redteam_results.json


## 7. Run tests
Preferred:

pytest -q

If you see import errors, run:

PYTHONPATH=. pytest -q


## 8. Clear tenant memory (helper)

python app/clear_memory.py --tenant U2


## 9. Helpful tweaks (config.yaml)
- For deterministic outputs set `llm.temperature: 0.0`.
- To limit snippets sent to LLM, edit `agents/controller.py` and cap `hits[:3]`.


## 10. Quick full run (one-liner)

python -m app.main --tenant U1 --query "What PPE is required in wet labs?"
python -m tools.run_redteam --config config.yaml
PYTHONPATH=. pytest -q
