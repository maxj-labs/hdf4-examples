# hdf4-examples

A catalogue of small HDF4 files for testing HDF4 readers. Each file comes with:

- a SHA-256 checksum and its provenance,
- tags describing how it is stored (`hdf4:layouts`, `hdf4:coders`, ...), computed from the file,
- an answer key, `<file>.expected.json`, recording what the HDF4 C library reports for it:
  every scientific dataset's type, shape, dimensions, attributes, a hash of its decoded
  values and the byte ranges holding its stored bytes; Vdata tables; Vgroups; and
  HDF-EOS2 structure metadata.

A reader under test parses a file and compares its result with the answer key. It needs
no HDF4 C library to do so.

## What is in it

| Collection | Items | Source |
| --- | --- | --- |
| `synthetic` | 22 | Written by `tools/gen_synthetic.py`, one storage feature per file |
| `gdal` | 27 | GDAL's autotest files and the six real granules on its sample-data server |
| `opendap` | 13 | OPeNDAP BES DMR++ test files, with OPeNDAP's DMR++ description |
| `nasa-lpcloud`, `nasa-larc`, `nasa-nsidc`, `nasa-ghrc` | 24 | One small granule per selected NASA collection |

86 files, 64 MB of HDF4 data in total.

## Layout

```
catalog/v1/                 published metadata (in git)
  catalog.json              STAC 1.1 root
  items.json                flat list of every item, for test suites
  <collection>/collection.json
  <collection>/<id>/<id>.json             STAC item
  <collection>/<id>/<file>.expected.json  answer key
sources/                    what to fetch or generate, with pinned checksums
schemas/                    JSON Schema for the answer key and the hdf4 STAC extension
tools/                      generate, fetch, describe, build, publish
tests/                      catalogue checks
data/                       the HDF4 files themselves (not in git)
```

The HDF4 files are not stored in this repository. They are regenerated or downloaded
into `data/`, and published beside the metadata on Source Cooperative at
`s3://us-west-2.opendata.source.coop/pangeo/example-hdf4/v1/`.
**Nothing has been published there yet.**

## Using the catalogue from a test suite

Read `catalog/v1/items.json`. Each row has the item's collection and id, relative paths
to the data file and the answer key, the file's size and SHA-256, and its `hdf4:*` tags:

```json
{
  "collection": "synthetic",
  "id": "chunked-deflate-partial",
  "data": "synthetic/chunked-deflate-partial/chunked-deflate-partial.hdf",
  "expected": "synthetic/chunked-deflate-partial/chunked-deflate-partial.expected.json",
  "size": 7377,
  "sha256": "...",
  "hdf4:layouts": ["chunked"],
  "hdf4:coders": ["deflate"],
  "hdf4:features": ["fill_value", "partial_chunks"]
}
```

Select files by tag, fetch each, verify its checksum, parse it, and compare with the
answer key. `schemas/expected/v1.json` documents every field. The points most likely to
matter:

- `sds[].index` identifies a dataset. Names can repeat within a file.
- `values_sha256` hashes the whole decoded array, unwritten elements filled, in C order,
  little-endian, with no padding. Arrays of 64 elements or fewer are also given in `values`.
- `storage.ranges` lists the byte ranges of the stored (still encoded) bytes. A chunk split
  across the file has several entries with the same `chunk` index, in order. Ranges that
  sit back to back in the file are merged. A chunk with no entry was never written.
- `eos` and `descriptors` are derived by this repository's tools, not by the C library,
  and say so in a `derived_by` field.

## Rebuilding

Requires [uv](https://docs.astral.sh/uv/) on Linux (the tools call HDF4 functions through
the library bundled in the `pyhdf` wheel).

```bash
uv run tools/gen_synthetic.py                 # write data/synthetic/
uv run tools/fetch.py gdal opendap            # download, checking pinned checksums
EARTHDATA_TOKEN=... uv run tools/fetch.py nasa-lpcloud nasa-larc nasa-nsidc nasa-ghrc
uv run tools/describe.py data/*/*/*.hdf       # write the answer keys
uv run tools/build_catalog.py                 # write catalog/v1/
uv run pytest                                 # check everything
```

NASA downloads need an [Earthdata Login](https://urs.earthdata.nasa.gov) token in the
`EARTHDATA_TOKEN` environment variable. It is sent only to `*.nasa.gov` hosts and never
written to disk. In GitHub Actions it is read from the `EARTHDATA_TOKEN` repository secret.

To add a NASA collection, add a line to `sources/nasa-selection.txt` and run
`uv run tools/select_nasa.py`, which queries NASA's public metadata catalogue and picks a
small granule.

## Publishing

```bash
uv run --group publish tools/publish.py            # dry run
uv run --group publish tools/publish.py --confirm  # upload; needs AWS credentials
```

A published version is frozen: the script never deletes and refuses to replace a file
whose content differs. Corrections go in a new version prefix.

## How the answer keys were checked

- Byte ranges come from the C library's `SDgetdatainfo`. For the 12 OPeNDAP files that
  have a DMR++ description, they match OPeNDAP's independently generated ranges exactly.
- Every synthetic file regenerates byte for byte, and every answer key and tag set is
  recomputed and compared in the tests.

## Licences

This repository holds three kinds of content, under different terms:

| Content | Terms | File |
| --- | --- | --- |
| Code: `tools/`, `tests/`, `.github/` | Apache License 2.0 | `LICENSE` |
| Content generated by that code: the synthetic HDF4 files, the answer keys, the catalogue under `catalog/`, `schemas/`, `sources/` | CC0 1.0 Universal (public domain) | `LICENSE-GENERATED-DATA` |
| Files from GDAL, OPeNDAP and NASA, and OPeNDAP's DMR++ files under `catalog/v1/opendap/` | Their own terms, unchanged | `THIRD-PARTY.md` |

An answer key or STAC item that describes a third-party file is generated content, and
dedicating it to the public domain does not alter the terms of the file it describes.

In short, for the third-party files (details and links in `THIRD-PARTY.md`):

- **GDAL** states that its sample and test data files "are available as public and freely
  redistributable geodata".
- **NASA** items carry their collection's terms exactly as recorded in NASA's Common
  Metadata Repository (`cmr:terms`), with the DOI. Of the 24 collections, 16 link to
  NASA's data-use policy, 4 give a licence text, and 4 record nothing.
- **OPeNDAP** files come from the BES repository, whose `COPYING` file is the GNU LGPL
  version 3.
