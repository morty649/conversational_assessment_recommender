shl-conversational-assessment-recommender-agent/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   └── routes.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   └── logging.py
│   │
│   ├── models/
│   │   ├── schemas.py
│   │   └── catalog.py
│   │
│   ├── prompts/
│   │   └── prompts.py
│   │
│   ├── services/
│   │   ├── catalog_loader.py
│   │   ├── embeddings.py
│   │   ├── vector_store.py
│   │   ├── bm25_store.py
│   │   ├── retrieval.py
│   │   ├── reranker.py
│   │   ├── llm.py
│   │   ├── guardrails.py
│   │   └── agent.py
│   │
│   └── utils/
│       └── text.py
│
├── scripts/
│   ├── build_indexes.py
│   └── smoke_test.py
│
├── data/
│   ├── shl_catalog.json
│   ├── chroma/
│   └── bm25.pkl
│
├── requirements.txt
├── Dockerfile
├── .env
└── README.md


Ran PYTHONPATH=. python scripts/build_indexes.py

