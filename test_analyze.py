import requests

url_login = "http://localhost:8000/api/v1/auth/login"
data = {"username": "admin@example.com", "password": "password"} # Assuming default credentials
res_login = requests.post(url_login, data=data)
token = res_login.json().get("access_token")

url = "http://localhost:8000/api/v1/forms/analyze-docx"
files = {'file': open('D:\\TerraLegalAI\\test.docx', 'rb')}
data_form = {'detect_blanks': 'true'}
headers = {'Authorization': f'Bearer {token}'} 

response = requests.post(url, files=files, data=data_form, headers=headers)
print(response.status_code)
print(response.json())
