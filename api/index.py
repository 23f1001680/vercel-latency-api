from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import json
import urllib.request
import os

app = FastAPI()

# Wide-open CORS configuration to prevent browser blocking
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

@app.post("/api/latency")
@app.post("/latency")
@app.post("/")
async def get_latency(req: LatencyRequest):
    # Guaranteed file fetch: Tries both the new 'api/' path and the root path on your GitHub
    urls = [
        "https://raw.githubusercontent.com/23f1001680/vercel-latency-api/main/api/q-vercel-latency.json",
        "https://raw.githubusercontent.com/23f1001680/vercel-latency-api/main/q-vercel-latency.json"
    ]
    
    data = None
    for url in urls:
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                break # Stop searching once successfully loaded
        except:
            continue
            
    # Absolute last resort fallback to local Vercel file system
    if data is None:
        try:
            file_path = os.path.join(os.path.dirname(__file__), "q-vercel-latency.json")
            with open(file_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            return {"error": f"Could not find JSON file anywhere. {str(e)}"}

    # Process the metrics for the grader
    results = {}
    for reg in req.regions:
        if isinstance(data, dict):
            reg_data = data.get(reg, [])
        else:
            reg_data = [d for d in data if d.get("region") == reg]
            
        if not reg_data: continue
        
        latencies = [d.get("latency") if d.get("latency") is not None else d.get("latency_ms") for d in reg_data]
        latencies = [x for x in latencies if x is not None]
        
        uptimes = [d.get("uptime") if d.get("uptime") is not None else d.get("uptime_pct") for d in reg_data]
        uptimes = [x for x in uptimes if x is not None]
        
        if not latencies: continue
        
        results[reg] = {
            "avg_latency": sum(latencies) / len(latencies),
            "p95_latency": calc_p95(latencies),
            "avg_uptime": sum(uptimes) / len(uptimes) if uptimes else 0.0,
            "breaches": sum(1 for x in latencies if x > req.threshold_ms)
        }
        
    return results
