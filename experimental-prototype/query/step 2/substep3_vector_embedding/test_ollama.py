import requests

def test_ollama():
    url = "http://localhost:11434/api/embeddings"
    data = {
        "model": "qwen3-embedding:4b",
        "prompt": "The sky is blue because of Rayleigh scattering."
    }
    
    try:
        print(f"Testing Ollama at {url} with model {data['model']}...")
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        if "embedding" in result:
            print(f"Success! Embedding dimension: {len(result['embedding'])}")
            print(f"First 5 values: {result['embedding'][:5]}")
        else:
            print("Response missing 'embedding' field:", result)
    except Exception as e:
        print(f"Failed to connect to Ollama: {e}")

if __name__ == "__main__":
    test_ollama()
