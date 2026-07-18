
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.utils.resource_aggregator import ResourceAggregator
from app.data.career_keywords import career_keywords

def test_aggregator():
    print("Testing ResourceAggregator...")
    
    test_careers = ["AI ML Researcher", "Data Scientist", "Software Engineer"]
    
    for career in test_careers:
        print(f"\nCareer: {career}")
        keywords = career_keywords.get(career)
        print(f"Keywords: {keywords}")
        
        ndli = ResourceAggregator.get_ndli_link(keywords)
        arxiv = ResourceAggregator.get_arxiv_link(keywords)
        youtube = ResourceAggregator.get_youtube_link(keywords)
        scholar = ResourceAggregator.get_google_scholar_link(keywords)
        
        print(f"NDLI: {ndli}")
        print(f"arXiv: {arxiv}")
        print(f"YouTube: {youtube}")
        print(f"Scholar: {scholar}")
        
        assert "ndl.iitkgp.ac.in" in ndli
        assert "arxiv.org" in arxiv
        assert "youtube.com" in youtube
        assert "scholar.google.com" in scholar

    print("\nSUCCESS: ResourceAggregator tests passed!")

async def test_ai_aggregator():
    print("\nTesting AI-powered Resource Recommendations...")
    
    # Mock generate_content_with_fallback for local testing if needed, 
    # but here we try to use the logic directly
    from app.main import generate_content_with_fallback
    
    test_career = "AI ML Researcher"
    print(f"Fetching AI resources for: {test_career}")
    
    resources = await ResourceAggregator.get_ai_recommendations(test_career, generate_content_with_fallback)
    
    print(f"AI Suggested Resources: {len(resources)}")
    for res in resources:
        print(f" - {res.get('title')} ({res.get('type')})")
        
    assert len(resources) > 0
    assert "title" in resources[0]
    assert "link" in resources[0]

    print("\nSUCCESS: AI Resource Recommendations verified!")

if __name__ == "__main__":
    import asyncio
    # First run the static link tests
    test_aggregator()
    # Then run the AI test
    try:
        asyncio.run(test_ai_aggregator())
    except Exception as e:
        print(f"AI Test skipped or failed: {e}")
