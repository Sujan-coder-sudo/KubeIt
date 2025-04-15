import requests

response = requests.post(
    "http://localhost:8000/query",
    json={"question": "show pods in namespace"}
)
print(response.json())