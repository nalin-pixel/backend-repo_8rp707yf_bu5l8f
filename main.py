import os
import time
import hashlib
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, conint

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MineRequest(BaseModel):
    data: str = Field("Hello, Bitcoin!", description="Arbitrary data to include in the block header")
    difficulty: conint(ge=1, le=7) = Field(4, description="Number of leading zeros required in hex form (max 7 to be safe here)")
    start_nonce: int = Field(0, description="Nonce value to start searching from")
    max_hashes: int = Field(200000, description="Safety cap on the number of hashes to try in one request")
    time_limit_ms: int = Field(1500, description="Max time to spend hashing in this request (milliseconds)")


class MineResult(BaseModel):
    found: bool
    nonce: Optional[int] = None
    hash_hex: Optional[str] = None
    tried_hashes: int
    elapsed_ms: int
    target_prefix: str


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db  # type: ignore
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:  # pragma: no cover - best-effort
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


@app.post("/api/mine", response_model=MineResult)
def mine(req: MineRequest):
    """
    Educational proof-of-work miner.
    This does NOT mine real Bitcoin. It simply searches for a nonce
    such that sha256(data + nonce) has a hex prefix of N zeros.
    Safety caps are applied to prevent resource abuse.
    """
    if req.max_hashes > 1_000_000:
        # Hard cap to protect environment
        raise HTTPException(status_code=400, detail="max_hashes too large; must be <= 1,000,000")

    target_prefix = "0" * int(req.difficulty)
    start = time.perf_counter()

    tried = 0
    nonce = req.start_nonce
    deadline = start + (req.time_limit_ms / 1000.0)

    found_hash = None
    found_nonce = None

    while tried < req.max_hashes and time.perf_counter() < deadline:
        payload = f"{req.data}|{nonce}".encode()
        digest = hashlib.sha256(payload).hexdigest()
        tried += 1
        if digest.startswith(target_prefix):
            found_hash = digest
            found_nonce = nonce
            break
        nonce += 1

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    return MineResult(
        found=found_nonce is not None,
        nonce=found_nonce,
        hash_hex=found_hash,
        tried_hashes=tried,
        elapsed_ms=elapsed_ms,
        target_prefix=target_prefix,
    )


@app.post("/api/hash")
def simple_hash(data: str):
    """Return sha256 hex of the provided data for demo purposes."""
    return {"data": data, "sha256": hashlib.sha256(data.encode()).hexdigest()}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
