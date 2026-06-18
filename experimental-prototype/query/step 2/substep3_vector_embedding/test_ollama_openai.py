import requests

def test_ollama_openai():
    url = "http://localhost:11434/v1/embeddings"
    data = {
        "model": "qwen3-embedding:4b",
        "input": "The sky is blue because of Rayleigh scattering."
    }
    
    try:
        print(f"Testing Ollama OpenAI endpoint at {url} with model {data['model']}...")
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        if "data" in result and len(result["data"]) > 0:
            embedding = result["data"][0]["embedding"]
            print(f"Success! Embedding dimension: {len(embedding)}")
            print(f"First 5 values: {embedding[:5]}")
        else:
            print("Response missing 'data' or empty:", result)
    except Exception as e:
        print(f"Failed to connect to Ollama OpenAI endpoint: {e}")

if __name__ == "__main__":
    test_ollama_openai()
