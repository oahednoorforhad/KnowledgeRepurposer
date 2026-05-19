import requests

BASE_URL = "http://127.0.0.1:8000"

def test_pipeline():
    print("⏳ Step 1: Fetching YouTube transcript...")
    # Pass a YouTube URL to the scrape endpoint
    scrape_response = requests.post(
        f"{BASE_URL}/api/scrape/youtube",
        json={"url": "https://www.youtube.com/watch?v=nWzXyjXCoCE"},
    )
    
    if scrape_response.status_code != 200:
        print("❌ Failed to scrape transcript:", scrape_response.text)
        return
        
    transcript_data = scrape_response.json()
    transcript_text = transcript_data["transcript"]
    print(f"✅ Transcript fetched successfully! (Length: {len(transcript_text)} characters)")
    
    print("\n⏳ Step 2: Generating LinkedIn Post via OpenRouter...")
    # Hits your new generate endpoint
    # We only pass the transcript; it uses the default prompt and the API key from .env
    generate_response = requests.post(f"{BASE_URL}/api/generate/linkedin-post", json={
        "transcript": transcript_text
        # creative_direction: "optional extra guidance can go here"
    })
    
    if generate_response.status_code != 200:
        print("❌ Failed to generate post:", generate_response.text)
        return
        
    post_data = generate_response.json()
    print("\n✨ Generated LinkedIn Post ✨")
    print("=" * 40)
    print(post_data["post"])
    print("=" * 40)

if __name__ == "__main__":
    test_pipeline()
