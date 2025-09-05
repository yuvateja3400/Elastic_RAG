import os
from functools import lru_cache
from elasticsearch import Elasticsearch

# Auto-load .env so CLI runs and PyCharm runs both get creds
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

@lru_cache(maxsize=1)
def get_es() -> Elasticsearch:
    url = os.getenv("ELASTIC_URL", "http://localhost:9200")

    # Prefer API key if provided (works great with GitHub push protection)
    api_key = os.getenv("ELASTIC_API_KEY")
    if api_key:
        return Elasticsearch(
            url,
            api_key=api_key,
            request_timeout=60,
            retry_on_timeout=True,
        )

    # Fallback to basic auth
    user = os.getenv("ELASTIC_USERNAME")
    pwd  = os.getenv("ELASTIC_PASSWORD")
    return Elasticsearch(
        url,
        basic_auth=(user, pwd) if user and pwd else None,
        request_timeout=60,
        retry_on_timeout=True,
    )
