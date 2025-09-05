import os
from functools import lru_cache
from elasticsearch import Elasticsearch

@lru_cache(maxsize=1)
def get_es() -> Elasticsearch:
    url = os.getenv("ELASTIC_URL", "http://localhost:9200")
    user = os.getenv("ELASTIC_USERNAME")
    pwd  = os.getenv("ELASTIC_PASSWORD")
    return Elasticsearch(
        url,
        basic_auth=(user, pwd) if user and pwd else None,
        request_timeout=60,
        retry_on_timeout=True,
    )
