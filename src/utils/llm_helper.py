import os
import json
import requests
import re
from dotenv import load_dotenv
from typing import Dict, Any, List

load_dotenv()

class LLMHelper:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        self.base_url = "https://api.openai.com/v1/chat/completions"
        
        if self.api_key and self.api_key != "your_actual_api_key_here":
            print(f"✅ OpenAI API configured with model: {self.model}")
        else:
            print("❌ No valid API key found")

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key != "your_actual_api_key_here")

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
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a resume screening assistant. Extract candidate information and determine eligibility. Return only valid JSON."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 800,
            "response_format": {"type": "json_object"}
        }
        
        try:
            print("   🤖 Calling OpenAI API...")
            response = requests.post(self.base_url, headers=headers, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                json_result = json.loads(content)
                
                # Add profile links to the result
                json_result["profile_links"] = profile_links
                
                print(f"   ✅ Screening completed")
                return json_result
            else:
                print(f"   ❌ API Error: {response.status_code}")
                return {
                    "eligible": False,
                    "reason": f"API error: {response.status_code}",
                    "meets_minimum_requirements": False,
                    "profile_links": profile_links
                }
                
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
            return {
                "eligible": False,
                "reason": f"Request failed: {str(e)}",
                "meets_minimum_requirements": False,
                "profile_links": profile_links
            }