import argparse, os, sys, json, time, shutil
from typing import Any, Dict
import yaml

# Core Agent Imports
from agents.controller import agent, _load_cfg_from_disk, _load_llm_cfg 
from policies.guard import mask_pii 
# NOTE: The provided agents/llm.py imports groq, so we don't need it here.

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STATE_DIR = os.path.join(BASE_DIR, ".state", "memory") 

VALID_TENANTS = ['U1', 'U2', 'U3', 'U4']
VALID_MEM_MODES = ['buffer', 'summary', 'none']
SUMMARY_PROMPT = "Summarize the following conversation for context in the next turn. The summary must be concise and retain only masked, factual information. Do not include any PII."


# --- MEMORY MANAGER CLASS (Integrated into main.py) ---
class MemoryManager:
    """Handles tenant-isolated, PII-masked Buffer and Summary memory."""
    def __init__(self, tenant_id: str, initial_type: str):
        self.tenant_id = tenant_id
        self.memory_type = initial_type
        self.memory_path = os.path.join(STATE_DIR, tenant_id)
        os.makedirs(self.memory_path, exist_ok=True)
        self.buffer_file = os.path.join(self.memory_path, "buffer.jsonl")
        self.summary_file = os.path.join(self.memory_path, "summary.txt")

    def get_context(self) -> str | None:
        """Retrieves the current memory context (Buffer or Summary)."""
        if self.memory_type == 'summary' and os.path.exists(self.summary_file):
            with open(self.summary_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        if self.memory_type == 'buffer' and os.path.exists(self.buffer_file):
            context_lines = []
            with open(self.buffer_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        turn = json.loads(line)
                        context_lines.append(f"User: {turn['user']}")
                        context_lines.append(f"Assistant: {turn['assistant']}")
                    except json.JSONDecodeError:
                        continue
            return "\n".join(context_lines)
            
        return None

    def update_memory(self, user_query: str, assistant_response: str, cfg: Dict[str, Any]):
        """Updates memory, ensuring PII is masked before persistence."""
        
        # CRITICAL: Mask PII before saving to memory or LLM summary processing
        masked_user = mask_pii(user_query)
        masked_assistant = mask_pii(assistant_response)
        
        turn_data = {
            "user": masked_user,
            "assistant": masked_assistant,
            "timestamp": time.time()
        }
        
        # 1. Update Buffer (for both buffer and summary tracking)
        with open(self.buffer_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(turn_data) + '\n')

        # 2. Handle Summary Mode
        if self.memory_type == 'summary':
            # Dynamic imports are fine here since they are only used in this mode
            from agents.llm import call_llm, build_messages 
            
            # Re-read the full buffer context for summarization (must contain masked data)
            current_buffer_content = self.get_context() 
            if current_buffer_content:
                
                # Load LLM config using the imported helper function
                model, temp, max_t = _load_llm_cfg(cfg) 

                summary_prompt_messages = build_messages(
                    system_prompt=SUMMARY_PROMPT,
                    user_prompt=current_buffer_content
                )
                
                # NOTE: This calls the LLM for summarization
                new_summary = call_llm(summary_prompt_messages, model, temp, max_t)

                # Write the new summary
                with open(self.summary_file, 'w', encoding='utf-8') as f:
                    f.write(new_summary)
                    
                # Truncate buffer after summary refresh (optional/allowed)
                if os.path.exists(self.buffer_file):
                     os.remove(self.buffer_file)
    
    def set_mode(self, new_mode: str):
        """Sets a new memory mode."""
        if new_mode in VALID_MEM_MODES:
            self.memory_type = new_mode
            return True
        return False
    
    @staticmethod
    def clear_tenant_memory(tenant_id: str):
        """Deletes .state/memory/<tenant>/* when called."""
        tenant_memory_path = os.path.join(STATE_DIR, tenant_id)
        if os.path.exists(tenant_memory_path):
            shutil.rmtree(tenant_memory_path)
            return f"Memory cleared for tenant {tenant_id}"
        return f"No memory found for tenant {tenant_id}"


# --- MAIN EXECUTION FUNCTIONS ---

def run_single_turn(tenant: str, query: str, memory_mode: str, config_path: str):
    """Handles the single-turn execution mode."""
    cfg = _load_cfg_from_disk(BASE_DIR)
    
    # Load any existing context, but won't persist
    mem_manager = MemoryManager(tenant, memory_mode)
    memory_context = mem_manager.get_context()
    
    result = agent(BASE_DIR, tenant, query, cfg, memory_context, memory_mode)
    print(result)

def run_chat_repl(tenant: str, initial_mode: str, config_path: str):
    """Handles the interactive chat REPL mode."""
    print(f"--- Agentic RAG Chat REPL (Tenant: {tenant}, Mode: {initial_mode}) ---")
    print("Commands: /clear, /mode [buffer|summary|none], /exit")
    
    cfg = _load_cfg_from_disk(BASE_DIR)
    mem_manager = MemoryManager(tenant, initial_mode)
    
    while True:
        try:
            # Check for EOF/Ctrl+C
            if sys.stdin.isatty():
                user_input = input(f"[{tenant}/{mem_manager.memory_type}] > ")
            else: # Handle non-interactive input if applicable
                user_input = sys.stdin.readline().strip()
                if not user_input:
                    break
            
            if not user_input.strip():
                continue
            
            # --- Command Handling ---
            if user_input.lower() == '/exit':
                break
            
            elif user_input.lower() == '/clear':
                print(MemoryManager.clear_tenant_memory(tenant))
                continue
            
            elif user_input.lower().startswith('/mode '):
                parts = user_input.lower().split(' ')
                if len(parts) == 2 and mem_manager.set_mode(parts[1].strip()):
                    print(f"Memory mode switched to {mem_manager.memory_type}.")
                else:
                    print("Usage: /mode [buffer|summary|none]")
                continue

            # --- Agentic Loop Execution ---
            memory_context = mem_manager.get_context()
            result_text = agent(BASE_DIR, tenant, user_input, cfg, memory_context, mem_manager.memory_type)
            print(result_text)
            
            # 4. Update memory (only if not a refusal, and if memory mode is active)
            # The agent returns the full output (Answer + Citations OR Refusal)
            if not result_text.startswith("Refusal:") and mem_manager.memory_type != 'none':
                # Split the answer from the citations for storage
                parts = result_text.split('\n')
                answer_only = "\n".join([p for p in parts if not p.startswith('[')])
                
                # Use the original user input, but the full output result as the "assistant" response
                mem_manager.update_memory(user_input, result_text, cfg)
            

        except EOFError:
            print("\nExiting REPL.")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            sys.exit(1)


# NOTE: Keeping the provided load_cfg function structure from your starter
def load_cfg(path: str):
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def main():
    parser = argparse.ArgumentParser(description="Agentic RAG CLI and Chat REPL")
    # Updated parser to include all required arguments
    parser.add_argument("--tenant", required=True, choices=VALID_TENANTS, help="Tenant ID (U1, U2, U3, U4)")
    parser.add_argument("--query", type=str, default=None, help="Single-turn query string.")
    parser.add_argument("--memory", choices=VALID_MEM_MODES, default='none', help="Memory mode for single-turn or initial mode for chat.")
    parser.add_argument("--chat", action="store_true", help="Run in interactive chat REPL mode.")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to configuration file.")

    args = parser.parse_args()
    
    if args.chat:
        # Chat REPL mode (multi-turn)
        run_chat_repl(args.tenant, args.memory, args.config)
    elif args.query is not None:
        # Single-turn mode
        run_single_turn(args.tenant, args.query, args.memory, args.config)
    else:
        print("Error: Must specify either --query (for single-turn) or --chat (for REPL).")
        sys.exit(1)

if __name__ == "__main__":
    main()