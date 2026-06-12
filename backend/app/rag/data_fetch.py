"""
Example script to fetch data from MongoDB using tools.mongo_tool.
Defaults to database `vinsmartfuture` and reads MONGO_URI from .env.
Usage:
  python data_fetch.py --outdir data
  python data_fetch.py --collection <collection> --limit 50 --outdir data
  python data_fetch.py --fetch-all --outdir data
"""
import os
import json
import argparse
from dotenv import load_dotenv
from utils.logger import get_logger
from tools.mongo_tool import list_databases, list_collections, fetch_documents

# Load environment variables from .env
load_dotenv()

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Fetch data from MongoDB")
    parser.add_argument("--uri", type=str, help="MongoDB URI", default=None)
    parser.add_argument("--db", type=str, help="Database name", default="VinSmartFuture")
    parser.add_argument("--collection", type=str, help="Collection name", default="Users")
    parser.add_argument("--limit", type=int, help="Max documents to fetch per collection", default=3000)
    parser.add_argument("--fetch-all", action="store_true", help="Fetch all documents from each collection")
    parser.add_argument("--outdir", type=str, help="Output directory to save results", default=None)
    args = parser.parse_args()

    uri = args.uri or os.getenv("MONGO_URI")
    if not uri:
        print("MONGO_URI not provided. Pass --uri or set MONGO_URI in environment (see .env.example).")
        return

    try:
        # Ensure outdir exists
        outdir = args.outdir or "data"
        import pathlib
        pathlib.Path(outdir).mkdir(parents=True, exist_ok=True)

        print("Listing databases...")
        dbs = list_databases(uri)
        print(json.dumps(dbs, ensure_ascii=False, indent=2))
        # Save databases list
        with open(pathlib.Path(outdir) / "databases.json", "w", encoding="utf-8") as f:
            json.dump(dbs, f, ensure_ascii=False, indent=2)

        if args.db:
            print(f"\nListing collections for database: {args.db}")
            cols = list_collections(args.db, uri)
            print(json.dumps(cols, ensure_ascii=False, indent=2))
            # Save collections list
            with open(pathlib.Path(outdir) / f"{args.db}_collections.json", "w", encoding="utf-8") as f:
                json.dump(cols, f, ensure_ascii=False, indent=2)

            def normalize(d):
                from bson import ObjectId
                for k, v in list(d.items()):
                    if isinstance(v, ObjectId):
                        d[k] = str(v)
                    elif isinstance(v, dict):
                        d[k] = normalize(v)
                return d

            if args.collection:
                collections_to_fetch = [args.collection]
            else:
                collections_to_fetch = cols

            fetch_limit = None if args.fetch_all else args.limit
            for collection_name in collections_to_fetch:
                print(f"\nFetching documents from {args.db}.{collection_name} "
                      f"({'all' if fetch_limit is None else f'limit={fetch_limit}'})")
                docs = fetch_documents(args.db, collection_name, limit=fetch_limit or 0, uri=uri)
                if fetch_limit is None:
                    docs = [normalize(dict(d)) for d in docs]
                else:
                    docs = [normalize(dict(d)) for d in docs]
                print(json.dumps(docs, ensure_ascii=False, indent=2))
                filename = f"{args.db}_{collection_name}.json"
                with open(pathlib.Path(outdir) / filename, "w", encoding="utf-8") as f:
                    json.dump(docs, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}")
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
