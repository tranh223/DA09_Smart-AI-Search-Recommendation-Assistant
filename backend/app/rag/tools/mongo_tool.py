"""
MongoDB utility wrapper using pymongo.
Provides simple helpers to list databases, collections, and fetch documents.
"""
from typing import List, Dict, Any, Optional
import os

from pymongo import MongoClient
import certifi
import os
from pymongo.collection import Collection
from utils.logger import get_logger

logger = get_logger(__name__)


def get_client(uri: Optional[str] = None, tls_allow_invalid: Optional[bool] = None) -> MongoClient:
    """Return a MongoClient connected to `uri` or the MONGO_URI env var.

    Uses certifi CA bundle by default to avoid SSL handshake issues with Atlas.
    Set environment variable `MONGO_TLS_ALLOW_INVALID=true` to disable cert verification (for testing only).
    """
    uri = uri or os.getenv("MONGO_URI")
    if not uri:
        raise ValueError("MONGO_URI is not set. Provide a URI or set MONGO_URI in environment.")

    # Determine tls allow invalid option (explicit arg > env)
    if tls_allow_invalid is None:
        tls_env = os.getenv("MONGO_TLS_ALLOW_INVALID", "false").lower().strip().strip('"\'')
        tls_allow_invalid = tls_env in ("1", "true", "yes")
        logger.info(f"MONGO_TLS_ALLOW_INVALID env: {tls_env} -> {tls_allow_invalid}")

    try:
        if tls_allow_invalid:
            # Insecure: skip CA verification (only for testing)
            logger.info("Connecting with tlsAllowInvalidCertificates=True (insecure, testing only)")
            client = MongoClient(uri, tls=True, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=20000, connectTimeoutMS=20000)
        else:
            # Use certifi CA bundle for trusted certs
            logger.info(f"Connecting with certifi CA bundle")
            ca_file = certifi.where()
            client = MongoClient(uri, tls=True, tlsCAFile=ca_file, serverSelectionTimeoutMS=20000, connectTimeoutMS=20000)

        # Try a quick server_info ping to trigger early errors
        logger.info("Testing connection with ping...")
        client.admin.command('ping')
        logger.info("Connection successful!")
        return client

    except Exception as e:
        logger.warning(f"MongoClient initial connection failed: {e}. Retrying with basic MongoClient...")
        # Fallback to a plain client (may still fail)
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=30000)
            client.admin.command('ping')
            logger.info("Fallback connection successful!")
            return client
        except Exception as e2:
            logger.error(f"Fallback connection also failed: {e2}")
            raise


def list_databases(uri: Optional[str] = None) -> List[str]:
    """List database names."""
    client = get_client(uri)
    dbs = client.list_database_names()
    logger.info(f"Found databases: {dbs}")
    return dbs


def list_collections(db_name: str, uri: Optional[str] = None) -> List[str]:
    """List collections in a database."""
    client = get_client(uri)
    cols = client[db_name].list_collection_names()
    logger.info(f"Collections in {db_name}: {cols}")
    return cols


def fetch_documents(db_name: str, collection_name: str, filter: Optional[Dict[str, Any]] = None, limit: int = 100, uri: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch documents from a collection.

    Args:
        db_name: database name
        collection_name: collection name
        filter: mongo filter dict
        limit: max documents to return
        uri: optional mongo uri
    """
    client = get_client(uri)
    coll: Collection = client[db_name][collection_name]
    cursor = coll.find(filter or {}).limit(limit)
    docs = list(cursor)
    logger.info(f"Fetched {len(docs)} documents from {db_name}.{collection_name}")
    return docs
