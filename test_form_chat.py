import asyncio
import httpx
import uuid
import json

async def test_form_chat():
    async with httpx.AsyncClient() as client:
        # 1. Login
        email = f"test_{uuid.uuid4()}@terralegal.vn"
        resp = await client.post("http://localhost:8000/api/v1/auth/register", json={
            "full_name": "Test User",
            "email": email,
            "password": "password123"
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Bắt đầu chat để vào luồng điền form
        print("--- USER: Tôi muốn khai thuế sử dụng đất phi nông nghiệp ---")
        chat_resp = await client.post(
            "http://localhost:8000/api/v1/chat", 
            json={"question": "Tôi muốn khai thuế sử dụng đất phi nông nghiệp", "conversation_id": None}, 
            headers=headers,
            timeout=30.0
        )
        
        data = chat_resp.json()
        print("--- BOT: ---")
        print(data.get("answer"))
        
        conv_id = data.get("conversation_id")
        
        # Tiếp tục chat để xem bot hỏi gì tiếp theo
        for i in range(5):
            print("\n--- USER: Bỏ qua trường này ---")
            chat_resp = await client.post(
                "http://localhost:8000/api/v1/chat", 
                json={"question": "Bỏ qua trường này", "conversation_id": conv_id}, 
                headers=headers,
                timeout=30.0
            )
            data = chat_resp.json()
            print("--- BOT: ---")
            print(data.get("answer"))
            if data.get("form_completed"):
                print("\n[Form Completed]")
                break

if __name__ == "__main__":
    asyncio.run(test_form_chat())
