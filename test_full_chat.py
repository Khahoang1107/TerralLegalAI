import asyncio
import json
import requests
import io
import uuid

def test():
    email = f"test_{uuid.uuid4()}@terralegal.vn"
    resp = requests.post("http://localhost:8000/api/v1/auth/register", json={
        "full_name": "Test User",
        "email": email,
        "password": "password123"
    })
    
    token = resp.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    chat_resp = requests.post("http://localhost:8000/api/v1/chat", json={"question": "Sang tên sổ đỏ cần gì?"}, headers=headers)
    with io.open("error_trace.txt", "w", encoding="utf-8") as f:
        f.write(chat_resp.text)
    
if __name__ == "__main__":
    test()
