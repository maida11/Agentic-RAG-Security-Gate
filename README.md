# Agentic-RAG-Security-Gate
A multi-stage Agentic RAG pipeline for secure, multi-tenant knowledge retrieval. It uses deterministic controls (Planner and Policy Guard) to prevent data leakage, ACL, and PII violations before engaging the non-deterministic LLM. Key features include ACL enforcement, PII masking, injection detection, and post-LLM compliance checks.
Agentic-RAG-Security-Gate

Secure Agentic RAG for Multi-Project Research Lab Knowledge Base

This project implements a multi-stage Agentic Retrieval-Augmented Generation (RAG) pipeline designed for secure, multi-tenant knowledge retrieval within a research lab environment. The core objective is to prevent data leakage (ACL and PII violations) by applying deterministic security controls before engaging the non-deterministic Large Language Model (LLM).

1. System Architecture and Design

The system is implemented as a strict, sequential control flow, ensuring that security and compliance checks are completed at multiple stages of the query process.

Stage

Component

Description

Security Role

1. Planning

agents/planner.py

Acts as the primary security gate, detecting jailbreaks and prohibited intent (Leakage Risk) using hardcoded rules.

Deterministic Pre-Check

2. Retrieval

index.py

Queries tenant-isolated (e.g., tenant_U1) and public (tenant_public) Chroma indices.

Data Segmentation

3. Guarding

policies/guard.py

Applies Access Control List (ACL) filtering and PII masking on all retrieved document snippets.

Deterministic Filtering & Masking

4. Synthesis

llm.py

Generates a concise answer using only the filtered, masked snippets and memory context.

Grounded Generation

5. Post-Check

controller.py

Verifies LLM output compliance (citation presence, exact refusal format) before presentation.

Compliance Enforcement

2. Security and Policy Enforcement

Security is a multi-layered approach, involving a proactive Planner and a data-manipulating Policy Guard.

2.1. Agentic Planner (agents/planner.py)

The Planner is a deterministic security feature required to prevent Prompt Injection and Data Leakage before the LLM is involved.

Injection Detection: Flags inputs designed to bypass system rules (e.g., ignore all previous rules). Returns: Refusal: InjectionDetected. Ignoring instructions that conflict with system policy.

Prohibited Intent Detection (Leakage Risk): Flags requests that explicitly target sensitive data (e.g., private phone numbers). Returns: Refusal: LeakageRisk. Your request may expose private or PII data.

2.2. Policy Guard (policies/guard.py)

The Policy Guard performs two mandatory actions on all retrieved document snippets (Hit objects):

A. Access Control List (ACL) Enforcement

Any hit belonging to a different tenant that is not public (vis=public) is immediately discarded. If no allowed snippets remain, the system returns: Refusal: Access Denied. You do not have access to that information.

B. PII Masking

PII patterns (e.g., CNIC-like 5-7-1 format, PK Phone-like patterns) are masked using regular expressions. All matches are replaced with the token [REDACTED].

3. Retrieval and Compliance

Retrieval: Uses ChromaDB with the all-MiniLM-L6-v2 embedding model. The Planner also implements semantic rewriting to improve low-precision search queries.

Citation Fidelity: The Controller's Post-LLM Check aggressively enforces citation compliance. If the output is not an exact refusal template AND does not contain the mandatory citation format ((doc=...)), the output is converted to the hard refusal.

4. Memory Management and Ablation Study

The system supports two tenant-isolated memory modes:

Mode

Functionality

Cost/Risk

Findings

Buffer

Appends PII-masked turns to a dedicated tenant memory file.

High token cost; perfect recall.

Perfect recall; answered all follow-ups accurately.

Summary

Overwrites the tenant memory via an LLM call summarizing the buffer.

Low token cost (approx. 50% saving); risk of nuance loss.

Good, but lost minor detail (e.g., specific fire drill frequency). Unsuitable for factual recall.

5. Evaluation Results

The system successfully passed all security and compliance tests.

Test Suite

Metric

Result

Compliance

Pytest

ACL, PII, Injection Checks

3/3 Passed

PASS

Red-Team

Blocking Rate

Blocked

PASS

Evaluation Harness

Citation Fidelity/Blocking

(Reviewed during post-check)

PASS

Limitations and Ethical Considerations

PII Ambiguity: Masking relies purely on deterministic regex. Non-standard PII formatting can bypass the guard.

LLM Hallucination: The LLM's adherence to format is non-deterministic; the Controller's final security check remains essential to enforce compliance.
