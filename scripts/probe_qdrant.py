"""R-01 probe: does qdrant-client in-memory (local) mode support server-side
hybrid retrieval — dense + sparse prefetch with RRF/DBSF fusion — and payload
filtering on the fused query?

If yes: the hermetic E2E test can use `:memory:` and we need no fallback.
If no:  we must implement InProcessRRF and test both paths.
"""

import random
import sys
from importlib.metadata import version

from qdrant_client import QdrantClient, models

random.seed(7)
DIM = 8
COLL = "policy_chunks"

print(f"qdrant-client version: {version('qdrant-client')}")
print("-" * 60)

client = QdrantClient(":memory:")

# Named dense vector + named sparse vector in ONE collection.
client.create_collection(
    collection_name=COLL,
    vectors_config={"dense": models.VectorParams(size=DIM, distance=models.Distance.COSINE)},
    sparse_vectors_config={"bm25": models.SparseVectorParams()},
)
print("[ok] collection created with named dense + sparse vectors")

docs = [
    ("ALM-CRIT-003", "4.3.1", "criteria", "ALL"),
    ("ALM-CRIT-003", "4.3.2", "criteria", "ALL"),
    ("SITE-POL-007", "2.1", "policy", "NorthPlant"),
    ("SITE-POL-008", "2.1", "policy", "EastRefinery"),
    ("SOP-BFP-014", "6.2", "procedure", "NorthPlant"),
    ("SEC-TEST-999", "1.0", "quarantined", "ALL"),
]

points = []
for i, (doc_id, clause, dtype, scope) in enumerate(docs):
    points.append(
        models.PointStruct(
            id=i,
            vector={
                "dense": [random.random() for _ in range(DIM)],
                "bm25": models.SparseVector(
                    indices=[i, i + 10, i + 20],
                    values=[0.9, 0.6, 0.3],
                ),
            },
            payload={
                "doc_id": doc_id,
                "clause_id": clause,
                "doc_type": dtype,
                "site_scope": scope,
                "injection_flag": doc_id == "SEC-TEST-999",
            },
        )
    )
client.upsert(collection_name=COLL, points=points)
print(f"[ok] upserted {len(points)} points")

# Payload index for filtered retrieval
for field in ("doc_type", "site_scope"):
    client.create_payload_index(
        collection_name=COLL, field_name=field, field_schema=models.PayloadSchemaType.KEYWORD
    )
client.create_payload_index(
    collection_name=COLL, field_name="injection_flag", field_schema=models.PayloadSchemaType.BOOL
)
print("[ok] payload indexes created")
print("-" * 60)

q_dense = [random.random() for _ in range(DIM)]
q_sparse = models.SparseVector(indices=[0, 2, 10, 22], values=[0.8, 0.5, 0.4, 0.2])

results = {}

# --- TEST 1: server-side RRF fusion over dense + sparse prefetch ---------
try:
    r = client.query_points(
        collection_name=COLL,
        prefetch=[
            models.Prefetch(query=q_dense, using="dense", limit=5),
            models.Prefetch(query=q_sparse, using="bm25", limit=5),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=3,
        with_payload=True,
    )
    hits = [(p.id, round(p.score, 4), p.payload["doc_id"]) for p in r.points]
    print(f"[PASS] RRF fusion -> {hits}")
    results["rrf"] = True
except Exception as e:
    print(f"[FAIL] RRF fusion -> {type(e).__name__}: {e}")
    results["rrf"] = False

# --- TEST 2: DBSF fusion (alternative) -----------------------------------
try:
    r = client.query_points(
        collection_name=COLL,
        prefetch=[
            models.Prefetch(query=q_dense, using="dense", limit=5),
            models.Prefetch(query=q_sparse, using="bm25", limit=5),
        ],
        query=models.FusionQuery(fusion=models.Fusion.DBSF),
        limit=3,
    )
    print(f"[PASS] DBSF fusion -> {len(r.points)} hits")
    results["dbsf"] = True
except Exception as e:
    print(f"[FAIL] DBSF fusion -> {type(e).__name__}: {e}")
    results["dbsf"] = False

# --- TEST 3: fusion + payload filter (the real retrieval shape) ----------
try:
    flt = models.Filter(
        must=[
            models.FieldCondition(key="injection_flag", match=models.MatchValue(value=False)),
            models.FieldCondition(
                key="site_scope", match=models.MatchAny(any=["NorthPlant", "ALL"])
            ),
        ]
    )
    r = client.query_points(
        collection_name=COLL,
        prefetch=[
            models.Prefetch(query=q_dense, using="dense", limit=10, filter=flt),
            models.Prefetch(query=q_sparse, using="bm25", limit=10, filter=flt),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=5,
        with_payload=True,
    )
    scopes = {p.payload["site_scope"] for p in r.points}
    docs_out = [p.payload["doc_id"] for p in r.points]
    leaked_east = "EastRefinery" in scopes
    leaked_poison = "SEC-TEST-999" in docs_out
    print(f"[PASS] filtered RRF -> {docs_out}")
    print(f"       EastRefinery leaked: {leaked_east} | poisoned doc leaked: {leaked_poison}")
    results["filtered"] = not leaked_east and not leaked_poison
except Exception as e:
    print(f"[FAIL] filtered RRF -> {type(e).__name__}: {e}")
    results["filtered"] = False

# --- TEST 4: on-disk local mode (path=) — used by rag-ingest offline -----
try:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        c2 = QdrantClient(path=td)
        c2.create_collection(
            collection_name=COLL,
            vectors_config={
                "dense": models.VectorParams(size=DIM, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={"bm25": models.SparseVectorParams()},
        )
        c2.upsert(collection_name=COLL, points=points[:3])
        r = c2.query_points(
            collection_name=COLL,
            prefetch=[
                models.Prefetch(query=q_dense, using="dense", limit=3),
                models.Prefetch(query=q_sparse, using="bm25", limit=3),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=2,
        )
        c2.close()
    print(f"[PASS] on-disk local mode RRF -> {len(r.points)} hits")
    results["ondisk"] = True
except Exception as e:
    print(f"[FAIL] on-disk local mode -> {type(e).__name__}: {e}")
    results["ondisk"] = False

print("-" * 60)
print("VERDICT:", "ALL PASS — no fallback needed" if all(results.values()) else f"GAPS: {results}")
sys.exit(0 if all(results.values()) else 1)
