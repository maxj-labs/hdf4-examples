"""Publish the catalogue and the HDF4 files to Source Cooperative.

    uv run --group publish tools/publish.py            # dry run: what would change
    uv run --group publish tools/publish.py --confirm  # upload; needs AWS credentials

Uploads ``catalog/v1/`` (metadata, from git) and the data files listed in
``catalog/v1/items.json`` (from ``data/``) to the same prefix, so every item's
relative ``./file.hdf`` link resolves. Also uploads ``catalog/README.md``, which
``build_catalog.py`` generates, to the product root, where Source Cooperative
shows it on the product page.

A published version is frozen. This script never deletes, and it refuses to
replace an object whose content differs unless ``--allow-overwrite`` is given.
Fix mistakes in a new version prefix instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "v1"
BUCKET = "us-west-2.opendata.source.coop"
REGION = "us-west-2"
PRODUCT = "pangeo/example-hdf4"
PREFIX = f"{PRODUCT}/{VERSION}"
# Shown on the product page. It sits above the version folders and describes the
# latest one, so unlike everything under a version it may be replaced.
README_KEY = "README.md"
CONTENT_TYPES = {".json": "application/json", ".hdf": "application/x-hdf", ".dmrpp": "application/xml"}


def local_files() -> dict[str, Path]:
    """Map each published key (relative to the version prefix) to its local file."""
    catalog = ROOT / "catalog" / VERSION
    files = {str(p.relative_to(catalog)): p for p in sorted(catalog.rglob("*")) if p.is_file()}
    missing = []
    for row in json.loads((catalog / "items.json").read_text()):
        path = ROOT / "data" / row["data"]
        if path.exists():
            files[row["data"]] = path
        else:
            missing.append(row["data"])
    if missing:
        raise SystemExit(
            f"{len(missing)} data file(s) are not in data/ (first: {missing[0]}). "
            "Run tools/fetch.py and tools/gen_synthetic.py first."
        )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--confirm", action="store_true", help="actually upload")
    parser.add_argument("--allow-overwrite", action="store_true")
    args = parser.parse_args()

    import obstore
    from obstore.store import S3Store

    files = local_files()
    config = {"AWS_REGION": REGION}
    if not args.confirm:
        config["AWS_SKIP_SIGNATURE"] = "true"  # a dry run only lists, anonymously
    store = S3Store(bucket=BUCKET, prefix=PREFIX, config=config)
    remote = {meta["path"]: meta["size"] for batch in obstore.list(store) for meta in batch}

    new, same, changed = [], [], []
    for key, path in files.items():
        if key not in remote:
            new.append(key)
        elif remote[key] == path.stat().st_size and bytes(obstore.get(store, key).bytes()) == path.read_bytes():
            same.append(key)
        else:
            changed.append(key)
    total = sum(files[k].stat().st_size for k in new + changed)
    print(f"s3://{BUCKET}/{PREFIX}/")
    print(f"  new: {len(new)}   unchanged: {len(same)}   differing: {len(changed)}   to upload: {total} bytes")
    for key in changed:
        print(f"  differs from the published copy: {key}")
    if changed and not args.allow_overwrite:
        print("Refusing to replace published files. Publish a new version, or pass --allow-overwrite.", file=sys.stderr)
        return 1
    if not args.confirm:
        print(f"  plus {README_KEY} at s3://{BUCKET}/{PRODUCT}/ (always replaced)")
        print("Dry run. Nothing was uploaded; pass --confirm to upload.")
        return 0
    readme = (ROOT / "catalog" / README_KEY).read_bytes()
    product = S3Store(bucket=BUCKET, prefix=PRODUCT, config=config)
    obstore.put(product, README_KEY, readme, attributes={"Content-Type": "text/markdown"})
    print(f"  uploaded {README_KEY} to the product root")
    for key in new + changed:
        path = files[key]
        content_type = CONTENT_TYPES.get(path.suffix, "application/octet-stream")
        obstore.put(store, key, path.read_bytes(), attributes={"Content-Type": content_type})
        print(f"  uploaded {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
