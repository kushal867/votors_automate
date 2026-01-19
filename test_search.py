from duckduckgo_search import DDGS

def test_search():
    try:
        with DDGS() as ddgs:
            results = ddgs.text("Nepal current news", max_results=5)
            print("Search Results:", results)
    except Exception as e:
        print("Search Failed:", e)

if __name__ == "__main__":
    test_search()
