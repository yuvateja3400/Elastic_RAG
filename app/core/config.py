import os

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_USERNAME = os.getenv("ELASTIC_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ELASTIC_PASSWORD", "yuvateja")
ES_INDEX   = os.getenv("ES_INDEX", "rag_documents_v1")  # <-- lowercase
ELSER_MODEL_ID = os.getenv("ELSER_MODEL_ID", ".elser_model_2")
