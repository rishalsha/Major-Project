"""
Complete Semantic Job Description Analyzer
Supports both chat-based confirmation and direct analysis
"""

import os
import json
import re
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class SemanticJDAnalyzer:
    """Analyzes job descriptions using LLM with Chain-of-Thought"""
    
    def __init__(self):
        # Get API key from environment
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            api_key = self._load_key_from_env_file()
        
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Please create a .env file with: "
                "OPENAI_API_KEY=your_key_here"
            )
        
        # FIX: Set environment variable and initialize WITHOUT parameters
        os.environ['OPENAI_API_KEY'] = api_key
        self.client = OpenAI()  # Uses environment variable automatically
        self.model = "gpt-3.5-turbo"
    
    def _load_key_from_env_file(self) -> str:
        """Try to load API key from .env file directly"""
        try:
            if os.path.exists('.env'):
                with open('.env', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and 'OPENAI_API_KEY=' in line:
                            return line.split('=', 1)[1].strip()
        except Exception as e:
            print(f"⚠️ Error reading .env file: {e}")
        return None

    # ================================================================
    # EXTRACTION FUNCTIONS (for chat confirmation)
    # ================================================================
    
    def extract_jd_details(self, jd_text: str) -> Dict:
        """
        Extract key details from JD for user confirmation
        Returns structured data that can be reviewed/edited
        """
        print("\n" + "="*60)
        print("📋 EXTRACTING JD DETAILS FOR CONFIRMATION")
        print("="*60)
        
        if not jd_text or len(jd_text.strip()) < 10:
            return self._get_default_extraction()
        
        try:
            prompt = f"""
            Extract key details from this job description. Focus on understanding the semantic meaning.
            
            JOB DESCRIPTION:
            {jd_text}
            
            Extract and return the following information in JSON format:
            {{
              "job_title": "The primary job title/position name",
              "requirements": ["List of key technical/skill requirements"],
              "qualifications": ["List of educational/certification qualifications"],
              "experience": "Required years of experience (e.g., '3-5 years' or 'Entry Level')",
              "work_location": "Work location/mode (e.g., 'Remote', 'New York, NY', 'Hybrid')",
              "key_responsibilities": ["Main job responsibilities"],
              "missing_fields": ["List any fields that couldn't be extracted from the JD"]
            }}
            
            INSTRUCTIONS:
            - Extract semantic meaning, not just keywords
            - If a field is not clearly mentioned, add it to "missing_fields"
            - Be concise but accurate
            - For requirements, focus on must-have skills/technologies
            - For qualifications, focus on degrees/certifications
            """
            
            print("🤖 Asking LLM to extract JD details...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting structured information from job descriptions. Extract semantic meaning accurately."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            result = response.choices[0].message.content
            
            # Extract JSON
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                extracted = json.loads(json_match.group())
                
                # Validate and clean
                extracted = self._validate_extraction(extracted)
                
                print("\n✅ EXTRACTED DETAILS:")
                print(f"   Job Title: {extracted.get('job_title', 'N/A')}")
                print(f"   Requirements: {len(extracted.get('requirements', []))} items")
                print(f"   Qualifications: {len(extracted.get('qualifications', []))} items")
                print(f"   Experience: {extracted.get('experience', 'N/A')}")
                print(f"   Work Location: {extracted.get('work_location', 'N/A')}")
                
                if extracted.get('missing_fields'):
                    print(f"   ⚠️  Missing: {', '.join(extracted['missing_fields'])}")
                
                return extracted
            
        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            return self._get_default_extraction()
        
        return self._get_default_extraction()
    
    def _validate_extraction(self, extracted: Dict) -> Dict:
        """Validate and clean extracted data"""
        # Ensure all required fields exist
        defaults = {
            "job_title": "Position",
            "requirements": [],
            "qualifications": [],
            "experience": "Not specified",
            "work_location": "Not specified",
            "key_responsibilities": [],
            "missing_fields": []
        }
        
        for key, default_value in defaults.items():
            if key not in extracted or not extracted[key]:
                extracted[key] = default_value
                if key not in extracted.get('missing_fields', []):
                    if 'missing_fields' not in extracted:
                        extracted['missing_fields'] = []
                    extracted['missing_fields'].append(key)
        
        # Clean lists
        for list_field in ['requirements', 'qualifications', 'key_responsibilities', 'missing_fields']:
            if list_field in extracted:
                if isinstance(extracted[list_field], list):
                    # Remove empty strings
                    extracted[list_field] = [item for item in extracted[list_field] if item and str(item).strip()]
                else:
                    extracted[list_field] = []
        
        return extracted
    
    def _get_default_extraction(self) -> Dict:
        """Return default empty extraction"""
        return {
            "job_title": "",
            "requirements": [],
            "qualifications": [],
            "experience": "",
            "work_location": "",
            "key_responsibilities": [],
            "missing_fields": ["job_title", "requirements", "qualifications", "experience", "work_location"]
        }
    
    # ================================================================
    # WORKFLOW ANALYSIS (with confirmed data from chat)
    # ================================================================
    
    def analyze_with_confirmed_data(
        self, 
        confirmed_data: Dict,
        is_just_ranking: bool = False,
        needs_scheduling: bool = True
    ) -> Dict:
        """
        Return a basic workflow config based on confirmed data.
        The heavy reasoning now happens INSIDE the Orchestrator graph.
        """
        return self._get_default_workflow(is_just_ranking, needs_scheduling, confirmed_data)
    
    def reason_about_workflow(self, job_description: str, user_preferences: Dict) -> Dict:
        """
        Deep semantic reasoning for the Orchestrator jd_reasoner node.
        This is called DURING the recruitment process.
        """
        try:
            is_just_ranking = user_preferences.get('is_just_ranking', False)
            needs_scheduling = user_preferences.get('needs_scheduling', True)
            
            prompt = f"""
            Perform a deep semantic analysis of this job description to inform the recruitment workflow.
            
            JOB DESCRIPTION:
            {job_description[:4000]}
            
            USER PREFERENCES:
            - JUST RANKING (No Interview/Emails): {is_just_ranking}
            - SCHEDULING ENABLED: {needs_scheduling}
            
            INSTRUCTIONS:
            1. **TECHNICAL NATURE**: Is it a technical/creative role needing skill verification (coding, design, IT, etc.)?
            2. **INTERVIEW NEED**: Should we interview? (Usually True unless 'JUST RANKING' is True. Note: 'Quick chat', 'Chat', or 'Meeting' implies has_interview=True).
            3. **BACKGROUND VERIFICATION (CRITICAL)**: Decide if this role needs background/credential verification.
               - Infer this from labels like 'security-sensitive', 'financial responsibilities', 'high trust', 'Senior/Lead technical', or 'portfolio/github verification'.
               - **SPECIAL RULE**: If the JD explicitly mentions 'Junior', 'Entry Level', or 'Intern' in the title, set needs_background_verification to FALSE (even if contradictory experience years are mentioned).
               - **SKIP CHECK**: If the JD mentions 'Quick process', 'Rapid hire', 'Immediate chat', or implies a low-stakes role (manual labor, drivers), default to False unless security is mentioned.
               - **RUN CHECK**: For 'Senior', 'Lead', 'Core Banking', 'Security', or cases where 'portfolio links' or 'references' are highlighted for technical depth.
            
            Return ONLY a JSON object:
            {{
              "is_technical": [bool],
              "has_interview": [bool],
              "just_ranking": [bool],
              "needs_background_verification": [bool],
              "semantic_reasoning": "Briefly explain based on JD cues (e.g. 'Quick process mentioned' or 'Security sensitivity').",
              "job_title": "[Extracted Title]"
            }}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a senior recruitment orchestrator. Analyze the JD deeply to determine the optimized workflow. Focus on implicit cues for trust and verification requirements."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
                
        except Exception as e:
            print(f"⚠️ Reasoning failed: {e}")
            
        # Fallback
        return {
            "is_technical": False,
            "has_interview": user_preferences.get('needs_scheduling', True) and not user_preferences.get('is_just_ranking', False),
            "just_ranking": user_preferences.get('is_just_ranking', False),
            "needs_background_verification": False,
            "semantic_reasoning": "Fallback reasoning based on defaults.",
            "job_title": "Position"
        }
    
    def _build_jd_context(self, confirmed_data: Dict) -> str:
        """Build readable context from confirmed JD data"""
        context = f"""
Job Title: {confirmed_data.get('job_title', 'N/A')}

Requirements:
{self._format_list(confirmed_data.get('requirements', []))}

Qualifications:
{self._format_list(confirmed_data.get('qualifications', []))}

Experience Required: {confirmed_data.get('experience', 'N/A')}

Work Location: {confirmed_data.get('work_location', 'N/A')}

Key Responsibilities:
{self._format_list(confirmed_data.get('key_responsibilities', []))}
        """.strip()
        
        return context
    
    def _format_list(self, items: list) -> str:
        """Format list items for display"""
        if not items:
            return "- Not specified"
        return "\n".join([f"- {item}" for item in items])
    
    def _process_workflow_analysis(
        self, 
        response: str, 
        is_just_ranking: bool,
        needs_scheduling: bool
    ) -> Dict:
        """Process LLM's workflow analysis"""
        print("\n📝 LLM'S WORKFLOW ANALYSIS:")
        print("="*60)
        print(response)
        print("="*60)
        
        # Extract JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        
        if json_match:
            try:
                analysis = json.loads(json_match.group())
                
                # Validate with user preferences
                analysis = self._validate_workflow_analysis(
                    analysis, 
                    is_just_ranking, 
                    needs_scheduling
                )
                
                print("\n✅ WORKFLOW DECISIONS:")
                print(f"   🔧 Technical role: {analysis.get('is_technical', False)}")
                print(f"   📅 Has interview: {analysis.get('has_interview', False)}")
                print(f"   📊 Just ranking: {analysis.get('just_ranking', False)}")
                print(f"   🔍 Background verification: {analysis.get('needs_background_verification', False)}")
                
                return analysis
                
            except json.JSONDecodeError:
                print(f"⚠️  Could not parse JSON")
        
        # Fallback
        return self._get_fallback_analysis(is_just_ranking, needs_scheduling)
    
    def _validate_workflow_analysis(
        self, 
        analysis: Dict,
        is_just_ranking: bool,
        needs_scheduling: bool
    ) -> Dict:
        """Ensure workflow decisions respect user preferences"""
        
        # Convert string booleans
        for key in ['is_technical', 'has_interview', 'just_ranking', 'needs_background_verification']:
            if key in analysis and isinstance(analysis[key], str):
                analysis[key] = analysis[key].lower() in ['true', 'yes', '1', 't']
        
        # RESPECT USER PREFERENCES:
        
        # 1. If user said "just ranking", enforce it
        if is_just_ranking:
            analysis['just_ranking'] = True
            analysis['has_interview'] = False
            print("   ✓ User preference: Just ranking (no interviews)")
        
        # 2. If user wants scheduling, enforce it
        elif needs_scheduling:
            analysis['has_interview'] = True
            analysis['just_ranking'] = False
            print("   ✓ User preference: Scheduling enabled")
        
        # 3. Background verification logic
        if analysis.get('is_technical', False):
            # Technical role → default to TRUE unless user explicitly said no
            if 'needs_background_verification' not in analysis:
                analysis['needs_background_verification'] = True
        
        return analysis
    
    def _get_fallback_analysis(self, is_just_ranking: bool, needs_scheduling: bool) -> Dict:
        """Fallback analysis based on user preferences"""
        return {
            "is_technical": False,
            "has_interview": needs_scheduling and not is_just_ranking,
            "just_ranking": is_just_ranking,
            "needs_background_verification": False,
            "semantic_reasoning": "Fallback analysis based on user preferences"
        }
    
    def _convert_to_workflow_decisions(self, analysis: Dict, confirmed_data: Dict) -> Dict:
        """Convert analysis to final workflow decisions"""
        
        is_technical = analysis.get("is_technical", False)
        has_interview = analysis.get("has_interview", True)
        just_ranking = analysis.get("just_ranking", False)
        needs_background = analysis.get("needs_background_verification", False)
        
        # Workflow steps
        needs_scheduling = has_interview and not just_ranking
        
        print("\n🔧 FINAL WORKFLOW CONFIGURATION:")
        print(f"   Screening: TRUE (always)")
        print(f"   Background Check: {needs_background}")
        print(f"   Ranking: TRUE (always)")
        print(f"   Scheduling: {needs_scheduling}")
        print(f"   Communication: {needs_scheduling}")
        
        return {
            "needs_screening": True,
            "needs_background_check": needs_background,
            "needs_ranking": True,
            "needs_scheduling": needs_scheduling,
            "needs_emails": needs_scheduling,
            "confirmed_jd_data": confirmed_data,
            "semantic_analysis": analysis,
            "job_title": confirmed_data.get('job_title', 'Position'),
            "just_ranking": just_ranking
        }
    
    def _get_default_workflow(self, is_just_ranking: bool, needs_scheduling: bool, confirmed_data: Dict = None) -> Dict:
        """Default workflow based on user preferences"""
        has_interview = needs_scheduling and not is_just_ranking
        
        return {
            "needs_screening": True,
            "needs_background_check": False,
            "needs_ranking": True,
            "needs_scheduling": has_interview,
            "needs_emails": has_interview,
            "confirmed_jd_data": confirmed_data or {},
            "semantic_analysis": {
                "is_technical": False,
                "has_interview": has_interview,
                "just_ranking": is_just_ranking,
                "needs_background_verification": False,
                "semantic_reasoning": "Default workflow"
            },
            "job_title": confirmed_data.get('job_title', 'Position') if confirmed_data else "Position",
            "just_ranking": is_just_ranking
        }
    
    # ================================================================
    # LEGACY FUNCTIONS (for backward compatibility)
    # ================================================================
    
    def analyze(self, jd_text: str) -> Dict:
        """
        Legacy direct analysis (for backward compatibility)
        Use analyze_with_confirmed_data() for better results
        """
        print("\n" + "="*60)
        print("🧠 LEGACY: DIRECT JD ANALYSIS (without confirmation)")
        print("="*60)
        
        if not jd_text or len(jd_text.strip()) < 10:
            print("⚠️  Empty JD, using default workflow")
            return self._get_default_analysis("Empty JD")
        
        try:
            # First extract details
            extracted = self.extract_jd_details(jd_text)
            
            # Then analyze (assuming full process with scheduling)
            return self.analyze_with_confirmed_data(
                extracted,
                is_just_ranking=False,
                needs_scheduling=True
            )
            
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            return self._get_default_analysis(f"Analysis error: {str(e)}")
    
    def extract_title(self, jd_text: str) -> str:
        """Extract job title using semantic understanding"""
        if not jd_text or len(jd_text.strip()) < 10:
            return "Open Position"
        
        try:
            prompt = f"""Extract the primary job title from this text using semantic understanding:
            
            {jd_text[:500]}
            
            Return only the title, no explanations. Focus on semantic meaning."""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Extract semantic job title."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=30
            )
            
            title = response.choices[0].message.content.strip()
            # Clean up
            title = title.replace('"', '').replace("'", "").strip()
            title = re.sub(r'(?i)(job title:|title:|position:|role:)', '', title).strip()
            
            return title if title else "Position"
            
        except Exception as e:
            print(f"⚠️ Title extraction failed: {e}")
            return "Position"
    
    def _get_default_analysis(self, reason: str) -> Dict:
        """Return default analysis with semantic defaults"""
        return {
            "needs_screening": True,
            "needs_background_check": False,
            "needs_ranking": True,
            "needs_scheduling": False,
            "needs_emails": False,
            "semantic_analysis": {
                "is_technical": False,
                "has_interview": False,
                "just_ranking": False,
                "needs_background_verification": False,
                "semantic_reasoning": f"Default: {reason}"
            }
        }


# ================================================================
# PUBLIC API FUNCTIONS
# ================================================================

def extract_jd_details(jd_text: str) -> Dict:
    """
    Extract JD details for user confirmation
    Used by chat system
    """
    analyzer = SemanticJDAnalyzer()
    return analyzer.extract_jd_details(jd_text)


def analyze_with_confirmation(
    confirmed_data: Dict,
    is_just_ranking: bool = False,
    needs_scheduling: bool = True
) -> Dict:
    """
    Determine workflow using confirmed data
    Used after chat confirmation
    """
    analyzer = SemanticJDAnalyzer()
    return analyzer.analyze_with_confirmed_data(
        confirmed_data, 
        is_just_ranking, 
        needs_scheduling
    )


def analyze_job_description(jd_text: str) -> Dict:
    """
    Legacy: Analyze JD directly without confirmation
    For backward compatibility
    """
    analyzer = SemanticJDAnalyzer()
    return analyzer.analyze(jd_text)


def extract_job_title_llm(jd_text: str) -> str:
    """Extract job title"""
    analyzer = SemanticJDAnalyzer()
    return analyzer.extract_title(jd_text)