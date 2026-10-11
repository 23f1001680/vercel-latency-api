from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import json
import os

app = FastAPI()

# Wide-open CORS configuration matching the discussion board solutions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Access-Control-Allow-Origin"],
)

class LatencyRequest(BaseModel):
    regions: List[str]
    threshold_ms: int

def calc_p95(values):
    if not values: return 0.0
    s = sorted(values)
    k = (len(s) - 1) * 0.95
    f = int(k)
    c = f + 1
    if f == c or c >= len(s): return float(s[f])
    return float(s[f] * (c - k) + s[c] * (k - f))

# We add multiple route variations here so Vercel can't miss it, even if it strips the path!
@app.post("/api/latency")
@app.post("/latency")
@app.post("/")
async def get_latency(req: LatencyRequest):
    
    # Foolproof way to find the JSON file regardless of how Vercel packages the directory
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "q-vercel-latency.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "q-vercel-latency.json"),
        "q-vercel-latency.json",
        "api/q-vercel-latency.json"
    ]
    
    file_path = None
    for p in possible_paths:
        if os.path.exists(p):
            file_path = p
            break
            
    if not file_path:
        return {"error": "JSON file missing. Make sure q-vercel-latency.json is uploaded to GitHub."}
        
    with open(file_path, "r") as f:
        data = json.load(f)

    results = {}
    for reg in req.regions:
        if isinstance(data, dict):
            reg_data = data.get(reg, [])
        else:
            reg_data = [d for d in data if d.get("region") == reg]
            
        if not reg_data: continue
        
        latencies = [d.get("latency") or d.get("latency_ms") for d in reg_data]
        latencies = [x for x in latencies if x is not None]
        
        uptimes = [d.get("uptime") or d.get("uptime_pct") for d in reg_data]
        uptimes = [x for x in uptimes if x is not None]
        
        if not latencies: continue
        
        results[reg] = {
            "avg_latency": sum(latencies) / len(latencies),
            "p95_latency": calc_p95(latencies),
            "avg_uptime": sum(uptimes) / len(uptimes) if uptimes else 0.0,
            "breaches": sum(1 for x in latencies if x > req.threshold_ms)
        }
    return results
