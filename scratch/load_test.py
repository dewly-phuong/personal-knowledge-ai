import asyncio
import time
import httpx
import numpy as np

# Configuration
URL = "http://127.0.0.1:8000/api/chat"
CONCURRENT_USERS = 20
QUERY = "Tìm kiếm thông tin về qmd và các tính năng chính của nó"

async def simulate_user(client: httpx.AsyncClient, user_id: int) -> dict:
    payload = {
        "query": QUERY,
        "chat_history": []
    }
    
    start_time = time.perf_counter()
    ttft = None
    total_time = None
    success = False
    tokens_count = 0
    
    try:
        async with client.stream("POST", URL, json=payload, timeout=90.0) as response:
            if response.status_code == 200:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if ttft is None:
                        ttft = time.perf_counter() - start_time
                    if line.startswith("data: "):
                        tokens_count += 1
                total_time = time.perf_counter() - start_time
                success = True
            else:
                print(f"User {user_id} failed with status code {response.status_code}")
    except Exception as e:
        print(f"User {user_id} failed with exception: {e}")
        
    return {
        "user_id": user_id,
        "success": success,
        "ttft": ttft if ttft is not None else -1.0,
        "total_time": total_time if total_time is not None else -1.0,
        "tokens": tokens_count
    }

async def main():
    print(f"Starting load test with {CONCURRENT_USERS} concurrent users...")
    print(f"Endpoint: {URL}")
    print(f"Query: '{QUERY}'\n")
    
    # We increase limits to allow large pool sizes
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    
    async with httpx.AsyncClient(limits=limits, timeout=90.0) as client:
        start_all = time.perf_counter()
        tasks = [simulate_user(client, i) for i in range(CONCURRENT_USERS)]
        results = await asyncio.gather(*tasks)
        end_all = time.perf_counter()
        
    total_wall_time = end_all - start_all
    
    # Analyze results
    success_results = [r for r in results if r["success"]]
    failures = CONCURRENT_USERS - len(success_results)
    
    ttfts = [r["ttft"] for r in success_results if r["ttft"] > 0]
    total_times = [r["total_time"] for r in success_results if r["total_time"] > 0]
    
    print("--- Load Test Results ---")
    print(f"Total Wall Clock Time: {total_wall_time:.2f} seconds")
    print(f"Successful Requests: {len(success_results)} / {CONCURRENT_USERS} ({len(success_results)/CONCURRENT_USERS*100:.1f}%)")
    print(f"Failed Requests: {failures}")
    
    if success_results:
        print("\n--- Latency to First Token (TTFT) ---")
        print(f"  Min: {np.min(ttfts):.3f}s")
        print(f"  Max: {np.max(ttfts):.3f}s")
        print(f"  Avg: {np.mean(ttfts):.3f}s")
        print(f"  P50: {np.percentile(ttfts, 50):.3f}s")
        print(f"  P90: {np.percentile(ttfts, 90):.3f}s")
        print(f"  P95: {np.percentile(ttfts, 95):.3f}s")
        
        print("\n--- Full Request Stream Duration ---")
        print(f"  Min: {np.min(total_times):.3f}s")
        print(f"  Max: {np.max(total_times):.3f}s")
        print(f"  Avg: {np.mean(total_times):.3f}s")
        print(f"  P50: {np.percentile(total_times, 50):.3f}s")
        print(f"  P90: {np.percentile(total_times, 90):.3f}s")
        print(f"  P95: {np.percentile(total_times, 95):.3f}s")
    else:
        print("No successful requests to analyze.")

if __name__ == "__main__":
    asyncio.run(main())
