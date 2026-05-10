# SHL Assessment Recommendation Agent

A FastAPI-based conversational agent that recommends SHL Individual Test Solutions from a grounded catalog index. Instead of requiring users to know exact assessment names or catalog terminology, the agent accepts natural hiring intent, asks clarifying questions when needed, retrieves relevant SHL products, and returns a structured shortlist.

Example user request:

```text
We are hiring graduate financial analysts.
```

The agent turns this into a catalog-grounded recommendation workflow: clarify the role if the request is vague, retrieve matching SHL assessments, rerank candidates, and respond only with assessments that exist in the indexed SHL catalog.

## Problem Context

Hiring managers often start with an imprecise need such as "I need a Java developer assessment" or "We are hiring analysts." Traditional catalog search assumes the user already knows the right keywords, filters, or assessment names. This project solves that by exposing a conversational recommendation API that can:

- clarify vague hiring requests before recommending anything;
- recommend 1 to 10 SHL assessments when enough context is available;
- refine recommendations when the user changes requirements mid-conversation;
- compare assessments using retrieved catalog facts;
- refuse off-topic, legal, unsupported, or prompt-injection requests;
- return only SHL catalog URLs from the indexed Individual Test Solutions catalog.

The implementation is designed for the SHL Labs conversational assessment recommendation assignment.

## What The Agent Does

The API is stateless. Each `/chat` request includes the full conversation history, and the service returns the next assistant reply plus a structured recommendation list when appropriate.

Supported behaviors:

| Behavior | Example | Expected Handling |
| --- | --- | --- |
| Clarification | "I need an assessment." | Ask for role, seniority, skills, or hiring context before recommending. |
| Recommendation | "Hiring graduate financial analysts." | Return a grounded shortlist of relevant SHL assessments. |
| Refinement | "Actually, add personality tests." | Update the shortlist using the prior conversation context. |
| Comparison | "What is the difference between OPQ and GSA?" | Compare only using catalog-retrieved information. |
| Refusal | "Write my hiring policy." | Politely refuse because it is outside SHL assessment selection. |

## Architecture

```text
User conversation
    |
    v
LLM query optimizer
    |
    v
Hybrid retriever
    |-- semantic search with ChromaDB
    |-- lexical search with BM25
    v
Reranker
    |
    v
Grounded SHL catalog context
    |
    v
LLM recommendation agent
    |
    v
Structured JSON API response
```

### Retrieval Flow

1. The full conversation is compressed into an optimized retrieval query.
2. The retriever searches the SHL catalog with both semantic and lexical methods.
3. Candidate assessments are reranked for role fit, skill match, and screening relevance.
4. The top catalog records are passed to the LLM as the only allowed evidence.
5. The final response is parsed into the API schema and catalog names are mapped back to official URLs.

This design keeps the model useful conversationally while reducing hallucinated assessment names and unsupported URLs.

## Tech Stack

| Layer | Technology |
| --- | --- |
| API | FastAPI |
| Data validation | Pydantic |
| LLM provider | Groq |
| Embeddings | Sentence Transformers |
| Vector search | ChromaDB |
| Lexical search | rank-bm25 |
| Reranking | Custom scoring heuristics |
| Deployment | Docker, Render-compatible |

## Project Structure

```text
.
├── app/
│   ├── api/
│   │   └── routes.py              # FastAPI route definitions
│   ├── core/
│   │   └── config.py              # Environment and runtime settings
│   ├── models/
│   │   ├── catalog.py             # SHL catalog item model
│   │   └── schemas.py             # Request and response schemas
│   ├── prompts/
│   │   └── prompts.py             # System and query-optimization prompts
│   ├── services/
│   │   ├── agent.py               # Main conversation orchestration
│   │   ├── bm25_store.py          # Lexical retrieval store
│   │   ├── catalog_loader.py      # Catalog loading
│   │   ├── embeddings.py          # Embedding model wrapper
│   │   ├── llm.py                 # Groq LLM client
│   │   ├── reranker.py            # Candidate reranking
│   │   ├── retrieval.py           # Hybrid retrieval
│   │   └── vector_store.py        # ChromaDB integration
│   └── main.py                    # Application startup and dependency wiring
├── data/
│   ├── shl_catalog.json           # Indexed SHL Individual Test Solutions data
│   └── chroma/                    # Persisted vector index
├── scripts/
│   └── build_indexes.py           # Rebuilds the vector index from catalog data
├── Dockerfile
├── requirements.txt
└── README.md
```

## API Contract

### `GET /health`

Readiness endpoint for deployment checks.

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

### `POST /chat`

Stateless chat endpoint. Send the full conversation history on every call.

```http
POST /chat
Content-Type: application/json
```

Request:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "We are hiring graduate financial analysts."
    }
  ]
}
```

Response:

```json
{
  "reply": "For graduate financial analysts, I would prioritize numerical reasoning, finance-related judgment, and workplace decision-making.\n\nRecommended assessments:\n- SHL Verify Interactive - Numerical Reasoning",
  "recommendations": [
    {
      "name": "SHL Verify Interactive - Numerical Reasoning",
      "url": "https://www.shl.com/...",
      "test_type": "Ability & Aptitude",
      "duration": "20 minutes",
      "languages": "English"
    }
  ],
  "end_of_conversation": false
}
```

Response fields:

| Field | Type | Description |
| --- | --- | --- |
| `reply` | string | Natural-language assistant response. |
| `recommendations` | array | Structured shortlist. Empty when clarification or refusal is needed. |
| `recommendations[].name` | string | Assessment name from the SHL catalog. |
| `recommendations[].url` | string | Official catalog URL from the indexed data. |
| `recommendations[].test_type` | string | Catalog category or assessment type. |
| `recommendations[].duration` | string | Catalog duration when available. |
| `recommendations[].languages` | string | Supported languages from the catalog. |
| `end_of_conversation` | boolean | Indicates whether the conversation can be considered complete. |

## Local Development

### 1. Create environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file:

```text
GROQ_API_KEY=your_groq_api_key
```

Optional settings are defined in `app/core/config.py`, including model name, catalog path, Chroma path, retrieval-mode flags, and top-k retrieval limits.

By default, local development can download the embedding model if it is not already cached. The default embedding model is `sentence-transformers/all-MiniLM-L6-v2`, which is lighter and faster than `all-mpnet-base-v2` for deployment on smaller CPUs. The Docker image pre-downloads the embedding model, builds the Chroma index during image build, and then runs with `EMBED_LOCAL_FILES_ONLY=true`. This avoids model downloads and index rebuilding during Render startup.

### 3. Build or refresh indexes

The repository includes catalog data and a persisted Chroma index. If the catalog changes, rebuild the vector index:

```bash
PYTHONPATH=. python scripts/build_indexes.py
```

To run lexical-only retrieval without vector embeddings, set:

```text
ENABLE_SEMANTIC_RETRIEVAL=false
```

This keeps BM25 retrieval enabled and is useful for isolating semantic-search latency in production.

### 4. Run the API

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

### 5. Smoke test

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "We are hiring graduate financial analysts."
      }
    ]
  }'
```

## Docker

Build the image:

```bash
docker build -t shl-assessment-agent .
```

Run the container:

```bash
docker run --env-file .env -p 10000:10000 shl-assessment-agent
```

The container exposes:

```text
http://localhost:10000
```

## Render Deployment

This project is Docker-ready and can be deployed as a Render web service.

Recommended Render settings:

| Setting | Value |
| --- | --- |
| Environment | Docker |
| Port | `10000` |
| Health check path | `/health` |
| Required environment variable | `GROQ_API_KEY` |

The Docker build caches the Sentence Transformers embedding model and builds the Chroma index in the image, so the deployed service does not depend on a runtime model download or index build before `/health` becomes available.

After deployment, verify:

```text
GET https://your-render-service.onrender.com/health
POST https://your-render-service.onrender.com/chat
```

## Design Decisions

### Stateless API

The evaluator sends the complete conversation history on every request, so the service does not store per-user session state. This makes the API easier to scale and keeps behavior deterministic from the supplied messages.

### Hybrid Retrieval

Pure vector search is useful for semantic matching but can miss exact catalog terminology. BM25 is strong for exact terms but weaker for vague role descriptions. Combining both improves recall across natural language requests, job-description snippets, assessment names, and follow-up refinements.

### Query Optimization

Raw conversation history can contain irrelevant turns, confirmations, or corrections. The query optimizer converts the conversation into a compact retrieval query that emphasizes role, seniority, skills, constraints, and implied competencies.

### Catalog Grounding

The LLM receives retrieved catalog records as its evidence source. Final recommendations are filtered through retrieved catalog items before they are returned, which helps ensure assessment names and URLs come from the SHL catalog snapshot.

## Evaluation Alignment

The implementation is built around the assignment scoring criteria:

- schema-compliant responses from `/chat`;
- recommendations limited to indexed catalog items;
- no recommendation on vague first turns;
- support for refinement and comparison;
- refusal for off-topic or unsupported requests;
- top-10 recommendation quality for Recall@10 evaluation;
- no server-side conversation state.

## Limitations

- Recommendations are limited to the local SHL catalog snapshot in `data/shl_catalog.json`.
- Retrieval quality depends on catalog coverage and embedding quality.
- Free-tier deployments may have cold-start latency.
- The current reranker is heuristic-based rather than a trained cross-encoder.

## Future Improvements

- Add cross-encoder reranking for stronger final ordering.
- Improve catalog refresh automation.
- Add response streaming for the chat endpoint.
- Add a lightweight frontend for manual testing.
- Add multilingual retrieval expansion for non-English hiring requests.

## License

Built for the SHL Labs conversational assessment recommendation assignment.
