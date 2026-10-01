import os
import json
import requests
import re
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional

load_dotenv()


def load_key_from_env_file() -> Optional[str]:
    """Try to load a Gemini API key from .env directly"""
    try:
        if os.path.exists('.env'):
            with open('.env', 'r', encoding='utf-8') as f:
                content = f.read()
            patterns = [
                r'GEMINI_API_KEY\s*=\s*["\']?([^"\'\r\n]+)["\']?',
                r'GOOGLE_API_KEY\s*=\s*["\']?([^"\'\r\n]+)["\']?',
            ]
            for pat in patterns:
                m = re.search(pat, content, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
    except Exception as e:
        print(f"⚠️ Error reading .env file: {e}")
    return None


def get_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API key from environment or .env file"""
    key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not key or key in ("your_actual_api_key_here", "your_gemini_api_key"):
        file_key = load_key_from_env_file()
        if file_key:
            key = file_key
    if key:
        key = key.strip('"\' ')
    return key


def get_gemini_model(default: str = "gemini-2.0-flash") -> str:
    """Retrieve Gemini model name from environment or fallback default"""
    return os.getenv('GEMINI_MODEL') or os.getenv('GOOGLE_MODEL') or default


def get_gemini_base_url() -> str:
    """Retrieve Gemini base URL for the native REST API"""
    return os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta')


class GeminiMessage:
    def __init__(self, content: str):
        self.content = content


class GeminiChoice:
    def __init__(self, content: str):
        self.message = GeminiMessage(content)


class GeminiResponse:
    def __init__(self, content: str, raw: Dict[str, Any]):
        self.choices = [GeminiChoice(content)]
        self.raw = raw


class GeminiCompletions:
    def __init__(self, client: "GeminiClient"):
        self._client = client

    @staticmethod
    def _convert_part(part: Dict[str, Any]) -> Dict[str, Any]:
        part_type = part.get("type")

        if part_type == "text":
            return {"text": part.get("text", "")}

        if part_type == "image_url":
            image_url = part.get("image_url", {}).get("url", "")
            if image_url.startswith("data:") and "," in image_url:
                header, encoded = image_url.split(",", 1)
                mime_match = re.match(r"data:([^;]+);base64", header)
                mime_type = mime_match.group(1) if mime_match else "image/png"
                return {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": encoded,
                    }
                }

            return {"text": image_url}

        return {"text": str(part)}

    def create(
        self,
        model: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> GeminiResponse:
        model_name = model or self._client.model
        if not model_name:
            raise ValueError("Gemini model name is required")

        contents: List[Dict[str, Any]] = []
        system_instructions: List[str] = []

        for message in messages or []:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                system_instructions.append(str(content))
                continue

            if isinstance(content, list):
                parts = [self._convert_part(part) for part in content]
            else:
                parts = [{"text": str(content)}]

            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": parts})

        generation_config: Dict[str, Any] = {
            "temperature": temperature,
        }

        if max_tokens is not None:
            generation_config["maxOutputTokens"] = max_tokens

        if response_format and response_format.get("type") == "json_object":
            generation_config["responseMimeType"] = "application/json"

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        if system_instructions:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_instructions)}]
            }

        url = f"{self._client.base_url}/models/{model_name}:generateContent?key={self._client.api_key}"
        response = requests.post(url, json=payload, timeout=120)

        if not response.ok:
            raise Exception(f"Gemini request failed ({response.status_code}): {response.text}")

        data = response.json()
        content = ""

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(part.get("text", "") for part in parts if isinstance(part, dict))

        return GeminiResponse(content, data)


class GeminiChat:
    def __init__(self, client: "GeminiClient"):
        self.completions = GeminiCompletions(client)


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or get_gemini_api_key()
        self.model = model or get_gemini_model()
        self.base_url = (base_url or get_gemini_base_url()).rstrip('/')
        self.chat = GeminiChat(self)


def get_gemini_client():
    """Create a native Gemini client."""
    return GeminiClient()


class LLMHelper:
    def __init__(self):
        self.api_key = get_gemini_api_key()
        self.model = get_gemini_model("gemini-2.0-flash")
        self.base_url = get_gemini_base_url()
        self.client = get_gemini_client()
        
        if self.is_available():
            print(f"✅ Gemini API configured with model: {self.model}")
        else:
            print("❌ No valid Gemini API key found (set GEMINI_API_KEY in .env)")

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key not in ("your_actual_api_key_here", "your_gemini_api_key"))

    def extract_profile_links(self, text: str) -> Dict[str, str]:
        """Extract LinkedIn, GitHub, and other profile links from resume text"""
        profiles = {
            "linkedin": None,
            "github": None,
            "portfolio": None,
            "email": None,
            "phone": None
        }
        
        # LinkedIn patterns
        linkedin_patterns = [
            r'linkedin\.com/in/[a-zA-Z0-9-]+',
            r'linkedin\.com/company/[a-zA-Z0-9-]+',
            r'linkedin\.com/pub/[a-zA-Z0-9-]+',
            r'https?://(www\.)?linkedin\.com/[^\s]+'
        ]
        
        # GitHub patterns
        github_patterns = [
            r'github\.com/[a-zA-Z0-9-]+',
            r'https?://(www\.)?github\.com/[^\s]+'
        ]
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Phone pattern (basic)
        phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        
        text_lower = text.lower()
        
        # Extract LinkedIn
        for pattern in linkedin_patterns:
            match = re.search(pattern, text_lower)
            if match:
                profiles["linkedin"] = match.group(0) if not match.group(0).startswith('http') else f"https://{match.group(0)}"
                break
        
        # Extract GitHub
        for pattern in github_patterns:
            match = re.search(pattern, text_lower)
            if match:
                profiles["github"] = match.group(0) if not match.group(0).startswith('http') else f"https://{match.group(0)}"
                break
        
        # Extract email
        email_match = re.search(email_pattern, text)
        if email_match:
            profiles["email"] = email_match.group(0)
        
        # Extract phone
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            profiles["phone"] = phone_match.group(0)
        
        return profiles

    def screen_eligibility(self, resume_text: str, job_description: str) -> Dict[str, Any]:
        """Screen resume with lenient criteria - pass if meets SOME key requirements"""
        
        if not self.is_available():
            return {
                "eligible": False, 
                "reason": "API not available",
                "meets_minimum_requirements": False,
                "critical_missing_requirements": ["API service unavailable"]
            }
        
        # Extract profile links first
        profile_links = self.extract_profile_links(resume_text)
        
        prompt = f"""
        TASK: Screen this candidate for eligibility using REALISTIC and LENIENT criteria.

        JOB REQUIREMENTS:
        {job_description}

        CANDIDATE RESUME:
        {resume_text[:3500]}

        SCREENING GUIDELINES:
        1.  **Analyze Core Requirements**: Extract the 3-5 most critical skills (MUST HAVES) from the JOB REQUIREMENTS (e.g., Python, SQL, 3 years experience, leadership).
        2.  **Skills-Based Inclusion**: The candidate is **ELIGIBLE** if their resume explicitly demonstrates *at least 2* of the core technical or functional skills identified in the JOB REQUIREMENTS.
        3.  **Experience Flexibility**: If the JD requires X years, consider **transferable skills**, **academic projects**, or **internships** as proof of competency, especially for entry-level roles.
        4.  **Disqualification Rule**: Only mark as **NOT ELIGIBLE** if the candidate's background is entirely outside the job's domain (e.g., a Lawyer applying for a Software Engineer role) AND they lack any of the core required technical skills.
        5.  **Seniority Check**: For senior roles, ensure evidence of management, mentorship, or large-scale project leadership is present, even if the title isn't an exact match.


        HARD DISQUALIFIERS ONLY:
        - Completely unrelated background (e.g., accountant applying for developer role)
    
        Analyze and return ONLY valid JSON with this structure:
        {{
            "eligible": true/false,
            "reason": "brief explanation focusing on MUST HAVE criteria",
            "meets_minimum_requirements": true/false,
            "critical_missing_requirements": ["list if any"],
            "candidate_info": {{
                "name": "extracted full name",
                "email": "extracted email",
                "phone": "extracted phone number",
                "location": "extracted location if available",
                "total_experience": "X years",
                "current_role": "current/most recent position",
                "current_company": "current/most recent company"
            }},
            "skills_summary": {{
                "skills": ["list all relevant skills"],
                "certifications": ["list of certifications if any"]
            }}
        }}

        ELIGIBILITY THRESHOLD:
        - Mark as ELIGIBLE if candidate has reasonable experience in the field
        - Mark as ELIGIBLE if they have 2+ key skills from requirements
        - Mark as ELIGIBLE if they show good potential and learning ability
        - Be INCLUSIVE rather than exclusive in borderline cases
        """
        
        try:
            print("   🤖 Calling Gemini API...")
            client = get_gemini_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a resume screening assistant. Extract candidate information and determine eligibility. Return only valid JSON."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            # Clean possible markdown fencing (e.g. ```json ... ```)
            content_cleaned = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.IGNORECASE)
            content_cleaned = re.sub(r'\s*```$', '', content_cleaned).strip()
            
            # Extract first JSON object if surrounded by other text
            json_match = re.search(r'\{.*\}', content_cleaned, re.DOTALL)
            if json_match:
                json_result = json.loads(json_match.group())
            else:
                json_result = json.loads(content_cleaned)
            
            # Add profile links to the result
            json_result["profile_links"] = profile_links
            
            print(f"   ✅ Screening completed")
            return json_result
                
        except Exception as e:
            print(f"   ❌ Gemini request failed: {e}")
            return {
                "eligible": False,
                "reason": f"Request failed: {str(e)}",
                "meets_minimum_requirements": False,
                "profile_links": profile_links
            }