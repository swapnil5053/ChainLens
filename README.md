# ChainLens

ChainLens is a document analysis tool for supply chain and logistics workflows. It enables structured querying of vendor contracts, SLAs, freight agreements, and shipping documentation using a retrieval-based pipeline.

The system is designed to return clause-level answers with page-level citations instead of relying on keyword search.

---

## Origin

ChainLens began as a fork of a general-purpose RAG chatbot template. The retrieval core was rebuilt into a modular pipeline, adding Maximal Marginal Relevance (MMR) retrieval for diverse clause coverage and persistent vector storage so documents are indexed once rather than re-embedded on each run. The system was refocused specifically on supply-chain and logistics documents such as vendor contracts, SLAs, and freight agreements.

---

## Overview

Operational constraints in supply chain contracts — delivery SLAs, penalty clauses, Incoterms, liability terms — are often distributed across long PDF documents. Finding a specific clause manually means reading the entire contract.

ChainLens indexes these documents locally and allows semantic querying against them. Responses are generated using only retrieved source material, so the model cannot hallucinate terms that aren't in the document.

Typical queries it handles:

- "What is the penalty if the vendor misses the 48-hour delivery SLA?"
- "Under what conditions does the force majeure clause apply to the ocean freight carrier?"
- "What are the DDP obligations for Southeast Asian suppliers?"

---

## System Architecture

```
PDF Documents
    ↓
Text Extraction (PyPDFLoader)
    ↓
Recursive Chunking (overlapping segments)
    ↓
Vector Embeddings (Gemini Embedding Model)
    ↓
ChromaDB Persistent Store
    ↓
MMR Retrieval (k=6, λ=0.5)
    ↓
Gemini 2.5 Flash (Context-Constrained Generation)
```

---

## Retrieval Strategy

The system uses Maximal Marginal Relevance (MMR) instead of plain similarity search. Standard similarity retrieval tends to return multiple chunks from the same section of a document. MMR penalises redundancy, pulling diverse segments from across the contract instead. This matters for long agreements where relevant clauses are spread across different sections.

Parameters: `k=6`, `lambda_mult=0.5`.

---

## Engineering Decisions

- **Persistent indexing**: The vector store is written to disk under `.vector_store`. Documents are not re-embedded on restart.
- **Batched embeddings**: Chunks are sent in groups of 100 per API call rather than individually. This reduces request volume by roughly 99% and keeps usage within the free-tier rate limit (15 RPM) for most uploads.
- **Timeout-protected model calls**: The generation step is wrapped with a timeout to prevent the Streamlit interface from hanging on slow responses.
- **Environment validation**: The application fails immediately on startup if `GOOGLE_API_KEY` is missing, rather than at query time.
- **Source metadata**: Every response includes the source PDF filename and page number of each retrieved chunk.

---

## Tech Stack

- LangChain (chain orchestration)
- ChromaDB (local vector storage)
- Google Gemini 2.5 Flash (embeddings + generation)
- Streamlit (interface)

---

## Setup

```bash
git clone https://github.com/swapnil5053/chainlens.git
cd chainlens
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.\.venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
```

Create a `.env` file in the root directory:

```env
GOOGLE_API_KEY=your_api_key_here
```

Get a key from [Google AI Studio](https://aistudio.google.com/) under **Get API Key**.

Run:

```bash
streamlit run app/app.py
```

Opens at `http://localhost:8501`.

---

## API Rate Limits

The Gemini free tier allows 15 requests per minute. The batched embedding client keeps most uploads within this limit, but uploading several large documents at once may still trigger a 429 error. If that happens, wait a minute and retry. Upgrading to the pay-as-you-go tier in Google AI Studio removes this constraint.

---
