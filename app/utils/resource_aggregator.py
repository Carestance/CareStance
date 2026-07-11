
import re
import urllib.parse
from urllib.parse import urlparse


RESOURCE_SEARCH_PROVIDERS = (
    "Coursera",
    "edX",
    "MIT OpenCourseWare",
    "Khan Academy",
    "YouTube",
    "Google Scholar",
)

PROVIDER_SEARCH_SITES = {
    "coursera": "coursera.org",
    "edx": "edx.org",
    "mit": "ocw.mit.edu",
    "ocw": "ocw.mit.edu",
    "khan": "khanacademy.org",
    "youtube": "youtube.com",
    "scholar": "scholar.google.com",
    "arxiv": "arxiv.org",
}


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _quote_query(*parts):
    query = " ".join(_clean_text(part) for part in parts if _clean_text(part))
    return urllib.parse.quote_plus(query)


def _valid_http_url(url):
    if not isinstance(url, str):
        return False
    url = url.strip()
    if not url or any(token in url.lower() for token in ("example.com", "placeholder", "your-url", "localhost")):
        return False
    if re.search(r"\s", url):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc) and "." in parsed.netloc

class ResourceAggregator:
    @staticmethod
    def is_valid_http_url(url):
        return _valid_http_url(url)

    @staticmethod
    def get_web_search_link(*query_parts):
        """Stable fallback search link. Prefer this over AI-invented direct URLs."""
        return f"https://www.google.com/search?q={_quote_query(*query_parts)}"

    @staticmethod
    def get_provider_search_link(provider, *query_parts):
        provider_key = _clean_text(provider).lower()
        query = _quote_query(*query_parts)
        for key, site in PROVIDER_SEARCH_SITES.items():
            if key in provider_key:
                return f"https://www.google.com/search?q={query}+site%3A{urllib.parse.quote_plus(site)}"

        return ResourceAggregator.get_web_search_link(provider, *query_parts)

    @staticmethod
    def build_learning_resource(name, career_title, step_action="", resource_type="Course", provider=None):
        clean_name = _clean_text(name) or f"{career_title} learning resource"
        clean_provider = _clean_text(provider)
        link_provider = clean_provider or ResourceAggregator.guess_provider(clean_name, resource_type)

        return {
            "name": clean_name,
            "url": ResourceAggregator.get_provider_search_link(
                link_provider,
                clean_name,
                career_title,
                step_action,
            ),
            "type": _clean_text(resource_type) or "Course",
            "provider": link_provider,
            "difficulty": "Beginner to Intermediate",
        }

    @staticmethod
    def guess_provider(title, resource_type=""):
        text = f"{title} {resource_type}".lower()
        if "mit" in text or "opencourseware" in text or "ocw" in text:
            return "MIT OpenCourseWare"
        if "edx" in text:
            return "edX"
        if "khan" in text:
            return "Khan Academy"
        if "youtube" in text or "video" in text:
            return "YouTube"
        if "paper" in text or "research" in text or "scholar" in text:
            return "Google Scholar"
        return "Coursera"

    @staticmethod
    def normalize_course_resources(courses, career_title, step_action=""):
        normalized = []
        source_courses = courses if isinstance(courses, list) else []

        for course in source_courses[:3]:
            if isinstance(course, dict):
                name = course.get("name") or course.get("title") or course.get("resource") or step_action
                resource_type = course.get("type") or course.get("kind") or "Course"
                provider = course.get("provider") or ResourceAggregator.guess_provider(name, resource_type)
            else:
                name = course
                resource_type = "Course"
                provider = ResourceAggregator.guess_provider(name, resource_type)

            normalized.append(ResourceAggregator.build_learning_resource(
                name=name,
                career_title=career_title,
                step_action=step_action,
                resource_type=resource_type,
                provider=provider,
            ))

        defaults = [
            ("Beginner foundation course", "Coursera"),
            ("Practical project tutorial", "YouTube"),
            ("Academic reference material", "Google Scholar"),
        ]
        while len(normalized) < 3:
            label, provider = defaults[len(normalized)]
            normalized.append(ResourceAggregator.build_learning_resource(
                name=f"{career_title} {label}",
                career_title=career_title,
                step_action=step_action,
                provider=provider,
            ))

        return normalized

    @staticmethod
    def normalize_roadmap_resources(path_data, career_title):
        if isinstance(path_data, list):
            normalized = {
                "steps": path_data,
                "progress_percentage": 0,
                "internships": [],
                "career_outlook": {},
                "reminders": [],
            }
            return ResourceAggregator.normalize_roadmap_resources(normalized, career_title)

        if not isinstance(path_data, dict):
            return path_data

        steps = path_data.get("steps")
        if not isinstance(steps, list):
            return path_data

        for step in steps:
            if not isinstance(step, dict):
                continue
            step["completed"] = bool(step.get("completed", False))
            action = step.get("action") or step.get("stage") or ""
            step["courses"] = ResourceAggregator.normalize_course_resources(
                step.get("courses") or step.get("resources") or [],
                career_title,
                action,
            )

        completed_count = sum(1 for step in steps if isinstance(step, dict) and step.get("completed"))
        calculated_progress = int((completed_count / len(steps)) * 100) if steps else 0
        existing_progress = path_data.get("progress_percentage") or 0
        try:
            existing_progress = int(existing_progress)
        except (TypeError, ValueError):
            existing_progress = 0
        path_data["progress_percentage"] = max(existing_progress, calculated_progress)

        return path_data

    @staticmethod
    def get_ndli_link(keywords):
        """Generates a search link for National Digital Library of India."""
        query = " ".join(keywords)
        encoded_query = urllib.parse.quote_plus(query)
        # The older ndl.iitkgp.ac.in deep search path is brittle; route via the current public domain.
        return f"https://www.google.com/search?q={encoded_query}+site%3Andl.gov.in"

    @staticmethod
    def get_arxiv_link(keywords):
        """Generates a search link for arXiv.org."""
        return ResourceAggregator.get_provider_search_link("arxiv", " ".join(keywords), "research papers")

    @staticmethod
    def get_youtube_link(keywords):
        """Generates a search link for YouTube."""
        return ResourceAggregator.get_provider_search_link("youtube", " ".join(keywords), "course tutorial")

    @staticmethod
    def get_google_scholar_link(keywords):
        """Generates a search link for Google Scholar."""
        return ResourceAggregator.get_provider_search_link("scholar", " ".join(keywords), "academic reference")

    @staticmethod
    async def get_ai_recommendations(career_title, generate_content_func):
        """Uses AI (Groq/Gemini) to suggest specific high-quality resources."""
        prompt = f"""
        Act as an elite career counselor and resource curator. 
        For the career path "{career_title}", suggest 4 highly specific, high-quality learning resources.
        These can be course names, paper/book titles, documentation topics, or certification names.
        Do NOT invent or return direct URLs. The app will create safe search links separately.

        Provide the response STRICTLY in JSON format with this structure:
        {{
            "resources": [
                {{
                    "title": "Resource Name",
                    "description": "Short description of what makes it great",
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
            resources = []
            for item in data.get("resources", [])[:4]:
                if not isinstance(item, dict):
                    continue
                title = _clean_text(item.get("title") or item.get("name"))
                resource_type = _clean_text(item.get("type") or "Resource")
                if not title:
                    continue
                provider = ResourceAggregator.guess_provider(title, resource_type)
                resources.append({
                    "title": title,
                    "description": _clean_text(item.get("description")) or f"Curated learning resource for {career_title}.",
                    "type": resource_type,
                    "provider": provider,
                    "link": ResourceAggregator.get_provider_search_link(provider, title, career_title),
                })
            return resources
        except Exception as e:
            print(f"AI Resource Error: {e}")
            return [
                {
                    "title": f"{career_title} Foundation Course",
                    "description": "Start with structured beginner-friendly courses and compare syllabi before committing.",
                    "type": "Course",
                    "provider": "Coursera",
                    "link": ResourceAggregator.get_provider_search_link("Coursera", career_title, "foundation course"),
                },
                {
                    "title": f"{career_title} Practical Projects",
                    "description": "Use project tutorials to build visible proof of skill while learning.",
                    "type": "Video",
                    "provider": "YouTube",
                    "link": ResourceAggregator.get_provider_search_link("YouTube", career_title, "project tutorial"),
                },
            ]
