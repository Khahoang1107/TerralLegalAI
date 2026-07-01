import requests
import json
import io

response = requests.post(
    "http://localhost:8000/api/v1/chat",
    json={"question": "Sổ đỏ bị hỏng thì xin cấp đổi thế nào?"}
)
with io.open("test_chat_out.json", "w", encoding="utf-8") as f:
    f.write(json.dumps(response.json(), indent=2, ensure_ascii=False))
