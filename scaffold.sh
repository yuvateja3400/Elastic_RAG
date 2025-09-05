#!/bin/bash



# Top-level files
touch README.md LICENSE .gitignore .env.example

# Docs
mkdir -p docs/screenshots
touch docs/architecture.md docs/functional_requirements.md docs/evaluation.md

# Infra
mkdir -p infra/elastic/index_templates infra/elastic/pipelines
touch infra/docker-compose.yml infra/elastic/elasticsearch.yml

# App structure
mkdir -p app/{api/{routers,schemas,services},ingestion,retrieval,llm,storage,ui,utils}
touch app/__init__.py

# API
touch app/api/__init__.py
touch app/api/routers/{__init__.py,health.py,ingest.py,query.py}
touch app/api/schemas/{__init__.py,common.py}
touch app/api/services/{__init__.py,ingestion_service.py,query_service.py}

# Ingestion
touch app/ingestion/{__init__.py,google_drive_client.py,pdf_extractor.py,chunker.py,ingestion_pipeline.py,models.py}

# Retrieval
touch app/retrieval/{__init__.py,bm25.py,elser.py,dense.py,rrf.py,types.py}

# LLM
touch app/llm/{__init__.py,hf_client.py,prompts.py,guardrails.py}

# Storage
touch app/storage/{__init__.py,elastic_client.py,index_mapping.py}

# UI
touch app/ui/streamlit_app.py

# Utils
touch app/utils/{__init__.py,settings.py,logging.py,text.py}

# Scripts
mkdir -p scripts
touch scripts/{bootstrap_elastic.sh,ingest_drive_folder.py}

# Tests
mkdir -p tests
touch tests/{__init__.py,test_ingestion.py,test_retrieval.py,test_answering.py}

echo "Project scaffold created successfully!"
