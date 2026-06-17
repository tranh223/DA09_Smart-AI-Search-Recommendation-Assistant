from enum import StrEnum


class SearchSource(StrEnum):
    RAG_VECTOR_DB = "RAG_VECTOR_DB"
    HOTEL_EMBEDDING_DB = "HOTEL_EMBEDDING_DB"
    UNIFIED_GRAPH = "UNIFIED_GRAPH"
