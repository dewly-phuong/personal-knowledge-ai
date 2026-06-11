# main.py
from fastapi import FastAPI
from chainlit.utils import mount_chainlit

app = FastAPI()

# 1. Tạo các API endpoints bình thường của FastAPI
@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Server FastAPI đang hoạt động"}

@app.get("/api/data")
def get_some_data():
    return {"data": [1, 2, 3]}

# 2. Gắn giao diện Chainlit vào một endpoint cụ thể (ví dụ: /chat)
mount_chainlit(app=app, target="app.py", path="/chat")
