# app/storage/elastic_client.py
from elasticsearch import Elasticsearch
from typing import Optional
import os

import os

def make_es():
    return Elasticsearch(
        os.getenv("ES_URL"),  # your cloud URL
        api_key=os.getenv("ES_API_KEY"),  # from Elastic Cloud console
    )
