"""
Conversational Chat-based JD Confirmation System
Natural chat interface for confirming job description details
"""

import os
import json
import re
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from enum import Enum

load_dotenv()


class ChatState(Enum):
    """States in the chat conversation"""
    GREETING = "greeting"
    EXTRACTING = "extracting"
    CONFIRM_TITLE = "confirm_title"
    CONFIRM_REQUIREMENTS = "confirm_requirements"
    CONFIRM_QUALIFICATIONS = "confirm_qualifications"
    CONFIRM_EXPERIENCE = "confirm_experience"
    CONFIRM_LOCATION = "confirm_location"
    FINAL_SUMMARY = "final_summary"
    ANALYZING_WORKFLOW = "analyzing_workflow"
    COMPLETE = "complete"


class JDConfirmationChat:
    """Interactive chat system for JD confirmation"""
    
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            api_key = self._load_key_from_env_file()
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found")
        
        # Set environment variable and initialize WITHOUT parameters
        os.environ['OPENAI_API_KEY'] = api_key
        self.client = OpenAI()  # Uses environment variable automatically
        self.model = "gpt-3.5-turbo"
        
        # Chat state
        self.state = ChatState.GREETING
        self.extracted_data = {}
        self.confirmed_data = {}
        self.conversation_history = []
        self.is_just_ranking = False
        self.needs_scheduling = True
    
    def _load_key_from_env_file(self) -> str:
        """Load API key from .env file"""
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
    
    def start_conversation(self, jd_text: str) -> str:
        """Start the conversation by extracting JD details"""
        self.state = ChatState.EXTRACTING
        
        # Extract details from JD
        self.extracted_data = self._extract_jd_details(jd_text)
        
        # Move to first confirmation
        self.state = ChatState.CONFIRM_TITLE
        
        # Generate greeting
        greeting = f"""👋 Hi! I'm your AI recruitment assistant. I've analyzed the job description and extracted some key details.

Let me confirm these with you one by one. You can:
- Type "yes" or "correct" if it's right
- Type the correct information if it needs changes
- Type "skip" if you want to come back to it later

Let's start!

📋 **Job Title:** {self.extracted_data.get('job_title', 'Not found')}

Is this correct?"""
        
        self.conversation_history.append({
            "role": "assistant",
            "content": greeting
        })
        
        return greeting
    
    def process_user_message(self, user_message: str) -> str:
        """Process user's response and generate next message"""
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Process based on current state
        response = self._handle_current_state(user_message)
        
        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        
        return response
    
    def _handle_current_state(self, user_message: str) -> str:
        """Handle user message based on current state"""
        user_msg_lower = user_message.lower().strip()
        
        # ============================================================
        # CONFIRM JOB TITLE
        # ============================================================
        if self.state == ChatState.CONFIRM_TITLE:
            if user_msg_lower in ['yes', 'correct', 'ok', 'y', 'yep', 'yeah']:
                self.confirmed_data['job_title'] = self.extracted_data.get('job_title', '')
                self.state = ChatState.CONFIRM_REQUIREMENTS
                return self._ask_requirements()
            else:
                # User provided a new title
                self.confirmed_data['job_title'] = user_message.strip()
                self.state = ChatState.CONFIRM_REQUIREMENTS
                return f"✅ Great! I've updated the job title to: **{user_message.strip()}**\n\n" + self._ask_requirements()
        
        # ============================================================
        # CONFIRM REQUIREMENTS
        # ============================================================
        elif self.state == ChatState.CONFIRM_REQUIREMENTS:
            requirements = self.extracted_data.get('requirements', [])
            
            if user_msg_lower in ['yes', 'correct', 'ok', 'y', 'yep', 'yeah']:
                self.confirmed_data['requirements'] = requirements
                self.state = ChatState.CONFIRM_QUALIFICATIONS
                return self._ask_qualifications()
            elif user_msg_lower in ['skip', 'none', 'no requirements']:
                self.confirmed_data['requirements'] = []
                self.state = ChatState.CONFIRM_QUALIFICATIONS
                return "⏭️ Skipping requirements.\n\n" + self._ask_qualifications()
            else:
                # User provided new requirements
                new_requirements = self._parse_list_from_message(user_message)
                self.confirmed_data['requirements'] = new_requirements
                self.state = ChatState.CONFIRM_QUALIFICATIONS
                return f"✅ Updated requirements ({len(new_requirements)} items)\n\n" + self._ask_qualifications()
        
        # ============================================================
        # CONFIRM QUALIFICATIONS
        # ============================================================
        elif self.state == ChatState.CONFIRM_QUALIFICATIONS:
            qualifications = self.extracted_data.get('qualifications', [])
            
            if user_msg_lower in ['yes', 'correct', 'ok', 'y', 'yep', 'yeah']:
                self.confirmed_data['qualifications'] = qualifications
                self.state = ChatState.CONFIRM_EXPERIENCE
                return self._ask_experience()
            elif user_msg_lower in ['skip', 'none', 'no qualifications']:
                self.confirmed_data['qualifications'] = []
                self.state = ChatState.CONFIRM_EXPERIENCE
                return "⏭️ Skipping qualifications.\n\n" + self._ask_experience()
            else:
                # User provided new qualifications
                new_qualifications = self._parse_list_from_message(user_message)
                self.confirmed_data['qualifications'] = new_qualifications
                self.state = ChatState.CONFIRM_EXPERIENCE
                return f"✅ Updated qualifications ({len(new_qualifications)} items)\n\n" + self._ask_experience()
        
        # ============================================================
        # CONFIRM EXPERIENCE
        # ============================================================
        elif self.state == ChatState.CONFIRM_EXPERIENCE:
            if user_msg_lower in ['yes', 'correct', 'ok', 'y', 'yep', 'yeah']:
                self.confirmed_data['experience'] = self.extracted_data.get('experience', '')
                self.state = ChatState.CONFIRM_LOCATION
                return self._ask_location()
            else:
                # User provided new experience
                self.confirmed_data['experience'] = user_message.strip()
                self.state = ChatState.CONFIRM_LOCATION
                return f"✅ Updated experience to: **{user_message.strip()}**\n\n" + self._ask_location()
        
        # ============================================================
        # CONFIRM LOCATION
        # ============================================================
        elif self.state == ChatState.CONFIRM_LOCATION:
            if user_msg_lower in ['yes', 'correct', 'ok', 'y', 'yep', 'yeah']:
                self.confirmed_data['work_location'] = self.extracted_data.get('work_location', '')
                self.state = ChatState.FINAL_SUMMARY
                return self._show_final_summary()
            else:
                # User provided new location
                self.confirmed_data['work_location'] = user_message.strip()
                self.state = ChatState.FINAL_SUMMARY
                return f"✅ Updated location to: **{user_message.strip()}**\n\n" + self._show_final_summary()
        
        # ============================================================
        # FINAL SUMMARY CONFIRMATION
        # ============================================================
        elif self.state == ChatState.FINAL_SUMMARY:
            if user_msg_lower in ['yes', 'correct', 'ok', 'confirm', 'y', 'yep', 'looks good', 'proceed']:
                self.state = ChatState.ANALYZING_WORKFLOW
                return self._analyze_workflow()
            elif any(word in user_msg_lower for word in ['change', 'edit', 'modify', 'no', 'wrong']):
                # Ask what to change
                return """What would you like to change? You can say:
- "change title"
- "change requirements"
- "change qualifications"
- "change experience"
- "change location"

Or type "**restart**" to start over."""
            elif 'restart' in user_msg_lower:
                self.state = ChatState.CONFIRM_TITLE
                return "🔄 Let's start over!\n\n" + self._ask_title()
            else:
                return """Please respond:
- "**yes**" to proceed with these details
- "**change [field]**" to modify something
- "**restart**" to start over"""
        
        # Default fallback
        return "I didn't understand that. Could you please clarify?"
    
    # ============================================================
    # QUESTION GENERATORS
    # ============================================================
    
    def _ask_title(self) -> str:
        """Ask about job title"""
        return f"📋 **Job Title:** {self.extracted_data.get('job_title', 'Not found')}\n\nIs this correct?"
    
    def _ask_requirements(self) -> str:
        """Ask about requirements"""
        requirements = self.extracted_data.get('requirements', [])
        
        if not requirements:
            return """🔧 **Technical/Skill Requirements:** None found

Please list the key requirements (one per line), or type "skip" if there are none."""
        
        req_list = "\n".join([f"  • {req}" for req in requirements])
        return f"""🔧 **Technical/Skill Requirements:**

{req_list}

Is this correct? (Type "yes" or provide the correct requirements, one per line)"""
    
    def _ask_qualifications(self) -> str:
        """Ask about qualifications"""
        qualifications = self.extracted_data.get('qualifications', [])
        
        if not qualifications:
            return """🎓 **Educational/Certification Qualifications:** None found

Please list the qualifications (one per line), or type "skip" if there are none."""
        
        qual_list = "\n".join([f"  • {qual}" for qual in qualifications])
        return f"""🎓 **Educational/Certification Qualifications:**

{qual_list}

Is this correct? (Type "yes" or provide the correct qualifications, one per line)"""
    
    def _ask_experience(self) -> str:
        """Ask about experience"""
        experience = self.extracted_data.get('experience', 'Not found')
        return f"""💼 **Required Experience:** {experience}

Is this correct? (Type "yes" or provide the correct experience level)"""
    
    def _ask_location(self) -> str:
        """Ask about work location"""
        location = self.extracted_data.get('work_location', 'Not found')
        return f"""📍 **Work Location:** {location}

Is this correct? (Type "yes" or provide the correct location)"""
    
    def _show_final_summary(self) -> str:
        """Show final summary of all confirmed data"""
        summary = f"""✨ **Summary of Confirmed Details:**

📋 **Job Title:** {self.confirmed_data.get('job_title', 'N/A')}

🔧 **Requirements:** {len(self.confirmed_data.get('requirements', []))} items
{self._format_list_preview(self.confirmed_data.get('requirements', []))}

🎓 **Qualifications:** {len(self.confirmed_data.get('qualifications', []))} items
{self._format_list_preview(self.confirmed_data.get('qualifications', []))}

💼 **Experience:** {self.confirmed_data.get('experience', 'N/A')}

📍 **Location:** {self.confirmed_data.get('work_location', 'N/A')}

---

Does everything look correct?
- Type "**yes**" to proceed
- Type "**change [field]**" to modify something"""
        
        return summary
    
    def _format_list_preview(self, items: List[str], max_items: int = 3) -> str:
        """Format list for preview"""
        if not items:
            return "  (None specified)"
        
        preview_items = items[:max_items]
        formatted = "\n".join([f"  • {item}" for item in preview_items])
        
        if len(items) > max_items:
            formatted += f"\n  ... and {len(items) - max_items} more"
        
        return formatted
    
    # ============================================================
    # BACKEND FUNCTIONS
    # ============================================================
    
    def _extract_jd_details(self, jd_text: str) -> Dict:
        """Extract details from JD using LLM"""
        try:
            prompt = f"""Extract key details from this job description:

JOB DESCRIPTION:
{jd_text}

Return JSON with:
{{
  "job_title": "...",
  "requirements": ["..."],
  "qualifications": ["..."],
  "experience": "...",
  "work_location": "..."
}}"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Extract structured job information accurately."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=600
            )
            
            result = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # Fallback
        return {
            "job_title": "Position",
            "requirements": [],
            "qualifications": [],
            "experience": "Not specified",
            "work_location": "Not specified"
        }
    
    def _parse_list_from_message(self, message: str) -> List[str]:
        """Parse a list from user message"""
        # Split by newlines or commas
        if '\n' in message:
            items = message.split('\n')
        elif ',' in message:
            items = message.split(',')
        else:
            # Single item
            items = [message]
        
        # Clean and filter
        items = [item.strip().lstrip('-•*').strip() for item in items]
        items = [item for item in items if item]
        
        return items
    
    def _analyze_workflow(self) -> str:
        """Analyze workflow using confirmed data"""
        try:
            from src.utils.jd_analyzer import analyze_with_confirmation
            
            # Call the analyzer (simplified version)
            analysis = analyze_with_confirmation(
                self.confirmed_data,
                is_just_ranking=self.is_just_ranking,
                needs_scheduling=self.needs_scheduling
            )
            
            # Store analysis
            self.workflow_analysis = analysis
            self.state = ChatState.COMPLETE
            
            return f"""✨ **Confirmation complete! You can now proceed to upload your resumes and start processing.**"""
            
        except Exception as e:
            self.state = ChatState.COMPLETE
            return f"""⚠️ Configuration finalized with default settings.

✨ **Ready to proceed!**

You can now start the recruitment process."""
    
    def get_workflow_config(self) -> Dict:
        """Get the final workflow configuration"""
        if not hasattr(self, 'workflow_analysis'):
            # Return default if not analyzed yet
            return {
                'needs_interview': self.needs_scheduling,
                'job_title': self.confirmed_data.get('job_title', 'Position'),
                'needs_background_check': False,
                'workflow_data': {
                    'run_screening': True,
                    'run_background': False,
                    'run_ranking': True,
                    'run_scheduling': self.needs_scheduling,
                    'run_communication': self.needs_scheduling
                },
                'analysis_details': {
                    'confirmed_jd_data': self.confirmed_data
                },
                'just_ranking': self.is_just_ranking
            }
        
        return {
            'needs_interview': self.workflow_analysis.get('needs_scheduling', False),
            'job_title': self.confirmed_data.get('job_title', 'Position'),
            'needs_background_check': self.workflow_analysis.get('needs_background_check', False),
            'workflow_data': {
                'run_screening': True,
                'run_background': self.workflow_analysis.get('needs_background_check', False),
                'run_ranking': True,
                'run_scheduling': self.workflow_analysis.get('needs_scheduling', False),
                'run_communication': self.workflow_analysis.get('needs_emails', False)
            },
            'analysis_details': {
                'semantic_analysis': self.workflow_analysis.get('semantic_analysis', {}),
                'confirmed_jd_data': self.confirmed_data
            },
            'analysis_source': 'chat_based_confirmation',
            'just_ranking': self.is_just_ranking or self.workflow_analysis.get('semantic_analysis', {}).get('just_ranking', False)
        }
    
    def is_complete(self) -> bool:
        """Check if chat is complete"""
        return self.state == ChatState.COMPLETE