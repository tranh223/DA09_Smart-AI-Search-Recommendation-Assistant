from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from pymongo.read_preferences import ReadPreference
load_dotenv()

DEFAULT_DB = "VinSmartFuture"
DEFAULT_COLLECTION = "Users"
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / "data" / ".env"
URI_ENV_NAMES = (
    "MONGODB_URI",
    "MONGO_URI",
    "MONGODB_CONNECTION_STRING",
    "MONGODB_API_KEY",
)
READ_PREFERENCES = {
    "primary": ReadPreference.PRIMARY,
    "secondaryPreferred": ReadPreference.SECONDARY_PREFERRED,
}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_mongodb_uri() -> tuple[str, str]:
    for env_name in URI_ENV_NAMES:
        value = os.environ.get(env_name)
        if value:
            if not value.startswith(("mongodb://", "mongodb+srv://")):
                raise ValueError(
                    f"{env_name} is set, but it does not look like a MongoDB connection URI."
                )
            return env_name, value

    expected = ", ".join(URI_ENV_NAMES)
    raise ValueError(f"No MongoDB connection URI found. Expected one of: {expected}.")


def summarize_document(document: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "_id": str(document.get("_id")),
        "top_level_keys": sorted(document.keys()),
    }

    for key in ("user_id", "name", "email"):
        if key in document:
            summary[key] = document[key]

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test MongoDB connectivity and read access for a collection."
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--sample-size", type=int, default=3)
    parser.add_argument(
        "--read-preference",
        choices=sorted(READ_PREFERENCES),
        default="secondaryPreferred",
        help="Use primary when you specifically need to verify write-ready primary access.",
    )
    args = parser.parse_args()

    load_env_file(args.env_file)

    try:
        env_name, uri = get_mongodb_uri()
        read_preference = READ_PREFERENCES[args.read_preference]
        client = MongoClient(
            uri,
            read_preference=read_preference,
            serverSelectionTimeoutMS=5000,
        )
        client.get_database("admin", read_preference=read_preference).command(
            "ping",
            read_preference=read_preference,
        )

        collection = client.get_database(args.db, read_preference=read_preference)[
            args.collection
        ]
        total_documents = collection.count_documents({})
        sample_documents = list(collection.find({}).limit(max(args.sample_size, 0)))

        print("MongoDB connection OK")
        print(f"URI source env: {env_name}")
        print(f"Read preference: {args.read_preference}")
        print(f"Database: {args.db}")
        print(f"Collection: {args.collection}")
        print(f"Document count: {total_documents}")

        if sample_documents:
            print("Sample documents:")
            for index, document in enumerate(sample_documents, start=1):
                print(f"  {index}. {summarize_document(document)}")
        else:
            print("Sample documents: none")

        client.close()
        return 0
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except ServerSelectionTimeoutError as exc:
        print(f"MongoDB server selection failed: {exc}", file=sys.stderr)
        return 3
    except PyMongoError as exc:
        print(f"MongoDB operation failed: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
