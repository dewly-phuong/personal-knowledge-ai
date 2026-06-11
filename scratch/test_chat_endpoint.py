import asyncio
import httpx
import json

async def main():
    url = "http://127.0.0.1:8000/api/chat"
    payload = {
        "query": "Tìm kiếm thông tin về qmd và các tính năng chính của nó",
        "chat_history": []
    }
    
    print("Connecting to /api/chat...")
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                print(f"Status Code: {response.status_code}")
                if response.status_code != 200:
                    print(await response.aread())
                    return
                async for line in response.aiter_lines():
                    print(f"LINE: {line}")
    except Exception as e:
        print(f"Connection/Stream Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
