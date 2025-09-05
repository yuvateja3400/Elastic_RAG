# app/storage/elastic_client.py
from elasticsearch import Elasticsearch
from typing import Optional
import os

def make_es() -> Elasticsearch:
    url = os.getenv("ELASTIC_URL", "http://localhost:9200")
    user = os.getenv("ELASTIC_USERNAME", "elastic")
    pwd = os.getenv("ELASTIC_PASSWORD", "changeme")

    es = Elasticsearch(url, basic_auth=(user, pwd), request_timeout=60)
    # ping raises on bad auth/URL
    if not es.ping():
        raise RuntimeError("Elasticsearch is not reachable at %s" % url)
    return es
