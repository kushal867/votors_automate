from duckduckgo_search import DDGS
import json

def test_search():
    print("Initializing DDGS...")
    try:
        with DDGS(timeout=10) as ddgs:
            print("Searching...")
            results = ddgs.text("Nepal politics", max_results=3)
            # results is a generator in some versions, or a list
            results_list = list(results)
            print(f"Found {len(results_list)} results.")
            for i, r in enumerate(results_list):
                print(f"Result {i+1}: {r.get('title')}")
    except Exception as e:
        print(f"Search failed with error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    test_search()
