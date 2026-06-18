import requests
url = "http://172.20.10.2:1234/v1/embeddings"
data = {"input": "hello", "model": "qwen3-embedding-4b-dwq"}
try:
    response = requests.post(url, json=data, timeout=5)
    r = response.json()
    if 'data' in r:
        print("READY! DIMENSION:", len(r['data'][0]['embedding']))
    else:
        print(r)
except Exception as e:
    print("Error:", e)
