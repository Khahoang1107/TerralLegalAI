import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8000/api/v1/auth/login", data={"username": "admin@terralegal.vn", "password": "123"})
        token = r.json().get("access_token")
        
        r2 = await client.get("http://localhost:8000/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        print(r2.status_code)
        print(r2.text)

asyncio.run(main())
