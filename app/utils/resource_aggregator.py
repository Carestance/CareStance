
import urllib.parse

class ResourceAggregator:
    @staticmethod
    def get_ndli_link(keywords):
        """Generates a search link for National Digital Library of India."""
        query = " ".join(keywords)
        # NDLI search URL format
        encoded_query = urllib.parse.quote(query)
        return f"https://ndl.iitkgp.ac.in/re_search?key={encoded_query}"

    @staticmethod
    def get_arxiv_link(keywords):
        """Generates a search link for arXiv.org."""
        query = " AND ".join([f'all:"{k}"' for k in keywords[:3]]) # Limit keywords for arXiv
        encoded_query = urllib.parse.quote(query)
        return f"https://arxiv.org/search/?query={encoded_query}&searchtype=all&source=header"

    @staticmethod
    def get_youtube_link(keywords):
        """Generates a search link for YouTube."""
        query = " ".join(keywords) + " course"
        encoded_query = urllib.parse.quote(query)
        return f"https://www.youtube.com/results?search_query={encoded_query}"

    @staticmethod
    def get_google_scholar_link(keywords):
        """Generates a search link for Google Scholar."""
        query = " ".join(keywords)
        encoded_query = urllib.parse.quote(query)
        return f"https://scholar.google.com/scholar?q={encoded_query}"

    @staticmethod
    async def get_ai_recommendations(career_title, generate_content_func):
        """Uses AI (Groq/Gemini) to suggest specific high-quality resources."""
        prompt = f"""
        Act as an elite career counselor and resource curator. 
        For the career path "{career_title}", suggest 4 highly specific, high-quality learning resources.
        These could be specific online courses, seminal papers, influential books, or specialized documentation.

        Provide the response STRICTLY in JSON format with this structure:
        {{
            "resources": [
                {{
                    "title": "Resource Name",
                    "description": "Short description of what makes it great",
                    "link": "Direct link or search link",
                    "type": "Course/Paper/Book/Docs"
                }},
                ...
            ]
        }}
        """
        try:
            response_json = await generate_content_func(prompt)
            import json
            data = json.loads(response_json)
            return data.get("resources", [])
        except Exception as e:
            print(f"AI Resource Error: {e}")
            return []
