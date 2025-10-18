from __future__ import annotations
import os, csv, re, json
from dataclasses import dataclass
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import chromadb
# Import the embedding function for get_or_create_collection compatibility
from chromadb.utils import embedding_functions as ef

# --- DATACLASS: CRITICAL UPDATE to include PII metadata ---
@dataclass
class Hit:
    doc_id: str
    tenant: str
    visibility: str
    page: str
    text: str
    score: float
    pii: str = 'N'          # <-- ADDED: Raw PII flag (Y/N) from index
    pii_masked: bool = False # Used by the Policy Guard

# --- UTILITY FUNCTIONS (Retained from your starter) ---

def load_manifest(base_dir: str) -> list[dict]:
    """Loads the manifest.csv file."""
    mpath = os.path.join(base_dir, "data", "manifest.csv")
    with open(mpath, encoding="utf-8") as f:
        # Assuming manifest.csv includes 'tenant', 'doc_id', 'path', and 'pii' columns
        return list(csv.DictReader(f))

def read_doc(base_dir: str, rel_path: str) -> str:
    """Reads the content of a document file."""
    try:
        with open(os.path.join(base_dir, rel_path), encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not read document at path {rel_path}. Error: {e}")
        return ""

class Retriever:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        # Retaining your existing model initialization
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.client = chromadb.PersistentClient(path=os.path.join(base_dir, ".chroma"))
        self.manifest = load_manifest(base_dir)

    def _ns(self, tenant_id: str) -> str:
        """Helper to format the collection name (namespace)."""
        return f"tenant_{tenant_id}"
    
    def _get_ef(self):
        """Returns the SentenceTransformer embedding function for Chroma."""
        # Use the explicit embedding function with the model name
        return ef.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

    # --- REQUIRED FUNCTION 1: INDEX BUILDING (Updated for PII and Chunking) ---
    def build_or_update(self):
        print("Starting index build/update...")
        
        # 1. Group documents by tenant
        by_tenant = {}
        for row in self.manifest:
            by_tenant.setdefault(row["tenant"], []).append(row)
            
        # 2. Iterate through tenants and their documents
        for t, rows in by_tenant.items():
            
            is_public_tenant = (t == "PUB")
            # Map 'PUB' to 'public' namespace ID
            ns_id = t if not is_public_tenant else "public"
            # Get/Create the Chroma collection for this namespace
            coll = self.client.get_or_create_collection(name=self._ns(ns_id), embedding_function=self._get_ef())
            
            ids, docs, metas = [], [], []
            
            for r in rows:
                file_content = read_doc(self.base_dir, r["path"])
                if not file_content:
                    continue
                    
                # --- CHUNKING STRATEGY: Simple Paragraph Split ---
                chunks = [c.strip() for c in file_content.split('\n\n') if c.strip()]
                
                # --- METADATA EXTRACTION ---
                doc_id = r["doc_id"]
                # Tenant metadata should be 'U1..U4' or 'public'
                tenant_id_meta = t if not is_public_tenant else "public"
                # Visibility logic: public if PUB, otherwise private
                visibility = "public" if is_public_tenant else "private"
                # CRITICAL: Pull the PII flag from the manifest
                pii_flag = r.get("pii", "N") 
                
                # 3. Process chunks and append data for batch upsert
                for i, chunk_text in enumerate(chunks):
                    # Unique Chroma ID: doc_id + chunk_index
                    chunk_id = f"{doc_id}_{i}"
                    
                    ids.append(chunk_id)
                    docs.append(chunk_text)
                    metas.append({
                        "doc_id": doc_id, 
                        "tenant": tenant_id_meta, 
                        "visibility": visibility, 
                        "path": r["path"],
                        "pii": pii_flag, # <--- CRITICAL: PII METADATA INSERTED
                        "chunk_index": str(i) 
                    })
            
            if ids:
                coll.upsert(ids=ids, documents=docs, metadatas=metas)
                print(f"Indexed {len(ids)} chunks for tenant {t} into namespace {self._ns(ns_id)}")
        
        print("Index build/update finished.")


    # --- REQUIRED FUNCTION 2: SEARCH / RETRIEVAL (Updated for PII) ---
    def search(self, query: str, tenant_id: str, top_k: int = 6) -> List[Hit]:
        hits: list[Hit] = []
        
        def q(ns_id):
            coll = self.client.get_or_create_collection(self._ns(ns_id), embedding_function=self._get_ef())
            
            if coll.count() == 0: # Handle empty collections
                return

            res = coll.query(query_texts=[query], n_results=top_k)
            
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            
            for text, meta, dist in zip(docs, metas, dists):
                score = 1.0/(1.0+float(dist)) if dist is not None else 0.5
                
                # CRITICAL: Passing the 'pii' flag from metadata to the Hit object
                pii_flag = meta.get("pii", "N") 
                
                hits.append(Hit(
                    doc_id=meta["doc_id"], 
                    tenant=meta["tenant"], 
                    visibility=meta["visibility"], 
                    page=meta.get("chunk_index", "n/a"), 
                    text=text, 
                    score=score,
                    pii=pii_flag  # <--- CRITICAL
                ))
        
        # 1. Query private index
        q(tenant_id)
        # 2. Query public index
        q("public")
        
        # Final processing: sort by score and truncate to top_k
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]