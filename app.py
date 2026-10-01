"""
HireIQ: Smart Hiring, Zero Effort - Complete Frontend
FIXED: Now uses WorkflowConfig for JD analysis
"""

import streamlit as st
import os
import zipfile
import asyncio
import sys
import PyPDF2
import docx
import json
import shutil
import pandas as pd
import glob
from datetime import datetime
import time
import bcrypt
import nest_asyncio
import base64
from PIL import Image
import io

# Add your project to path

from src.agents.calendar_scheduling_agent import CalendarSchedulingAgent
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import database module
try:
    # First, add the current directory to sys.path
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Try to import database functions
    from database import (
        init_database, create_user, authenticate_user, save_session_to_db,
        save_candidates_to_db, get_user_sessions, get_session_details,
        delete_session, update_user_profile, get_user_statistics,
        get_user_by_id, get_session_candidates_csv
    )
    
    print("✅ Database module imported successfully")
    
except ImportError as e:
    print(f"⚠️ Database import error: {e}")
    # Create mock database functions as fallback
    def init_database():
        print("⚠️ Using mock database")
        return True
    
    def create_user(username, email, company_name, password):
        print(f"Mock: Creating user {username}")
        return True, "Account created successfully (mock)"
    
    def authenticate_user(username, password):
        print(f"Mock: Authenticating {username}")
        if username == "admin" and password == "admin":
            return True, {"id": 1, "username": "admin", "email": "admin@example.com"}
        return False, None
    
    def save_session_to_db(*args, **kwargs):
        print("Mock: Saving session")
        return 1
    
    def save_candidates_to_db(*args, **kwargs):
        print("Mock: Saving candidates")
        return True
    
    def get_user_sessions(user_id):
        print(f"Mock: Getting sessions for user {user_id}")
        return []
    
    def get_session_details(*args, **kwargs):
        print("Mock: Getting session details")
        return {}
    
    def delete_session(session_id, user_id):
        print(f"Mock: Deleting session {session_id}")
        return True
    
    def update_user_profile(*args, **kwargs):
        print("Mock: Updating user profile")
        return True
    
    def get_user_statistics(user_id):
        print(f"Mock: Getting statistics for user {user_id}")
        return {"total_sessions": 0, "total_candidates": 0}
    
    def get_user_by_id(user_id):
        print(f"Mock: Getting user by ID {user_id}")
        return {"id": user_id, "username": "mockuser"}
    
    def get_session_candidates_csv(session_id):
        print(f"Mock: Getting CSV for session {session_id}")
        return ""
# Custom CSS - Green theme for login, Black theme for other pages

# Initialize database at startup
try:
    init_database()
    print("✅ Database initialized successfully")
except Exception as e:
    print(f"⚠️ Failed to initialize database: {e}")


def save_scheduling_data_to_session_folder(session_folder, scheduling_data):
    """Properly save scheduling data to session folder"""
    try:
        output_folder = os.path.join(session_folder, "output")
        os.makedirs(output_folder, exist_ok=True)
        
        # Save the scheduling data
        schedule_file = os.path.join(output_folder, "schedule_results.json")
        with open(schedule_file, 'w', encoding='utf-8') as f:
            json.dump(scheduling_data, f, indent=2)
        
        # Also update the interview_schedule.json in output folder for backward compatibility
        output_schedule_file = os.path.join("output", "interview_schedule.json")
        with open(output_schedule_file, 'w', encoding='utf-8') as f:
            json.dump(scheduling_data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error saving scheduling data: {e}")
        return False
    
def load_css(page="login"):
    if page == "login":
        st.markdown("""
        <style>
        /* Green Theme for Login Page */
        :root {
            --primary-green: #10B981;
            --dark-green: #059669;
            --white: #FFFFFF;
            --black: #111827;
        }
        
        .stApp {
            background-color: var(--white);
        }
        
        .green-header {
            background: linear-gradient(135deg, var(--primary-green) 0%, var(--dark-green) 100%);
            padding: 2rem;
            border-radius: 15px;
            margin-bottom: 2rem;
            color: var(--white);
            text-align: center;
        }
        
        .stButton > button {
            background-color: var(--primary-green) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
        }
        
        .login-card {
            background: var(--white);
            border-radius: 10px;
            padding: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border: 1px solid #E5E7EB;
        }
        
        /* Login tabs styling - Black by default, Red on focus */
        div[data-testid="stTabs"] button[role="tab"] {
            color: #111827 !important;  /* Black color by default */
            font-weight: 600;
        }
        
        div[data-testid="stTabs"] button[role="tab"]:hover {
            color: #EF4444 !important;  /* Red on hover */
        }
        
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #EF4444 !important;  /* Red when selected */
            border-bottom-color: #EF4444 !important;
        }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
        /* Black Theme for Other Pages */
        :root {
            --primary-black: #111827;
            --dark-black: #000000;
            --light-gray: #374151;
            --white: #FFFFFF;
            --accent-red: #EF4444;
        }
        
        .stApp {
            background-color: var(--primary-black) !important;
            color: var(--white) !important;
        }
        
        /* Apply black background to all elements */
        .main .block-container {
            background-color: var(--primary-black) !important;
        }
        
        /* Text color for all elements */
        h1, h2, h3, h4, h5, h6, p, div, span, label {
            color: var(--white) !important;
        }
        
        /* Cards and containers */
        .stTabs, .stExpander, div[data-testid="stExpander"], 
        .stAlert, div[data-testid="stAlert"], 
        .stDataFrame, div[data-testid="stDataFrame"],
        .stMetric, div[data-testid="stMetric"] {
            background-color: var(--light-gray) !important;
            color: var(--white) !important;
        }
        
        /* Input fields */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div > div {
            background-color: var(--light-gray) !important;
            color: var(--white) !important;
            border: 1px solid #6B7280 !important;
        }
        
        /* Buttons */
        .stButton > button {
            background-color: var(--accent-red) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
        }
        
        .stButton > button:hover {
            background-color: #DC2626 !important;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab"] {
            background-color: var(--light-gray) !important;
            color: var(--white) !important;
            border-radius: 8px 8px 0 0 !important;
            padding: 0.75rem 1.5rem !important;
            font-weight: 600 !important;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: var(--accent-red) !important;
            color: white !important;
        }
        
        /* Headers */
        .black-header {
            background: linear-gradient(135deg, var(--primary-black) 0%, var(--dark-black) 100%);
            padding: 2rem;
            border-radius: 15px;
            margin-bottom: 1rem;
            color: var(--white);
            text-align: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border: 2px solid var(--accent-red);
        }
        
        /* Cards */
        .card {
            background: var(--light-gray);
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
            border: 1px solid #6B7280;
            margin-bottom: 1rem;
            color: var(--white) !important;
        }
        
        .stat-card {
            background: linear-gradient(135deg, var(--light-gray) 0%, var(--primary-black) 100%);
            border-radius: 10px;
            padding: 1.5rem;
            text-align: center;
            border: 2px solid var(--accent-red);
            color: var(--white) !important;
        }
        
        /* Radio buttons and checkboxes */
        .stRadio > div, .stCheckbox > div {
            background-color: var(--light-gray) !important;
            color: var(--white) !important;
        }
        
        /* File uploader refined */
        [data-testid="stFileUploadDropzone"] {
            background-color: #1F2937 !important;
            border: 2px dashed #4B5563 !important;
            border-radius: 12px !important;
            padding: 1.5rem !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            min-height: 120px !important;
        }

        [data-testid="stFileUploadDropzone"]:hover {
            border-color: var(--primary-green) !important;
            background-color: rgba(16, 185, 129, 0.1) !important;
        }
        
        /* Hide default text nodes */
        [data-testid="stFileUploadDropzone"] div[data-testid="stMarkdownContainer"] {
            display: none !important;
        }
        
        [data-testid="stFileUploadDropzone"] small {
            display: none !important;
        }

        /* Add clean Upload prompt */
        [data-testid="stFileUploadDropzone"]::before {
            content: "📤 Click to Upload";
            display: block;
            margin-bottom: 10px;
            font-size: 1.1rem;
            font-weight: 600;
            color: #FFFFFF;
        }
        </style>
        """, unsafe_allow_html=True)

# Initialize database
init_database()

# Text extraction functions
def extract_text_from_pdf(file):
    """Extract text from PDF file"""
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_docx(file):
    """Extract text from DOCX file"""
    doc = docx.Document(file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_text_from_image_with_vision(image_file) -> str:
    """
    Extract text from image using OpenAI Vision API
    Handles quoted API keys in .env file
    """
    import base64
    import os
    import re
    
    try:
        print("🖼️ Starting Vision AI extraction...")
        
        # STEP 1: Clear proxy environment variables
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        os.environ.pop('ALL_PROXY', None)
        
        # STEP 2: Load API key from .env file, handling quotes properly
        api_key = None
        
        if os.path.exists('.env'):
            print("📁 Found .env file, reading API key...")
            
            # Read the entire file content
            with open('.env', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find API key using regex that handles quotes and various formats
            patterns = [
                r'OPENAI_API_KEY\s*=\s*["\'](.+?)["\']',  # With quotes
                r'OPENAI_API_KEY\s*=\s*(.+?)\s*(?:#.*)?$',  # Without quotes (end of line)
                r'OPENAI_API_KEY\s*:\s*["\'](.+?)["\']',  # With colon separator
                r'OPENAI_API_KEY\s*:\s*(.+?)\s*(?:#.*)?$'   # With colon, no quotes
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
                if match:
                    api_key = match.group(1).strip()
                    print(f"✅ Found API key using pattern: {pattern[:30]}...")
                    break
        
        # If not found via regex, try simple line-by-line parsing
        if not api_key and os.path.exists('.env'):
            with open('.env', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and 'OPENAI_API_KEY' in line.upper():
                        # Handle various formats
                        if '=' in line:
                            key_part = line.split('=', 1)[1].strip()
                        elif ':' in line:
                            key_part = line.split(':', 1)[1].strip()
                        else:
                            continue
                        
                        # Remove quotes if present
                        api_key = key_part.strip('"\'')
                        print("✅ Found API key via line parsing")
                        break
        
        # Fallback to environment variable
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                # Clean quotes from env var too
                api_key = api_key.strip('"\'')
                print("✅ Using API key from environment variable")
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in .env file or environment")
        
        # Additional cleaning - remove any trailing/leading whitespace
        api_key = api_key.strip()
        
        # Debug output (masked for security)
        print(f"✅ API key length: {len(api_key)} characters")
        print(f"✅ API key starts with: {api_key[:12] if len(api_key) >= 12 else api_key}")
        print(f"✅ API key ends with: ...{api_key[-4:] if len(api_key) >= 4 else ''}")
        
        # Check if key still has quotes (shouldn't happen after our cleaning)
        if api_key.startswith('"') or api_key.startswith("'"):
            print("⚠️ Warning: API key still has leading quote")
            api_key = api_key[1:]
        if api_key.endswith('"') or api_key.endswith("'"):
            print("⚠️ Warning: API key still has trailing quote")
            api_key = api_key[:-1]
        
        # Final validation
        api_key = api_key.strip()
        if not api_key.startswith('sk-'):
            print(f"⚠️ API key format warning: Doesn't start with 'sk-'. Starts with: '{api_key[:10]}'")
        
        # STEP 3: Import OpenAI and create client
        import openai
        
        # Create client with the cleaned API key
        client = openai.OpenAI(api_key=api_key)
        
        # STEP 4: Process the image
        image_bytes = image_file.read()
        image_file.seek(0)  # Reset for potential re-use
        
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Determine image type
        file_extension = image_file.name.split('.')[-1].lower()
        mime_type = f"image/{file_extension}"
        if file_extension == 'jpg':
            mime_type = "image/jpeg"
        
        print(f"📸 Processing {file_extension.upper()} image...")
        
        # STEP 5: Call Vision API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Extract all text from this job description image.
                            
                            Return the complete job description text exactly as it appears.
                            Include:
                            - Job title
                            - Requirements
                            - Qualifications
                            - Responsibilities
                            - Any other details
                            
                            Format it clearly and preserve the structure."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.1
        )
        
        extracted_text = response.choices[0].message.content
        print(f"✅ Successfully extracted {len(extracted_text)} characters")
        
        return extracted_text
        
    except openai.AuthenticationError as auth_error:
        print(f"❌ Authentication failed!")
        print(f"❌ Error message: {auth_error}")
        
        # Debug: Show what the API key looks like
        if 'api_key' in locals():
            print(f"🔍 DEBUG - API key used (first/last chars): {api_key[:12]}...{api_key[-4:]}")
        
        raise Exception(f"Authentication failed. Please check your OpenAI API key format in .env file.")
        
    except Exception as e:
        print(f"❌ Vision API error: {type(e).__name__}: {str(e)}")
        raise Exception(f"Failed to extract text from image: {str(e)}")

def is_image_file(filename: str) -> bool:
    """Check if file is an image"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
    return any(filename.lower().endswith(ext) for ext in image_extensions)


def validate_image_size(image_file, max_size_mb: int = 20) -> bool:
    """Validate image file size (OpenAI limit is 20MB)"""
    try:
        # Get file size
        image_file.seek(0, 2)  # Seek to end
        size_bytes = image_file.tell()
        image_file.seek(0)  # Reset to beginning
        
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > max_size_mb:
            return False, f"Image size ({size_mb:.2f}MB) exceeds {max_size_mb}MB limit"
        
        return True, f"Image size: {size_mb:.2f}MB"
    except Exception as e:
        return False, f"Error checking image size: {str(e)}"
    
def clear_previous_files():
    """Clear ALL previously uploaded files and results"""
    folders_to_clear = ['data', 'output', 'temp']
    files_to_clear = [
        'job_description.txt',
        'interview_schedule.json',
        'candidate_ranking_report.json',
        'background_verification_report.json',
        'screening_results.json'
    ]
    
    for folder in folders_to_clear:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
            except Exception as e:
                pass
    
    for file in files_to_clear:
        if os.path.exists(file):
            try:
                os.remove(file)
            except Exception as e:
                pass
    
    stray_patterns = [
        '*.json', '*.pdf', '*.docx', '*.txt',
        '*.zip', '*.log', '*.csv', '*.ics'
    ]
    
    for pattern in stray_patterns:
        for file in glob.glob(pattern):
            essential_files = ['app.py', 'requirements.txt', '.env', '.gitignore']
            if not any(file.startswith(essential) for essential in essential_files):
                try:
                    os.remove(file)
                except:
                    pass
    
    for folder in ['data', 'output', 'temp']:
        os.makedirs(folder, exist_ok=True)

def process_resumes_zip(zip_file, extract_path="data/resumes_extracted"):
    """Process uploaded ZIP file and return list of resume files"""
    os.makedirs(extract_path, exist_ok=True)
    
    # Save ZIP file
    zip_path = os.path.join("data", "resumes.zip")
    with open(zip_path, "wb") as f:
        f.write(zip_file.getbuffer())
    
    # Extract ZIP
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
    
    # Get list of extracted resume files
    resume_files = []
    for root, dirs, files in os.walk(extract_path):
        for file in files:
            if file.lower().endswith(('.pdf', '.docx', '.txt')):
                resume_files.append(os.path.join(root, file))
    
    return len(resume_files), resume_files


# Legacy workflow analysis functions removed. 
# All reasoning now happens dynamically within the RecruitmentOrchestrator.

def run_recruitment_pipeline(job_description, resume_files, workflow_config_data):
    """Run recruitment pipeline with pre-determined workflow - NO RE-ANALYSIS"""
    try:
        # Import your actual pipeline modules
        from config.workflow_config import WorkflowConfig
        from orchestration import RecruitmentOrchestrator
        
        # Create a simple mock config object that the orchestrator expects
        class SimpleWorkflowConfig:
            def __init__(self, workflow_data):
                self.config = workflow_data
                self.ical_url = workflow_data.get('calendar_url')
                self.jd_text = job_description
                
            def get_job_title(self):
                return workflow_config_data.get('job_title', 'Position')
                
            def get_workflow_steps(self):
                steps = []
                if self.config.get("run_screening", True):
                    steps.append("screening")
                if self.config.get("run_background", False):
                    steps.append("background_check")
                if self.config.get("run_ranking", True):
                    steps.append("ranking")
                if self.config.get("run_scheduling", False):
                    steps.append("scheduling")
                if self.config.get("run_communication", False):
                    steps.append("communication")
                return steps
        
        # Create config for orchestrator - only include essential flags and raw analysis
        # The orchestrator will reason about the workflow at runtime
        workflow_config_for_orchestrator = {
            "description": "Dynamic ReAct workflow",
            "run_screening": True,  # Always start with screening
            "run_ranking": True,    # Always include ranking
            
            # Pass user preferences as constraints, not final decisions
            "run_background": workflow_config_data.get('needs_background_check', False),
            "run_scheduling": workflow_config_data.get('needs_interview', True),
            "run_communication": workflow_config_data.get('needs_interview', True),
            
            # Pass the full analysis for the orchestrator to reason with
            "jd_analysis": workflow_config_data.get('analysis_details', {}).get('semantic_analysis', 
                          workflow_config_data.get('analysis_details', {}).get('jd_analysis', {})),
            "semantic_decisions": workflow_config_data.get('analysis_details', {}).get('semantic_decisions', {}),
            "calendar_url": workflow_config_data.get('calendar_url'),
            
            # Flag to indicate if user explicitly requested just ranking
            "is_just_ranking": workflow_config_data.get('analysis_details', {}).get('semantic_analysis', {}).get('just_ranking', False)
        }
        
        config = SimpleWorkflowConfig(workflow_config_for_orchestrator)
        
        # Run the pipeline
        orchestrator = RecruitmentOrchestrator(config)
        
        # Apply nest_asyncio for async operations
        nest_asyncio.apply()
        
        # Run async pipeline
        result = asyncio.run(orchestrator.run_recruitment_pipeline())
        
        return result, config
        
    except ImportError as e:
        st.error(f"Pipeline modules not available: {e}")
        # Create mock result for demonstration
        return create_mock_result(len(resume_files), workflow_config_data), None
    except Exception as e:
        st.error(f"Error running recruitment pipeline: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None, None

def create_mock_result(resume_count, workflow_config):
    """Create mock result for demonstration"""
    candidates = []
    for i in range(min(10, resume_count)):
        candidates.append({
            'name': f"Candidate {i+1}",
            'email': f"candidate{i+1}@example.com",
            'phone': f"123-456-{7890+i:04d}",
            'score': round(7.0 + (i * 0.3), 1),
            'rank': i + 1,
            'status': 'scheduled' if (workflow_config.get('needs_interview') and i < 5) else 'eligible',
            'interview_date': f"2024-12-{15 + (i % 10)}" if (workflow_config.get('needs_interview') and i < 5) else '',
            'interview_time': f"{9 + (i % 5)}:00 AM" if (workflow_config.get('needs_interview') and i < 5) else '',
            'meeting_link': f"https://meet.google.com/abc-xyz-{i}" if (workflow_config.get('needs_interview') and i < 5) else ''
        })
    
    # Determine agents
    agents = ['Resume Screener', 'Candidate Ranker']
    if workflow_config.get('needs_interview'):
        agents.append('Interview Scheduler')
    if workflow_config.get('needs_background_check'):
        agents.append('Background Verifier')
    
    return {
        'candidates': candidates,
        'agents': agents,
        'summary': {
            'total_candidates': len(candidates),
            'scheduled': sum(1 for c in candidates if c.get('status') == 'scheduled'),
            'eligible': len(candidates),
            'emails_sent': sum(1 for c in candidates if c.get('status') == 'scheduled')
        }
    }

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'login'
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'result' not in st.session_state:
    st.session_state.result = None
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = {}
if 'current_session_id' not in st.session_state:
    st.session_state.current_session_id = None
if 'workflow_config' not in st.session_state:
    st.session_state.workflow_config = {}
if 'jd_analyzed' not in st.session_state:
    st.session_state.jd_analyzed = False
if 'analysis_displayed' not in st.session_state:
    st.session_state.analysis_displayed = False

# Clear files on app start
if 'files_cleared' not in st.session_state:
    clear_previous_files()
    st.session_state.files_cleared = True

# Navigation function
def navigate_to(page):
    """Navigate to a new page"""
    st.session_state.current_page = page
    st.rerun()

def show_login_page():
    """Show login page - Clean Green & White Theme"""
    load_css("login")
    
    st.markdown("""
    <style>
    /* Force all alert text to be black */
    .stAlert p, .stAlert h1, .stAlert h2, .stAlert h3, 
    .stAlert h4, .stAlert h5, .stAlert h6, .stAlert span, 
    .stAlert div {
        color: #000000 !important;
        font-weight: 600 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # App title
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="color: #10B981; font-size: 3rem; margin-bottom: 0.5rem;">HireIQ</h1>
            <p style="color: #059669; font-size: 1.2rem; font-weight: 500;">Smart Hiring, Zero Effort</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Login/Create Account Tabs
        tab1, tab2 = st.tabs(["Login", "Create Account"])
        
        with tab1:
            st.markdown("#### Login to Your Account")
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter username")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                
                login_submit = st.form_submit_button("Login", use_container_width=True, type="primary")
                
                if login_submit:
                    if not username or not password:
                        st.error("❌ Please enter both username and password")
                    else:
                        with st.spinner("Logging in..."):
                            try:
                                success, user_data = authenticate_user(username, password)
                                
                                if success and user_data:
                                    st.session_state.authenticated = True
                                    st.session_state.user = user_data
                                    st.session_state.current_page = "home"
                                    st.success("✅ Login successful!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Invalid username or password")
                            except Exception as e:
                                st.error(f"❌ Login error: {str(e)}")
        
        with tab2:
            st.markdown("#### Create New Account")
            with st.form("register_form"):
                new_username = st.text_input("Username", placeholder="Choose username", key="reg_username")
                email = st.text_input("Email", placeholder="email@company.com", key="reg_email")
                company_name = st.text_input("Company Name", placeholder="Company name", key="reg_company")
                new_password = st.text_input("Password", type="password", placeholder="Create password (min 8 characters)", key="reg_password")
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm password", key="reg_confirm")
                
                register_submit = st.form_submit_button("Create Account", use_container_width=True, type="primary")
                
                if register_submit:
                    # Basic validation
                    if not new_username or not email or not company_name or not new_password or not confirm_password:
                        st.error("❌ All fields are required")
                    elif len(new_password) < 8:
                        st.error("❌ Password must be at least 8 characters")
                    elif new_password != confirm_password:
                        st.error("❌ Passwords do not match")
                    elif ' ' in new_username:
                        st.error("❌ Username cannot contain spaces")
                    else:
                        # Validate email format
                        import re
                        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                        if not re.match(email_pattern, email):
                            st.error("❌ Please enter a valid email address")
                        else:
                            with st.spinner("Creating your account..."):
                                try:
                                    # Call the actual database function
                                    success, message = create_user(new_username, email, company_name, new_password)
                                    
                                    if success:
                                        st.success("✅ Account created successfully!")
                                        st.info("You can now login with your username and password")
                                        # Auto-switch to login tab after 2 seconds
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                                except Exception as e:
                                    st.error(f"❌ Error creating account: {str(e)}")

def show_home_page():
    """Show home page - Clean Black Theme"""
    load_css("other")
    
    if not st.session_state.authenticated:
        navigate_to("login")
        return
    
    # Top navigation
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### Welcome, {st.session_state.user['username']}")
    with col2:
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.current_page = "login"
            st.rerun()
    
    # Main content
    st.markdown("""
    <div class="black-header">
        <h1 style="margin: 0; font-size: 2.5rem;">HireIQ: Smart Hiring, Zero Effort</h1>
        <p style="margin: 1rem 0 0 0; font-size: 1.1rem; line-height: 1.5;">
            HireIQ revolutionizes recruitment by leveraging advanced AI agents to streamline the entire hiring process. Our intelligent system automatically screens resumes, verifies candidate backgrounds, ranks top talent, and schedules interviews directly into your calendar. With configurable workflows and real-time calendar integration, we eliminate manual tasks and reduce hiring time, helping companies find the perfect candidates faster and more efficiently than ever before.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ New Recruitment", use_container_width=True, type="primary"):
            navigate_to("new_recruitment")
    with col2:
        if st.button("📋 Previous Sessions", use_container_width=True):
            navigate_to("previous_sessions")
    
# Add this to your app.py - Modified new_recruitment_page function

# Add this to your app.py - Modified new_recruitment_page with chat interface

def show_new_recruitment_page():
    """Show new recruitment process with CHAT-BASED JD confirmation"""
    load_css("other")
    
    if not st.session_state.authenticated:
        navigate_to("login")
        return
    
    # Back button
    if st.button("← Back to Home"):
        navigate_to("home")
        # Reset all states
        st.session_state.recruitment_step = 1
        st.session_state.chat_session = None
        st.session_state.chat_messages = []
        st.session_state.workflow_config = {}
    
    st.markdown("""
    <div class="black-header">
        <h2 style="margin: 0;">New Recruitment Process</h2>
        <p style="margin: 0.5rem 0 0 0;">Upload files and chat with AI to configure your recruitment</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize states
    if 'recruitment_step' not in st.session_state:
        st.session_state.recruitment_step = 1
    if 'chat_session' not in st.session_state:
        st.session_state.chat_session = None
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    # ============================================================
    # STEP 1: Upload Files
    # ============================================================
    if st.session_state.recruitment_step == 1:
        st.markdown("### Upload Requirements")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📄 Job Description")
            jd_option = st.radio(
                "Select input method:", 
                ["Upload File", "Upload Image", "Enter Text"], 
                horizontal=True, 
                key="jd_option",
                label_visibility="collapsed"
            )
            
            if jd_option == "Upload File":
                jd_file = st.file_uploader(
                    "Upload Job Description", 
                    type=["pdf", "docx", "txt"], 
                    key="jd_file_uploader",
                    label_visibility="collapsed"
                )
                if jd_file:
                    with st.spinner("📄 Extracting..."):
                        try:
                            if jd_file.type == "application/pdf":
                                job_description = extract_text_from_pdf(jd_file)
                            elif jd_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                                job_description = extract_text_from_docx(jd_file)
                            else:
                                job_description = jd_file.read().decode("utf-8")
                            
                            st.session_state.uploaded_files['job_description'] = job_description
                            st.session_state.uploaded_files['jd_filename'] = jd_file.name
                            st.success(f"✅ Extracted")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
            
            elif jd_option == "Upload Image":
                jd_image = st.file_uploader(
                    "Upload Image", 
                    type=["jpg", "jpeg", "png", "webp"], 
                    key="jd_image_uploader",
                    label_visibility="collapsed"
                )
                
                if jd_image:
                    st.image(jd_image, caption="JD Image", use_container_width=True)
                    
                    # Automate extraction if new image
                    if st.session_state.uploaded_files.get('jd_filename') != jd_image.name:
                        with st.spinner("🤖 Reading image..."):
                            try:
                                job_description = extract_text_from_image_with_vision(jd_image)
                                st.session_state.uploaded_files['job_description'] = job_description
                                st.session_state.uploaded_files['jd_filename'] = jd_image.name
                                st.success(f"✅ Extracted")
                            except Exception as e:
                                st.error(f"❌ Failed: {e}")
            
            else:  # Enter Text
                job_description = st.text_area(
                    "Paste text here:", 
                    height=200, 
                    key="jd_textarea",
                    label_visibility="collapsed"
                )
                if job_description:
                    st.session_state.uploaded_files['job_description'] = job_description
                    st.session_state.uploaded_files['jd_filename'] = "Manual Input"
        
        with col2:
            st.markdown("### 👥 Candidate Resumes")
            
            uploaded_zip = st.file_uploader(
                "Upload Resume ZIP", 
                type=["zip"], 
                key="resume_uploader",
                label_visibility="collapsed"
            )
            
            if uploaded_zip:
                st.session_state.uploaded_files['resumes_zip'] = uploaded_zip
                st.session_state.uploaded_files['zip_filename'] = uploaded_zip.name
                
                try:
                    with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                        file_list = zip_ref.namelist()
                        resume_files = [f for f in file_list if f.lower().endswith(('.pdf', '.docx', '.txt'))]
                        st.success(f"✅ {len(resume_files)} resumes found")
                except:
                    st.error("❌ Invalid ZIP")
            
            st.info("💡 Tip: ZIP all resumes into one folder.")
        
        # Recruitment Goal selection (Horizontal radio, no labels)
        st.markdown("---")
        recruitment_goal = st.radio(
            "Recruitment Goal",
            ["Interview Schedule Need", "Just Ranking"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
            key="recruitment_goal_step1"
        )
        is_ranking_only = recruitment_goal == "Just Ranking"
        
        # Navigation Buttons
        st.markdown("---")
        col_cancel, col_chat, col_direct = st.columns([1, 2, 2])
        
        with col_cancel:
            if st.button("Cancel", use_container_width=True, key="cancel_recruitment_step1"):
                navigate_to("home")
        
        has_jd = 'job_description' in st.session_state.uploaded_files
        has_resumes = 'resumes_zip' in st.session_state.uploaded_files
        
        with col_chat:
            if st.button("Interactive Chat Review 💬", type="secondary", use_container_width=True,
                         disabled=not (has_jd and has_resumes), key="chat_review_btn"):
                # Initialize chat session
                job_description = st.session_state.uploaded_files.get('job_description')
                with st.spinner("🤖 Starting AI chat assistant..."):
                    try:
                        from chat_jd_confirmation import JDConfirmationChat
                        chat = JDConfirmationChat()
                        
                        # Set initial preferences from Step 1
                        chat.is_just_ranking = is_ranking_only
                        chat.needs_scheduling = not is_ranking_only
                        
                        greeting = chat.start_conversation(job_description)
                        st.session_state.chat_session = chat
                        st.session_state.chat_messages = [{"role": "assistant", "content": greeting}]
                        st.session_state.recruitment_step = 2
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error starting chat: {e}")

        with col_direct:
            if st.button("No Further Review Process 🚀", type="primary", use_container_width=True,
                         disabled=not (has_jd and has_resumes), key="direct_extra_btn"):
                # Automatic Extraction Bypass
                job_description = st.session_state.uploaded_files.get('job_description')
                with st.spinner("🤖 Automating extraction & configuration..."):
                    try:
                        from src.utils.jd_analyzer import extract_jd_details, analyze_with_confirmation
                        
                        # 1. Extract details
                        extracted_data = extract_jd_details(job_description)
                        
                        # 2. Analyze & Configure Workflow (respect user preference from Step 1)
                        workflow_config = analyze_with_confirmation(
                            extracted_data,
                            is_just_ranking=is_ranking_only,
                            needs_scheduling=not is_ranking_only
                        )
                        
                        # Add job title if missing
                        if 'job_title' not in workflow_config:
                            workflow_config['job_title'] = extracted_data.get('job_title', 'Position')
                        
                        # 3. Store in session state (Add 'needs_interview' alias for UI consistency)
                        workflow_config['needs_interview'] = workflow_config.get('needs_scheduling', False)
                        st.session_state.workflow_config = workflow_config
                        
                        # 4. Skip Step 2, go straight to 3 or 4 based on analysis
                        if workflow_config.get('needs_interview', False):
                            st.session_state.recruitment_step = 3
                        else:
                            st.session_state.recruitment_step = 4
                            
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error in direct extraction: {e}")
                        import traceback
                        st.error(traceback.format_exc())
        
        # User Guidance Text
        st.markdown("""
        <div style="text-align: center; color: #9CA3AF; font-size: 0.9rem; margin-top: 15px; padding: 0 10% 10px 10%;">
            Choose <b>Interactive Chat Review</b> to manually verify recruitment details with AI, 
            or <b>No Further Review Process</b> to start immediately using automated extraction.
        </div>
        """, unsafe_allow_html=True)
    
    # ============================================================
    # STEP 2: Chat-based JD Confirmation
    # ============================================================
    elif st.session_state.recruitment_step == 2:
        st.markdown("### Confirm Details with AI Chat")
        
        # Chat container
        chat_container = st.container()
        
        with chat_container:
            # Display chat history
            for message in st.session_state.chat_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        
        # Check if chat is complete
        if st.session_state.chat_session and st.session_state.chat_session.is_complete():
            st.success("✅ Configuration complete! Ready to start recruitment process.")
            
            # Get workflow config
            workflow_config = st.session_state.chat_session.get_workflow_config()
            st.session_state.workflow_config = workflow_config
            
            # Show next steps
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("← Start Over"):
                    st.session_state.recruitment_step = 1
                    st.session_state.chat_session = None
                    st.session_state.chat_messages = []
                    st.rerun()
            
            with col2:
                # Check if needs interview setup
                if workflow_config.get('needs_interview', False):
                    if st.button("Next → Interview Setup", type="primary", use_container_width=True):
                        st.session_state.recruitment_step = 3
                        st.rerun()
                else:
                    if st.button("🚀 Start Process", type="primary", use_container_width=True):
                        st.session_state.recruitment_step = 4
                        st.rerun()
        
        else:
            # Chat input
            user_input = st.chat_input("Type your response here...")
            
            if user_input:
                # Add user message to display
                st.session_state.chat_messages.append({
                    "role": "user",
                    "content": user_input
                })
                
                # Process message
                if st.session_state.chat_session:
                    response = st.session_state.chat_session.process_user_message(user_input)
                    
                    # Add assistant response
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": response
                    })
                
                st.rerun()
            
            # Back button at bottom
            st.markdown("---")
            if st.button("← Back to Files", key="back_from_chat"):
                st.session_state.recruitment_step = 1
                st.session_state.chat_session = None
                st.session_state.chat_messages = []
                st.rerun()
    
    # ============================================================
    # STEP 3: Interview Setup (only if needed)
    # ============================================================
    elif st.session_state.recruitment_step == 3:
        if st.session_state.workflow_config.get('needs_interview'):
            st.markdown("### Interview Setup")
            
            col1, col2 = st.columns(2)
            
            with col1:
                interview_mode = st.radio("Interview Mode:", ["Online", "In-person"], horizontal=True, key="interview_mode")
                
                if interview_mode == "In-person":
                    location = st.text_input("Location:", placeholder="Office address", key="location")
                else:
                    location = ""
            
            with col2:
                calendar_url = st.text_input(
                    "Google Calendar URL:",
                    placeholder="https://calendar.google.com/calendar/ical/...",
                    help="Required for scheduling interviews",
                    key="calendar_url"
                )
            
            # Navigation
            st.markdown("---")
            col_prev, col_next = st.columns(2)
            with col_prev:
                back_label = "← Back to Chat" if st.session_state.chat_session else "← Back to Files"
                if st.button(back_label, key="step3_back_btn"):
                    st.session_state.recruitment_step = 2 if st.session_state.chat_session else 1
                    st.rerun()
            
            with col_next:
                disabled = not calendar_url
                if st.button("Next → Start Process", type="primary", use_container_width=True, 
                            disabled=disabled, key="step3_next_btn"):
                    st.session_state.workflow_config['interview_mode'] = "online" if interview_mode == "Online" else "in_person"
                    st.session_state.workflow_config['location'] = location
                    st.session_state.workflow_config['calendar_url'] = calendar_url
                    st.session_state.recruitment_step = 4
                    st.rerun()
        else:
            # Skip to process start
            st.session_state.recruitment_step = 4
            st.rerun()
    
    # ============================================================
    # STEP 4: Start Recruitment Process
    # ============================================================
    elif st.session_state.recruitment_step == 4:
        st.markdown("### Final Review & Start")
        
        # Get confirmed data (check chat session first, then workflow config)
        if st.session_state.chat_session:
            confirmed_data = st.session_state.chat_session.confirmed_data
        elif st.session_state.workflow_config:
            confirmed_data = st.session_state.workflow_config.get('confirmed_jd_data', {})
        else:
            confirmed_data = {}
        
        # Show summary
        st.markdown("**📋 Confirmed Job Details**")
        st.info(f"""
        **Job Title:** {confirmed_data.get('job_title', 'N/A')}
        
        **Experience:** {confirmed_data.get('experience', 'N/A')}
        
        **Location:** {confirmed_data.get('work_location', 'N/A')}
        
        **Requirements:** {len(confirmed_data.get('requirements', []))} items
        
        **Qualifications:** {len(confirmed_data.get('qualifications', []))} items
        
        **Process Type:** {"Just Ranking" if st.session_state.workflow_config.get('just_ranking') else "Interview Schedule Need"}
        """)
        
        # Navigation
        st.markdown("---")
        col_prev, col_next = st.columns([1, 2])
        
        with col_prev:
            if st.button("← Back", key="back_to_prev_step"):
                # Go back to Step 3 if interview enabled, else Step 1
                if st.session_state.workflow_config.get('needs_interview') and st.session_state.chat_session:
                    st.session_state.recruitment_step = 3
                else:
                    st.session_state.recruitment_step = 1
                st.rerun()
        
        with col_next:
            if st.button("🚀 Start AI Recruitment Process", type="primary", 
                        use_container_width=True, disabled=st.session_state.processing,
                        key="start_recruitment_btn"):
                
                st.session_state.processing = True
                
                # [Insert your existing recruitment pipeline code here]
                # Same as before - process resumes, run pipeline, save to database, etc.
                with st.spinner("Starting recruitment process..."):
                    try:
                        # Clear previous files
                        clear_previous_files()
                        
                        # Get uploaded files
                        job_description = st.session_state.uploaded_files.get('job_description')
                        uploaded_zip = st.session_state.uploaded_files.get('resumes_zip')
                        
                        if not job_description or not uploaded_zip:
                            st.error("Missing required files")
                            st.session_state.processing = False
                            return
                        
                        # Process resumes
                        resume_count, resume_files = process_resumes_zip(uploaded_zip)
                        
                        if resume_count == 0:
                            st.error("No valid resume files found")
                            st.session_state.processing = False
                            return
                        
                        st.info(f"Processing {resume_count} resumes...")
                        
                        # Create session folder
                        session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        job_title_slug = st.session_state.workflow_config.get('job_title', 'Position').replace(' ', '_').replace('/', '_')[:50]
                        user_id = st.session_state.user['id']
                        
                        session_folder = f"session_{user_id}_{job_title_slug}_{session_timestamp}"
                        
                        # Create directories
                        os.makedirs(session_folder, exist_ok=True)
                        os.makedirs(f"{session_folder}/data", exist_ok=True)
                        os.makedirs(f"{session_folder}/output", exist_ok=True)
                        
                        # Save job description
                        with open(f"{session_folder}/job_description.txt", "w", encoding="utf-8") as f:
                            f.write(job_description)
                        
                        with open("job_description.txt", "w", encoding="utf-8") as f:
                            f.write(job_description)
                        
                        # Run recruitment pipeline
                        result, config = run_recruitment_pipeline(
                            job_description, 
                            resume_files,
                            st.session_state.workflow_config
                        )
                        
                        if not result or not isinstance(result, dict):
                            st.error("Recruitment process failed")
                            st.session_state.processing = False
                            return
                        
                        # Save to database
                        session_name = f"{st.session_state.workflow_config.get('job_title', 'Position')} - {datetime.now().strftime('%Y-%m-%d')}"
                        
                        result_for_db = {
                            'summary': result.get('summary', {}),
                            'candidates': result.get('candidates', []),
                            'agents': result.get('agents', []),
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        session_id = save_session_to_db(
                            user_id=st.session_state.user['id'],
                            session_name=session_name,
                            job_description=job_description,
                            job_title=st.session_state.workflow_config.get('job_title', 'Position'),
                            resume_count=resume_count,
                            workflow_config=st.session_state.workflow_config,
                            results_data=result_for_db
                        )
                        
                        if session_id:
                            # Rename folder
                            new_session_folder = f"session_{session_id}_{job_title_slug}_{session_timestamp}"
                            try:
                                os.rename(session_folder, new_session_folder)
                                session_folder = new_session_folder
                            except:
                                pass
                            
                            # Copy output files
                            output_folder = os.path.join(session_folder, "output")
                            output_files_to_copy = [
                                ('screening_results.json', 'screening_results.json'),
                                ('candidate_ranking_report.json', 'ranking_results.json'),
                                ('interview_schedule.json', 'schedule_results.json'),
                                ('background_verification_report.json', 'background_results.json')
                            ]
                            
                            for src_file, dst_file in output_files_to_copy:
                                src_path = os.path.join('output', src_file)
                                dst_path = os.path.join(output_folder, dst_file)
                                if os.path.exists(src_path):
                                    try:
                                        shutil.copy2(src_path, dst_path)
                                    except:
                                        pass
                            
                            # Save candidates
                            candidates_to_save = result.get('candidates', [])
                            if candidates_to_save:
                                enhanced_candidates = []
                                for candidate in candidates_to_save:
                                    if isinstance(candidate, dict):
                                        enhanced_candidates.append({
                                            'name': candidate.get('name', ''),
                                            'email': candidate.get('email', ''),
                                            'phone': candidate.get('phone', ''),
                                            'score': candidate.get('score', 0),
                                            'rank': candidate.get('rank', 0),
                                            'status': candidate.get('status', ''),
                                            'interview_date': candidate.get('interview_date', ''),
                                            'interview_time': candidate.get('interview_time', ''),
                                            'meeting_link': candidate.get('meeting_link', '')
                                        })
                                
                                if enhanced_candidates:
                                    save_candidates_to_db(session_id, enhanced_candidates)
                        
                        # Update state
                        st.session_state.current_session_id = session_id
                        st.session_state.processing = False
                        st.session_state.result = result
                        
                        st.success("✅ Process completed successfully!")
                        time.sleep(1)
                        navigate_to("results")
                        
                    except Exception as e:
                        st.error(f"Process failed: {e}")
                        import traceback
                        st.error(traceback.format_exc())
                        st.session_state.processing = False

def load_actual_output_files():
    """Load actual output files from the output folder"""
    output_files = {}
    
    # Define possible output files
    possible_files = {
        'screening_results.json': 'screening',
        'candidate_ranking_report.json': 'ranking',
        'interview_schedule.json': 'scheduling',  # This is the key file
        'background_verification_report.json': 'background'
    }
    
    # Create output directory if it doesn't exist
    if not os.path.exists('output'):
        os.makedirs('output')
    
    # Load each file if it exists
    for filename, key in possible_files.items():
        filepath = os.path.join('output', filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    output_files[key] = json.load(f)
            except Exception as e:
                st.error(f"Error loading {filename}: {e}")
                output_files[key] = None
        else:
            output_files[key] = None
    
    return output_files

def show_results_page():
    """Show recruitment results with Final Output first, then agent-specific tabs"""
    load_css("other")
    
    if not st.session_state.authenticated:
        navigate_to("login")
        return
    
    # Navigation
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### Recruitment Results")
    with col2:
        if st.button("← Back to Home"):
            navigate_to("home")
            st.session_state.result = None
    
    # Load actual output files
    output_files = load_actual_output_files()
    
    
    # Get workflow configuration
    workflow_config = st.session_state.workflow_config.get('workflow_data', {})
    
    # Determine which agents were used based on ACTUAL output files present
    agents_used = []
    
    # Check for screening results
    if output_files.get('screening'):
        agents_used.append('Resume Screener')
    
    # Check for ranking results
    if output_files.get('ranking'):
        agents_used.append('Candidate Ranker')
        
    # Check for scheduling results
    if output_files.get('scheduling'):
        agents_used.append('Interview Scheduler')
    
    # Check for background results - This fixes the missing background tab issue
    if output_files.get('background'):
        agents_used.append('Background Verifier')
    
        # ================================================
    # CALENDAR UPLOAD FOR RESCHEDULING - ONLY WHEN NEEDED
    # ================================================
    if 'Interview Scheduler' in agents_used:
        # Check scheduling status first
        scheduling_data = output_files.get('scheduling')
        ranking_data = output_files.get('ranking')
        
        # Calculate if more slots are needed
        need_more_slots = False
        scheduled_count = 0
        ranked_count = 0
        
        # Get scheduled interviews count
        if scheduling_data and isinstance(scheduling_data, dict):
            interviews = scheduling_data.get('scheduled_interviews', [])
            if not interviews and 'interviews' in scheduling_data:
                interviews = scheduling_data.get('interviews', [])
            
            if isinstance(interviews, list):
                scheduled_count = len(interviews)
        
        # Get ranked candidates count
        if ranking_data and isinstance(ranking_data, dict):
            candidates = ranking_data.get('candidates', ranking_data.get('ranked_candidates', []))
            if isinstance(candidates, list):
                # Count only candidates with valid ranks
                ranked_count = sum(1 for c in candidates if isinstance(c, dict) and c.get('rank') is not None and c.get('rank') != 'N/A')
        
        # Determine if more slots are needed
        if ranked_count > 0 and scheduled_count < ranked_count:
            need_more_slots = True
        
        # Only show calendar upload if more slots are needed
        if need_more_slots:
            st.markdown("---")
            with st.expander("📅 Need More Interview Slots?", expanded=True):
                st.markdown("### ⚠️ Calendar Slots Needed")
                
                # Show current status
                st.warning(f"**{scheduled_count} of {ranked_count} ranked candidates have been scheduled**")
                st.info(f"**{ranked_count - scheduled_count} more interview slots needed**")
                
                # Current calendar info
                current_calendar = st.session_state.workflow_config.get('calendar_url', 'Not provided')
                st.info(f"**Current Calendar:** {current_calendar[:50]}..." if current_calendar and len(current_calendar) > 50 else f"**Current Calendar:** {current_calendar}")
                
                # Upload new calendar for rescheduling
                st.markdown("---")
                st.markdown("#### 📤 Upload New Calendar with More Available Slots")
                
                # Input for new calendar URL
                new_calendar_url = st.text_input(
                    "New Google Calendar iCal URL:",
                    placeholder="https://calendar.google.com/calendar/ical/.../basic.ics",
                    help="Get from Google Calendar → Settings → Specific calendar → Integrate calendar",
                    key="new_calendar_url_input"
                )
                
                if new_calendar_url:
                    # Validate URL
                    if not new_calendar_url.startswith(('http://', 'https://')):
                        st.error("❌ Please enter a valid URL starting with http:// or https://")
                    else:
                        st.success("✅ Valid URL format detected")
                        
                        # Rescheduling button
                        st.markdown("---")
                        if st.button("🚀 Run Rescheduling with New Calendar", 
                                    type="primary", 
                                    use_container_width=True):
                            
                            with st.spinner("🔄 Running rescheduling with new calendar..."):
                                try:
                                    # Create calendar agent instance
                                    calendar_agent = CalendarSchedulingAgent(new_calendar_url)
                                    
                                    # Run rescheduling
                                    reschedule_result = asyncio.run(
                                        calendar_agent.update_calendar_and_continue(
                                            new_calendar_url=new_calendar_url,
                                            interview_mode=st.session_state.workflow_config.get('interview_mode', 'online')
                                        )
                                    )
                                    
                                    if reschedule_result and reschedule_result.get('status') == 'complete':
                                        st.success("✅ Rescheduling completed successfully!")
                                        
                                        # Update workflow config with new calendar URL
                                        st.session_state.workflow_config['calendar_url'] = new_calendar_url
                                        
                                        # ================================================
                                        # FIX: Save updated scheduling data to session folder
                                        # ================================================
                                        current_session_id = st.session_state.current_session_id
                                        if current_session_id:
                                            # Find session folder
                                            import glob
                                            session_folders = glob.glob(f"session_{current_session_id}_*")
                                            if session_folders:
                                                session_folder = session_folders[0]
                                                output_folder = os.path.join(session_folder, "output")
                                                os.makedirs(output_folder, exist_ok=True)
                                                
                                                # Copy the updated schedule file
                                                updated_schedule_file = "output/interview_schedule.json"
                                                if os.path.exists(updated_schedule_file):
                                                    import shutil
                                                    dest_file = os.path.join(output_folder, "schedule_results.json")
                                                    shutil.copy2(updated_schedule_file, dest_file)
                                                    print(f"✅ Updated schedule saved to: {dest_file}")


                                        # Refresh results
                                        st.info("🔄 Refreshing to show updated results...")
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        error_msg = reschedule_result.get('message', 'Unknown error') if reschedule_result else 'No result returned'
                                        st.error(f"❌ Rescheduling failed: {error_msg}")
                                
                                except Exception as e:
                                    st.error(f"❌ Error during rescheduling: {str(e)}")
                                    import traceback
                                    st.error(traceback.format_exc())
        else:
            # All slots are scheduled, show success message
            if scheduled_count > 0 and scheduled_count >= ranked_count:
                st.markdown("---")
                st.success(f"✅ **All {ranked_count} ranked candidates have been scheduled!** No additional calendar slots needed.")
    
        # ================================================
    # PROCESS CANDIDATE DATA FOR FINAL OUTPUT
    # ================================================
    all_candidates_data = {}

    # 1. Get ranking data FIRST - we only care about RANKED candidates
    ranking_data = output_files.get('ranking')
    if ranking_data and isinstance(ranking_data, dict):
        # Handle both 'ranked_candidates' and 'candidates' keys
        ranked_candidates = ranking_data.get('ranked_candidates', ranking_data.get('candidates', []))
        
        if isinstance(ranked_candidates, list):
            for candidate in ranked_candidates:
                if isinstance(candidate, dict):
                    name = candidate.get('name', '').strip()
                    email = candidate.get('email', '').strip()
                    rank = candidate.get('rank')
                    
                    # ONLY process candidates with a valid rank (not N/A)
                    if name and rank is not None and rank != 'N/A':
                        try:
                            # Convert rank to integer if possible
                            rank_int = int(rank)
                            all_candidates_data[email or name] = {
                                'name': name,
                                'email': email,
                                'rank': rank_int,
                                'status': 'eligible'  # Default status
                            }
                        except (ValueError, TypeError):
                            # Skip if rank is not a valid number
                            continue

    # 2. Get scheduling data (if available) - only for RANKED candidates
    scheduling_data = output_files.get('scheduling')
    if scheduling_data and isinstance(scheduling_data, dict):
        interviews = scheduling_data.get('scheduled_interviews', [])
        if not interviews and 'interviews' in scheduling_data:
            interviews = scheduling_data.get('interviews', [])
        
        if isinstance(interviews, list):
            for interview in interviews:
                if isinstance(interview, dict):
                    name = interview.get('candidate_name', '').strip()
                    email = interview.get('candidate_email', '').strip()
                    
                    key = email or name
                    if key in all_candidates_data:  # Only update if candidate is in our ranked list
                        all_candidates_data[key].update({
                            'interview_date': interview.get('interview_date', ''),
                            'interview_time': interview.get('interview_time', ''),
                            'meeting_link': interview.get('meeting_link', ''),
                            'status': 'scheduled'
                        })

    # 3. If no ranked candidates found, check screening data as fallback (but only for eligible)
    if not all_candidates_data:
        screening_data = output_files.get('screening')
        if screening_data and isinstance(screening_data, dict) and 'eligible_candidates' in screening_data:
            eligible_candidates = screening_data.get('eligible_candidates', [])
            for candidate in eligible_candidates:
                if isinstance(candidate, dict):
                    candidate_info = candidate.get('candidate_info', {})
                    name = candidate_info.get('name', '').strip()
                    email = candidate_info.get('email', '').strip()
                    
                    if name:
                        all_candidates_data[email or name] = {
                            'name': name,
                            'email': email,
                            'rank': 'N/A',
                            'status': 'eligible'
                        }
    # ================================================
    # CREATE TABS
    # ================================================
    tab_names = ['Final Output']
    
    # Add agent tabs based on what was used
    for agent in agents_used:
        if agent == "Resume Screener":
            tab_names.append("Screening")
        elif agent == "Candidate Ranker":
            tab_names.append("Ranking")
        elif agent == "Interview Scheduler":
            tab_names.append("Scheduling")
        elif agent == "Background Verifier":
            tab_names.append("Background Check")
    
    # Create tabs
    tabs = st.tabs(tab_names)
    
        # ================================================
    # FINAL OUTPUT TAB - FIXED VERSION
    # ================================================
    with tabs[0]:
        st.markdown("## Final Output")
        
        if all_candidates_data:
            # Prepare ALL candidates for display
            display_data = []
            
            for candidate_id, candidate_info in all_candidates_data.items():
                name = candidate_info.get('name', '').strip()
                email = candidate_info.get('email', '').strip()
                rank = candidate_info.get('rank', 'N/A')
                status = candidate_info.get('status', 'eligible')
                
                if not name:
                    continue
                
                # Create base row
                row = {
                    'Name': name,
                    'Email': email,
                    'Rank': rank,
                    'Status': status
                }
                
                # Add interview details if available
                if 'interview_date' in candidate_info and candidate_info['interview_date']:
                    row['Interview Date'] = candidate_info.get('interview_date', '')
                    row['Interview Time'] = candidate_info.get('interview_time', '')
                    row['Meeting Link'] = candidate_info.get('meeting_link', '')
                    row['Status'] = 'scheduled'
                
                # If rank is "N/A" but candidate is eligible, keep as eligible
                if rank == 'N/A' and 'interview_date' not in candidate_info:
                    row['Status'] = 'eligible'
                
                display_data.append(row)
            
            if display_data:
                # Sort by: 1. Has interview, 2. Valid rank, 3. Name
                def sort_key(candidate):
                    # First: Scheduled candidates (have interview date)
                    has_interview = 'Interview Date' in candidate and candidate['Interview Date']
                    # Second: Rank (numeric first, then "N/A")
                    rank_val = candidate.get('Rank')
                    if isinstance(rank_val, (int, float)):
                        rank_order = (0, rank_val)  # Numeric ranks come first
                    else:
                        rank_order = (1, 0)  # "N/A" ranks come after
                    # Third: Name for alphabetical ordering
                    return (not has_interview, rank_order, candidate.get('Name', '').lower())
                
                display_data.sort(key=sort_key)
                
                # Display table
                st.markdown("### Final Evaluation")
                df = pd.DataFrame(display_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Summary statistics - FIXED COUNTS
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    total_candidates = len(display_data)
                    st.metric("Total Candidates", total_candidates)
                
                with col2:
                    scheduled = sum(1 for c in display_data if c.get('Status') == 'scheduled')
                    st.metric("Interviews Scheduled", scheduled)
                
                with col3:
                    ranked = sum(1 for c in display_data if isinstance(c.get('Rank'), (int, float)))
                    st.metric("Ranked Candidates", ranked)
                
                # Also show job title
                st.markdown(f"**Job Title:** {st.session_state.workflow_config.get('job_title', 'Position')}")
        # ================================================
    # OTHER TABS (Screening, Ranking, Scheduling, Background)
    # ================================================
    # [Rest of your tab code remains here...]
    # Make sure to continue with the rest of your tab implementations
        
    tab_index = 1
        # Screening Tab
    if "Resume Screener" in agents_used and tab_index < len(tabs):
        with tabs[tab_index]:
            st.markdown("## Screening Results")
            
            screening_data = output_files.get('screening')
            
            if screening_data and isinstance(screening_data, dict):
                # Get summary
                summary = screening_data.get('summary', {})
                total_screened = summary.get('total_screened', 0)
                eligible_count = summary.get('eligible_count', 0)
                ineligible_count = summary.get('ineligible_count', 0)
                
                # Display summary metrics
                st.markdown("### 📊 Summary")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Screened", total_screened)
                with col2:
                    st.metric("✅ Eligible", eligible_count)
                with col3:
                    st.metric("❌ Ineligible", ineligible_count)
                
                # Get candidate lists
                eligible_candidates_list = screening_data.get('eligible_candidates', [])
                ineligible_candidates_list = screening_data.get('ineligible_candidates', [])
                
                # Display ELIGIBLE candidates
                st.markdown("---")
                st.markdown("### ✅ Eligible Candidates")
                
                if eligible_candidates_list and isinstance(eligible_candidates_list, list):
                    if len(eligible_candidates_list) > 0:
                        # Extract names from eligible candidates
                        eligible_names = []
                        eligible_details = []  # Store full details for table
                        
                        for candidate in eligible_candidates_list:
                            if isinstance(candidate, dict):
                                # Get name from candidate_info
                                name = None
                                if 'candidate_info' in candidate and isinstance(candidate['candidate_info'], dict):
                                    candidate_info = candidate['candidate_info']
                                    if 'name' in candidate_info and candidate_info['name']:
                                        name = candidate_info['name'].strip()
                                
                                # Also get other details
                                email = ""
                                experience = ""
                                reason = candidate.get('reason', '')
                                
                                if 'candidate_info' in candidate and isinstance(candidate['candidate_info'], dict):
                                    email = candidate['candidate_info'].get('email', '')
                                    experience = candidate['candidate_info'].get('total_experience', '')
                                
                                # Get skills summary
                                skills = []
                                if 'skills_summary' in candidate and isinstance(candidate['skills_summary'], dict):
                                    skills_list = candidate['skills_summary'].get('skills', [])
                                    if isinstance(skills_list, list):
                                        skills = skills_list
                                
                                if name:
                                    # Clean the name - capitalize properly
                                    name = ' '.join(word.capitalize() for word in name.split())
                                    eligible_names.append(name)
                                    
                                    # Add to details for table
                                    eligible_details.append({
                                        'Name': name,
                                        'Email': email,
                                        'Experience': experience,
                                        'Skills': ', '.join(skills[:3]) + ('...' if len(skills) > 3 else ''),
                                        'Reason': reason[:50] + '...' if len(reason) > 50 else reason
                                    })
                        
                        if eligible_details:
                            # Display as table
                            df_eligible = pd.DataFrame(eligible_details)
                            st.dataframe(df_eligible, use_container_width=True, hide_index=True)
                            
                            # Also show as simple list
                            st.markdown(f"**Eligible Candidates List ({len(eligible_details)}):**")
                            for detail in eligible_details:
                                st.write(f"✅ **{detail['Name']}** - {detail['Email']}")
                            
                            # Download button
                            csv_data = df_eligible.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Eligible Candidates",
                                data=csv_data,
                                file_name=f"eligible_candidates_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                        else:
                            st.info("No candidate details found in eligible candidates list")
                    else:
                        st.info("No eligible candidates found")
                else:
                    st.info("No eligible candidates data available")
                
                # Display INELIGIBLE candidates
                if ineligible_candidates_list and isinstance(ineligible_candidates_list, list) and len(ineligible_candidates_list) > 0:
                    st.markdown("---")
                    with st.expander(f"❌ View Ineligible Candidates ({ineligible_count})", expanded=False):
                        # Extract names from ineligible candidates
                        ineligible_details = []
                        
                        for candidate in ineligible_candidates_list:
                            if isinstance(candidate, dict):
                                # Get name from candidate_info
                                name = None
                                if 'candidate_info' in candidate and isinstance(candidate['candidate_info'], dict):
                                    candidate_info = candidate['candidate_info']
                                    if 'name' in candidate_info and candidate_info['name']:
                                        name = candidate_info['name'].strip()
                                
                                # Get other details
                                email = ""
                                reason = candidate.get('reason', '')
                                missing_requirements = candidate.get('critical_missing_requirements', [])
                                
                                if 'candidate_info' in candidate and isinstance(candidate['candidate_info'], dict):
                                    email = candidate['candidate_info'].get('email', '')
                                
                                if name:
                                    # Clean the name
                                    name = ' '.join(word.capitalize() for word in name.split())
                                    
                                    # Add to details
                                    ineligible_details.append({
                                        'Name': name,
                                        'Email': email,
                                        'Missing Requirements': ', '.join(missing_requirements[:2]) + ('...' if len(missing_requirements) > 2 else ''),
                                        'Reason': reason[:50] + '...' if len(reason) > 50 else reason
                                    })
                        
                        if ineligible_details:
                            # Display as table
                            df_ineligible = pd.DataFrame(ineligible_details)
                            st.dataframe(df_ineligible, use_container_width=True, hide_index=True)
                            
                            # Download button
                            csv_data = df_ineligible.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Ineligible Candidates",
                                data=csv_data,
                                file_name=f"ineligible_candidates_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                        else:
                            st.info("No valid details found in ineligible candidates")
                
                # Show errors if any (collapsed by default)
                errors = screening_data.get('errors', [])
                if errors and len(errors) > 0:
                    st.markdown("---")
                    with st.expander(f"⚠️ View Processing Errors ({len(errors)})", expanded=False):
                        for error in errors:
                            if isinstance(error, dict):
                                st.error(f"**{error.get('type', 'Error')}**: {error.get('message', 'Unknown error')}")
                            else:
                                st.error(str(error))
                
            else:
                st.info("No screening data available")
        
        tab_index += 1
    # Ranking Tab
    if "Candidate Ranker" in agents_used and tab_index < len(tabs):
        with tabs[tab_index]:
            st.markdown("## Ranking Results")
            
            ranking_data = output_files.get('ranking')
            if ranking_data and isinstance(ranking_data, dict):
                # Display summary
                if 'summary' in ranking_data:
                    summary = ranking_data['summary']
                    col1, col2 = st.columns(2)
                    with col1:
                        total = summary.get('total_candidates', 0)
                        st.metric("Total Ranked", total)
                    with col2:
                        # Show top rank instead of top score
                        if 'candidates' in ranking_data and ranking_data['candidates']:
                            # Find minimum rank (best rank)
                            ranks = []
                            for c in ranking_data['candidates']:
                                if isinstance(c, dict) and c.get('rank'):
                                    try:
                                        ranks.append(int(c.get('rank')))
                                    except:
                                        pass
                            if ranks:
                                top_rank = min(ranks)
                                st.metric("Top Rank", f"#{top_rank}")
                            else:
                                st.metric("Top Rank", "N/A")
                
                # Display ranked candidates
                if 'candidates' in ranking_data:
                    candidates = ranking_data['candidates']
                    if candidates:
                        # Sort by rank
                        sorted_candidates = sorted(candidates, key=lambda x: x.get('rank', 999))
                        
                        display_data = []
                        for candidate in sorted_candidates:
                            if isinstance(candidate, dict):
                                display_data.append({
                                    'Rank': candidate.get('rank', 'N/A'),
                                    'Name': candidate.get('name', 'Unknown'),
                                    'Email': candidate.get('email', 'N/A')
                                    # NO SCORE COLUMN - removed as requested
                                })
                        
                        if display_data:
                            df = pd.DataFrame(display_data)
                            st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No ranking data available")
        
        tab_index += 1
    
    # Scheduling Tab (only if used)
    if "Interview Scheduler" in agents_used and tab_index < len(tabs):
        with tabs[tab_index]:
            st.markdown("## Interview Scheduling Results")
            
            scheduling_data = output_files.get('scheduling')
            
            if scheduling_data and isinstance(scheduling_data, dict):
                # Try multiple ways to extract interviews
                interviews = []
                total_candidates = 0
                ranked_candidates = 0
                
                # Get total and ranked candidates from ranking data for comparison
                ranking_data = output_files.get('ranking')
                if ranking_data and isinstance(ranking_data, dict):
                    if 'candidates' in ranking_data and isinstance(ranking_data['candidates'], list):
                        total_candidates = len(ranking_data['candidates'])
                        ranked_candidates = len([c for c in ranking_data['candidates'] if isinstance(c, dict) and c.get('rank')])
                
                # Method 1: Check for 'scheduled_interviews'
                if 'scheduled_interviews' in scheduling_data:
                    if isinstance(scheduling_data['scheduled_interviews'], list):
                        interviews = scheduling_data['scheduled_interviews']
                    elif isinstance(scheduling_data['scheduled_interviews'], dict):
                        # Handle dict format
                        interviews_list = scheduling_data['scheduled_interviews'].get('interviews', [])
                        if isinstance(interviews_list, list):
                            interviews = interviews_list
                
                # Method 2: Check for 'interviews'
                elif 'interviews' in scheduling_data and isinstance(scheduling_data['interviews'], list):
                    interviews = scheduling_data['interviews']
                
                # Method 3: Check for candidates with scheduled flag
                elif 'candidates' in scheduling_data and isinstance(scheduling_data['candidates'], list):
                    interviews = [c for c in scheduling_data['candidates'] if isinstance(c, dict) and c.get('scheduled', False)]
                
                scheduled_count = len(interviews)
                
                # Display summary
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Interviews Scheduled", scheduled_count)
                with col2:
                    st.metric("Total Candidates", total_candidates or scheduled_count)
                with col3:
                    st.metric("Ranked Candidates", ranked_candidates or total_candidates or scheduled_count)
                with col4:
                    st.metric("Job Title", st.session_state.workflow_config.get('job_title', 'Position'))
        
                # Show status message
                if scheduled_count > 0:
                    if scheduled_count >= total_candidates:
                        st.success("✅ All interviews scheduled!")
                    else:
                        st.warning(f"⚠️ {scheduled_count} of {total_candidates} interviews scheduled")
                        
                        # Show calendar upload option when more slots are needed
                        if total_candidates > scheduled_count:
                            st.markdown("---")
                            with st.expander("📤 Need More Time Slots? Upload a New Calendar", expanded=False):
                                new_cal_url = st.text_input(
                                    "New Google Calendar URL:",
                                    placeholder="https://calendar.google.com/calendar/ical/...",
                                    help="Upload a new calendar with more available time slots",
                                    key="scheduling_new_calendar_url"
                                )
                                
                                if new_cal_url:
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.button("🔄 Use for Rescheduling", type="primary", use_container_width=True):
                                            st.session_state.workflow_config['calendar_url'] = new_cal_url
                                            st.success("✅ New calendar URL saved!")
                                            st.info("Refresh the page after running rescheduling to see updated results.")
                                    with col2:
                                        if st.button("Save URL", type="secondary", use_container_width=True):
                                            st.session_state.workflow_config['calendar_url'] = new_cal_url
                                            st.success("✅ Calendar URL saved!")
                else:
                    st.warning("⚠️ No interviews scheduled yet")
                    
                    # Show calendar upload option if no interviews are scheduled
                    st.markdown("---")
                    with st.expander("📤 Upload Calendar to Start Scheduling", expanded=True):
                        new_cal_url = st.text_input(
                            "Google Calendar URL:",
                            placeholder="https://calendar.google.com/calendar/ical/...",
                            help="Upload a calendar with available time slots",
                            key="scheduling_new_calendar_url_empty"
                        )
                        
                        if new_cal_url:
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("🔄 Use for Scheduling", type="primary", use_container_width=True):
                                    st.session_state.workflow_config['calendar_url'] = new_cal_url
                                    st.success("✅ Calendar URL saved!")
                                    st.info("Refresh the page to start scheduling.")
                            with col2:
                                if st.button("Save URL", type="secondary", use_container_width=True):
                                    st.session_state.workflow_config['calendar_url'] = new_cal_url
                                    st.success("✅ Calendar URL saved!")
                
                # Display scheduled interviews with PANEL INFORMATION
                if scheduled_count > 0:
                    st.markdown("### 📅 Scheduled Interviews")
                    
                    display_data = []
                    for i, interview in enumerate(interviews, 1):
                        if isinstance(interview, dict):
                            # Extract panel information - check multiple possible keys
                            panel_name = interview.get('panel_name', 
                                                    interview.get('panel', 
                                                                interview.get('panel_assigned', 
                                                                            interview.get('assigned_panel', 'Not specified'))))
                            
                            # Extract buffer information
                            has_buffer = interview.get('has_buffer', 
                                                    interview.get('buffer_minutes', 0) > 0)
                            buffer_info = " (+15min buffer)" if has_buffer else ""
                            
                            display_data.append({
                                'No.': i,
                                'Name': interview.get('candidate_name', interview.get('name', 'Unknown')),
                                'Email': interview.get('candidate_email', interview.get('email', 'N/A')),
                                'Rank': interview.get('rank', interview.get('candidate_rank', 'N/A')),
                                'Panel': panel_name,
                                'Date': interview.get('interview_date', interview.get('date', '')),
                                'Time': interview.get('interview_time', interview.get('time', '')),
                                'Duration': f"{interview.get('duration_minutes', interview.get('duration', 0))} min",
                                'Mode': interview.get('interview_mode', interview.get('mode', 'online')),
                                #'Buffer': buffer_info,
                                'Status': interview.get('status', 'scheduled')
                            })
                    
                    if display_data:
                        df = pd.DataFrame(display_data)
                        
                        # Apply styling for better visualization
                        def highlight_panels(row):
                            styles = [''] * len(row)
                            if row['Panel']:
                                # Color code different panels
                                panel_colors = {
                                    'A': 'background-color: #FF6B6B; color: white',
                                    'B': 'background-color: #4ECDC4; color: white',
                                    'C': 'background-color: #FFD166; color: black',
                                    'D': 'background-color: #06D6A0; color: white',
                                    '4': 'background-color: #118AB2; color: white',
                                    'general': 'background-color: #6A0572; color: white'
                                }
                                for panel, color_style in panel_colors.items():
                                    if str(row['Panel']).upper() == str(panel).upper():
                                        styles[4] = color_style  # Panel column
                                        break
                            return styles
                        
                        # Apply styling
                        styled_df = df.style.apply(highlight_panels, axis=1)
                        
                        # Display the styled dataframe
                        st.dataframe(styled_df, use_container_width=True, hide_index=True)
                        
                        # Also show a summary of panel distribution
                        st.markdown("### 🎯 Panel Distribution")
                        panel_counts = df['Panel'].value_counts()
                        
                        if not panel_counts.empty:
                            col1, col2, col3 = st.columns(3)
                            panels_list = list(panel_counts.items())
                            
                            for idx, (panel, count) in enumerate(panels_list[:3]):
                                col_idx = idx % 3
                                if col_idx == 0:
                                    col = col1
                                elif col_idx == 1:
                                    col = col2
                                else:
                                    col = col3
                                
                                with col:
                                    st.metric(f"Panel {panel}", count)
                            
                            # Show any remaining panels
                            if len(panels_list) > 3:
                                st.markdown(f"**Additional panels:** {', '.join([str(p) for p in panel_counts.index[3:]])}")
                        
                        # Download option
                        st.markdown("---")
                        csv_data = df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Schedule with Panels",
                            data=csv_data,
                            file_name=f"interview_schedule_with_panels_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    else:
                        st.info("No interviews found in scheduling data")
                
                # Show what data is available for debugging
                if scheduled_count == 0:
                    with st.expander("🔍 View Scheduling Data Structure", expanded=False):
                        st.json(scheduling_data)
                        
                        # Check if we have partial scheduling info
                        if 'frontend_action' in scheduling_data:
                            action_data = scheduling_data['frontend_action']
                            if isinstance(action_data, dict):
                                st.info(f"Status: {action_data.get('message', 'Partial scheduling')}")
                                st.info(f"Scheduled so far: {action_data.get('scheduled_so_far', 0)}")
                                st.info(f"Remaining to schedule: {action_data.get('remaining_to_schedule', 0)}")
            else:
                st.warning("⚠️ No scheduling data available")
            
            tab_index += 1
        # Background Check Tab (only if used)
    if "Background Verifier" in agents_used and tab_index < len(tabs):
        with tabs[tab_index]:
            st.markdown("## Background Verification Results")
            
            background_data = output_files.get('background')
            if background_data and isinstance(background_data, dict):
                # Display summary from the raw data structure
                col1, col2 = st.columns(2)
                with col1:
                    total_verified = background_data.get('total_verified_candidates', 0)
                    st.metric("Verified Candidates", total_verified)
                with col2:
                    # Count actual candidates
                    verified_candidates = background_data.get('verified_candidates', [])
                    actual_count = len(verified_candidates) if isinstance(verified_candidates, list) else 0
                    st.metric("Total Checked", actual_count)
                
                # Handle the specific structure from your data
                verified_candidates = background_data.get('verified_candidates', [])
                
                if verified_candidates and isinstance(verified_candidates, list):
                    if len(verified_candidates) > 0:
                        # Create display data with only name and verification status
                        display_data = []
                        for candidate in verified_candidates:
                            if isinstance(candidate, dict):
                                name = candidate.get('name', 'Unknown Candidate')
                                
                                # All candidates in verified_candidates list are considered verified
                                display_data.append({
                                    'Name': name,
                                    'Status': '✅ Verified'
                                })
                        
                        if display_data:
                            df = pd.DataFrame(display_data)
                            
                            # Add styling for verification status
                            def color_status(val):
                                if val == '✅ Verified':
                                    return 'background-color: #4CAF50; color: white'
                                return ''
                            
                            # Apply styling
                            styled_df = df.style.map(color_status, subset=['Status'])
                            
                            st.markdown("### Verified Candidates")
                            st.dataframe(styled_df, use_container_width=True, hide_index=True)
                            
                            # Show simple list of verified candidates
                            st.markdown("---")
                            st.markdown("#### Verified Candidate List:")
                            for candidate in display_data:
                                st.write(f"✅ **{candidate['Name']}**")
                            
                            # Download button
                            st.markdown("---")
                            csv_data = df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Verification Report",
                                data=csv_data,
                                file_name=f"background_verification_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                        else:
                            st.info("No candidate details available in the verification data")
                    else:
                        st.info("No candidates have been verified yet")
                else:
                    # Show simple message if data exists but no verified_candidates
                    if background_data:
                        st.info("Background verification completed")
                        # Show export timestamp if available
                        if 'export_timestamp' in background_data:
                            st.write(f"**Verification completed on:** {background_data['export_timestamp']}")
            else:
                st.info("No background verification data available")

def delete_session_with_files(session_id, user_id, session_name):
    """Delete session and associated files"""
    try:
        # Delete from database
        success = delete_session(session_id, user_id)
        
        if success:
            # Clean up session files
            session_folder = f"session_{session_id}"
            
            # Delete session-specific folders
            folders_to_delete = [
                session_folder,
                f"data/{session_folder}",
                f"output/{session_folder}"
            ]
            
            for folder in folders_to_delete:
                if os.path.exists(folder):
                    try:
                        shutil.rmtree(folder)
                        st.info(f"Deleted folder: {folder}")
                    except Exception as e:
                        pass
            
            # Also clean up any files with session ID in name
            patterns = [
                f"*session_{session_id}*",
                f"*{session_name.replace(' ', '_').replace('/', '_')}*"
            ]
            
            for pattern in patterns:
                for file in glob.glob(pattern):
                    try:
                        if os.path.isfile(file):
                            os.remove(file)
                    except:
                        pass
        
        return success
        
    except Exception as e:
        st.error(f"Error deleting session files: {e}")
        # Still return True if database deletion succeeded
        return True
    
def load_session_data(session):
    """Load session data from database and file system"""
    try:
        # Base data from database
        session_data = {
            'id': session.get('id'),
            'session_name': session.get('session_name', ''),
            'job_description': session.get('job_description', ''),
            'job_title': session.get('job_title', ''),
            'resume_count': session.get('resume_count', 0),
            'created_at': session.get('created_at', ''),
            'candidates': [],
            'results_data': {},
            'workflow_config': {}
        }
        
        # Try to get results_data from database
        results_data = session.get('results_data')
        if results_data:
            if isinstance(results_data, str):
                try:
                    results_data = json.loads(results_data)
                except json.JSONDecodeError:
                    # Try to fix common JSON issues
                    results_data_str = str(results_data)
                    # Remove any extra characters that might break JSON parsing
                    results_data_str = results_data_str.replace("'", '"').replace('None', 'null')
                    try:
                        results_data = json.loads(results_data_str)
                    except:
                        results_data = {}
                except:
                    results_data = {}
            
            session_data['results_data'] = results_data
            
            # Extract candidates from results_data
            if isinstance(results_data, dict):
                candidates = results_data.get('candidates', [])
                if candidates and isinstance(candidates, list):
                    processed_candidates = []
                    for candidate in candidates:
                        if isinstance(candidate, dict):
                            processed_candidate = {
                                'name': candidate.get('name', candidate.get('Name', 'Unknown')),
                                'email': candidate.get('email', candidate.get('Email', '')),
                                'phone': candidate.get('phone', candidate.get('Phone', '')),
                                'rank': candidate.get('rank', candidate.get('Rank', 0)),
                                'score': candidate.get('score', candidate.get('Score', 0)),
                                'status': candidate.get('status', candidate.get('Status', 'eligible')),
                                'interview_date': candidate.get('interview_date', candidate.get('Interview Date', '')),
                                'interview_time': candidate.get('interview_time', candidate.get('Interview Time', '')),
                                'meeting_link': candidate.get('meeting_link', candidate.get('Meeting Link', ''))
                            }
                            processed_candidates.append(processed_candidate)
                    
                    session_data['candidates'] = processed_candidates
        
        # Try to get workflow config
        workflow_config = session.get('workflow_config')
        if workflow_config:
            if isinstance(workflow_config, str):
                try:
                    workflow_config = json.loads(workflow_config)
                except json.JSONDecodeError:
                    # Try to fix common JSON issues
                    workflow_config_str = str(workflow_config)
                    workflow_config_str = workflow_config_str.replace("'", '"').replace('None', 'null')
                    try:
                        workflow_config = json.loads(workflow_config_str)
                    except:
                        workflow_config = {}
                except:
                    workflow_config = {}
            
            session_data['workflow_config'] = workflow_config
        
        # CRITICAL FIX: Try to load from session folder if available
        # Look for session folder pattern
        session_id = session.get('id')
        if session_id:
            # Search for session folder (pattern: session_{id}_*)
            import glob
            session_folders = glob.glob(f"session_{session_id}_*")
            
            if session_folders:
                session_folder = session_folders[0]  # Take the first matching folder
                session_data['session_folder'] = session_folder
                
                print(f"📁 Found session folder: {session_folder}")  # Debug
                
                # Load job description from file
                jd_file = os.path.join(session_folder, 'job_description.txt')
                if os.path.exists(jd_file):
                    try:
                        with open(jd_file, 'r', encoding='utf-8') as f:
                            session_data['job_description'] = f.read()
                        print(f"✅ Loaded job description from: {jd_file}")  # Debug
                    except Exception as e:
                        print(f"❌ Error loading job description: {e}")
                
                # Load output files if they exist
                output_folder = os.path.join(session_folder, 'output')
                if os.path.exists(output_folder):
                    print(f"📂 Found output folder: {output_folder}")  # Debug
                    output_files = {}
                    
                    # List of possible output files with their expected names
                    possible_files = {
                        'screening_results.json': 'screening',
                        'ranking_results.json': 'ranking',  # This was 'candidate_ranking_report.json' in the old version
                        'schedule_results.json': 'scheduling',  # This was 'interview_schedule.json' in the old version
                        'background_results.json': 'background'  # This was 'background_verification_report.json' in the old version
                    }
                    
                    for filename, key in possible_files.items():
                        filepath = os.path.join(output_folder, filename)
                        if os.path.exists(filepath):
                            try:
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    output_files[key] = json.load(f)
                                print(f"✅ Loaded {key} data from: {filename}")  # Debug
                            except Exception as e:
                                print(f"❌ Error loading {filename}: {e}")
                                output_files[key] = None
                        else:
                            print(f"⚠️  File not found: {filepath}")  # Debug
                            output_files[key] = None
                    
                    session_data['output_files'] = output_files
                    print(f"📊 Total output files loaded: {len([k for k, v in output_files.items() if v])}")  # Debug
                else:
                    print(f"⚠️  Output folder not found: {output_folder}")  # Debug
            else:
                print(f"⚠️  No session folder found for session ID: {session_id}")  # Debug
        
        return session_data
        
    except Exception as e:
        print(f"❌ Error loading session data: {e}")
        import traceback
        print(traceback.format_exc())
        return session
    
def get_complete_session_data(session_id):
    """Get complete session data including candidates"""
    try:
        # Use your existing get_session_details function
        session_data = get_session_details(session_id)
        
        if not session_data:
            return None
        
        # Ensure candidates list exists
        if 'candidates' not in session_data:
            session_data['candidates'] = []
        
        # If candidates list is empty but we have resume count, add placeholder
        if not session_data['candidates'] and session_data.get('resume_count', 0) > 0:
            session_data['candidates'] = [{
                'name': 'Data processing incomplete',
                'status': 'processing',
                'note': 'Candidate data is being processed or was not saved properly'
            }]
        
        return session_data
        
    except Exception as e:
        print(f"Error getting complete session data: {e}")
        return None
    
def show_previous_sessions_page():
    """Show previous recruitment sessions with detailed view option"""
    load_css("other")
    
    if not st.session_state.authenticated:
        navigate_to("login")
        return
    
    # Back button
    if st.button("← Back to Home"):
        navigate_to("home")
        return
    
    st.markdown("## Previous Recruitment Sessions")
    
    try:
        sessions = get_user_sessions(st.session_state.user['id'])
    except Exception as e:
        st.error(f"Error loading sessions: {e}")
        sessions = []
    
    if not sessions:
        st.info("No previous sessions found")
        if st.button("Start New Recruitment"):
            navigate_to("new_recruitment")
        return
    
    # Add a filter/search option
    search_term = st.text_input("🔍 Search sessions by name or job title:", "", key="session_search")
    
    # Filter sessions based on search
    if search_term:
        filtered_sessions = [
            s for s in sessions 
            if search_term.lower() in s.get('session_name', '').lower() or 
               search_term.lower() in s.get('job_title', '').lower()
        ]
    else:
        filtered_sessions = sessions
    
    if not filtered_sessions:
        st.warning(f"No sessions found matching '{search_term}'")
        return
    
    # Sort sessions by date (newest first)
    filtered_sessions.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Display each session
    for session in filtered_sessions:
        session_id = session.get('id')
        session_name = session.get('session_name', 'Unnamed Session')
        job_title = session.get('job_title', 'N/A')
        resume_count = session.get('resume_count', 0)
        created_at = session.get('created_at', '')
        
        # Format date
        if created_at:
            try:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_at_str = created_dt.strftime('%Y-%m-%d %H:%M')
                time_ago = datetime.now() - created_dt
                if time_ago.days == 0:
                    time_ago_str = "Today"
                elif time_ago.days == 1:
                    time_ago_str = "Yesterday"
                elif time_ago.days < 7:
                    time_ago_str = f"{time_ago.days} days ago"
                else:
                    time_ago_str = f"{time_ago.days // 7} weeks ago"
            except:
                created_at_str = created_at[:19] if len(created_at) > 19 else created_at
                time_ago_str = ""
        else:
            created_at_str = 'Unknown Date'
            time_ago_str = ""
        
        # Create a card for each session
        with st.expander(f"📁 {session_name} - {job_title}", expanded=False):
            # Header with job title and details
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**{job_title}**")
                st.caption(f"Session: {session_name}")
            with col2:
                st.markdown(f"📄 **{resume_count}** resumes")
            with col3:
                st.markdown(f"📅 {created_at_str}")
                if time_ago_str:
                    st.caption(f"({time_ago_str})")
            
            # Load complete session data
            session_data = load_session_data(session)
            
            # Get workflow configuration from session data - PROPER DETECTION
            workflow_config = session_data.get('workflow_config', {})
            
            # Debug: Print workflow config to understand structure
            # print(f"DEBUG: Session {session_id} workflow_config type: {type(workflow_config)}")
            # print(f"DEBUG: Session {session_id} workflow_config: {workflow_config}")
            
            # Check if workflow_config is a dict with workflow_data
            if isinstance(workflow_config, dict):
                # Try to get workflow_data (this is how it's stored in your sessions)
                workflow_data = workflow_config.get('workflow_data', {})
                
                # If workflow_data is empty, maybe workflow_config itself contains the settings
                if not workflow_data and workflow_config:
                    # Check if workflow_config has the run_* keys directly
                    if any(key.startswith('run_') for key in workflow_config.keys()):
                        workflow_data = workflow_config
            else:
                # If workflow_config is not a dict, initialize empty
                workflow_data = {}
            
            # Also check results_data for workflow info
            results_data = session_data.get('results_data', {})
            if isinstance(results_data, dict):
                agents_in_results = results_data.get('agents', [])
                # print(f"DEBUG: Agents in results_data: {agents_in_results}")
            
            # DETERMINE WHICH AGENTS WERE USED - SAME LOGIC AS RESULTS PAGE
            # Default agents that are always used
            agents_used = ['Resume Screener', 'Candidate Ranker']
            
            # Check for scheduling agent
            scheduling_data = session_data.get('output_files', {}).get('scheduling')
            has_scheduling_data = scheduling_data is not None and isinstance(scheduling_data, dict)
            
            # Check workflow config for scheduling flag
            run_scheduling = workflow_data.get('run_scheduling', False)
            needs_interview = workflow_config.get('needs_interview', False)
            
            # If scheduling data exists OR workflow says to run scheduling, include it
            if has_scheduling_data or run_scheduling or needs_interview:
                if 'Interview Scheduler' not in agents_used:
                    agents_used.append('Interview Scheduler')
            
            # Check for background check agent
            background_data = session_data.get('output_files', {}).get('background')
            has_background_data = background_data is not None and isinstance(background_data, dict)
            
            # Check workflow config for background check flag
            run_background = workflow_data.get('run_background', False)
            needs_background_check = workflow_config.get('needs_background_check', False)
            
            # If background data exists OR workflow says to run background check, include it
            if has_background_data or run_background or needs_background_check:
                if 'Background Verifier' not in agents_used:
                    agents_used.append('Background Verifier')
            
            # Debug: Print agents detection
            # print(f"DEBUG: Session {session_id} - Agents used: {agents_used}")
            # print(f"DEBUG: Has scheduling data: {has_scheduling_data}")
            # print(f"DEBUG: Has background data: {has_background_data}")
            # print(f"DEBUG: workflow_data keys: {list(workflow_data.keys()) if isinstance(workflow_data, dict) else 'N/A'}")
            
            # Get output files from session data
            output_files = session_data.get('output_files', {})
            
            # ================================================
            # PROCESS CANDIDATE DATA FOR FINAL OUTPUT - SAME AS RESULTS PAGE
            # ================================================
            all_candidates_data = {}

            # 1. Get ranking data FIRST - we only care about RANKED candidates
            ranking_data = output_files.get('ranking')
            if ranking_data and isinstance(ranking_data, dict):
                # Handle both 'ranked_candidates' and 'candidates' keys
                ranked_candidates = ranking_data.get('ranked_candidates', ranking_data.get('candidates', []))
                
                if isinstance(ranked_candidates, list):
                    for candidate in ranked_candidates:
                        if isinstance(candidate, dict):
                            name = candidate.get('name', '').strip()
                            email = candidate.get('email', '').strip()
                            rank = candidate.get('rank')
                            
                            # ONLY process candidates with a valid rank (not N/A)
                            if name and rank is not None and rank != 'N/A':
                                try:
                                    # Convert rank to integer if possible
                                    rank_int = int(rank)
                                    all_candidates_data[email or name] = {
                                        'name': name,
                                        'email': email,
                                        'rank': rank_int,
                                        'status': 'eligible'  # Default status
                                    }
                                except (ValueError, TypeError):
                                    # Skip if rank is not a valid number
                                    continue

            # 2. Get scheduling data (if available) - only for RANKED candidates
            scheduling_data = output_files.get('scheduling')
            if scheduling_data and isinstance(scheduling_data, dict):
                interviews = scheduling_data.get('scheduled_interviews', [])
                if not interviews and 'interviews' in scheduling_data:
                    interviews = scheduling_data.get('interviews', [])
                
                if isinstance(interviews, list):
                    for interview in interviews:
                        if isinstance(interview, dict):
                            name = interview.get('candidate_name', '').strip()
                            email = interview.get('candidate_email', '').strip()
                            
                            key = email or name
                            if key in all_candidates_data:  # Only update if candidate is in our ranked list
                                all_candidates_data[key].update({
                                    'interview_date': interview.get('interview_date', ''),
                                    'interview_time': interview.get('interview_time', ''),
                                    'meeting_link': interview.get('meeting_link', ''),
                                    'status': 'scheduled'
                                })

            # 3. If no ranked candidates found, check screening data as fallback (but only for eligible)
            if not all_candidates_data:
                screening_data = output_files.get('screening')
                if screening_data and isinstance(screening_data, dict) and 'eligible_candidates' in screening_data:
                    eligible_candidates = screening_data.get('eligible_candidates', [])
                    for candidate in eligible_candidates:
                        if isinstance(candidate, dict):
                            candidate_info = candidate.get('candidate_info', {})
                            name = candidate_info.get('name', '').strip()
                            email = candidate_info.get('email', '').strip()
                            
                            if name:
                                all_candidates_data[email or name] = {
                                    'name': name,
                                    'email': email,
                                    'rank': 'N/A',
                                    'status': 'eligible'
                                }
            
            # ================================================
            # CREATE TABS - BASED ON AGENTS USED
            # ================================================
            tab_names = ['Final Output']
            
            # Add agent tabs based on what was used
            for agent in agents_used:
                if agent == "Resume Screener":
                    tab_names.append("Screening")
                elif agent == "Candidate Ranker":
                    tab_names.append("Ranking")
                elif agent == "Interview Scheduler":
                    tab_names.append("Scheduling")
                elif agent == "Background Verifier":
                    tab_names.append("Background Check")
            
            # Debug: Print tabs to be created
            # print(f"DEBUG: Session {session_id} - Creating tabs: {tab_names}")
            # print(f"DEBUG: Has scheduling output: {'scheduling' in output_files}")
            # print(f"DEBUG: Has background output: {'background' in output_files}")
            
            # Create tabs
            tabs = st.tabs(tab_names)
            
            # ================================================
            # FINAL OUTPUT TAB - EXACTLY LIKE RESULTS PAGE
            # ================================================
            with tabs[0]:
                st.markdown("## Final Output")
                
                if all_candidates_data:
                    # Prepare ALL candidates for display
                    display_data = []
                    
                    for candidate_id, candidate_info in all_candidates_data.items():
                        name = candidate_info.get('name', '').strip()
                        email = candidate_info.get('email', '').strip()
                        rank = candidate_info.get('rank', 'N/A')
                        status = candidate_info.get('status', 'eligible')
                        
                        if not name:
                            continue
                        
                        # Create base row
                        row = {
                            'Name': name,
                            'Email': email,
                            'Rank': rank,
                            'Status': status
                        }
                        
                        # Add interview details if available
                        if 'interview_date' in candidate_info and candidate_info['interview_date']:
                            row['Interview Date'] = candidate_info.get('interview_date', '')
                            row['Interview Time'] = candidate_info.get('interview_time', '')
                            row['Meeting Link'] = candidate_info.get('meeting_link', '')
                            row['Status'] = 'scheduled'
                        
                        # If rank is "N/A" but candidate is eligible, keep as eligible
                        if rank == 'N/A' and 'interview_date' not in candidate_info:
                            row['Status'] = 'eligible'
                        
                        display_data.append(row)
                    
                    if display_data:
                        # Sort by: 1. Has interview, 2. Valid rank, 3. Name
                        def sort_key(candidate):
                            # First: Scheduled candidates (have interview date)
                            has_interview = 'Interview Date' in candidate and candidate['Interview Date']
                            # Second: Rank (numeric first, then "N/A")
                            rank_val = candidate.get('Rank')
                            if isinstance(rank_val, (int, float)):
                                rank_order = (0, rank_val)  # Numeric ranks come first
                            else:
                                rank_order = (1, 0)  # "N/A" ranks come after
                            # Third: Name for alphabetical ordering
                            return (not has_interview, rank_order, candidate.get('Name', '').lower())
                        
                        display_data.sort(key=sort_key)
                        
                        # Display table
                        st.markdown("### Final Evaluation")
                        df = pd.DataFrame(display_data)
                        st.dataframe(df, use_container_width=True, hide_index=True, key=f"final_output_df_{session_id}")
                        
                        # Summary statistics - FIXED COUNTS
                        st.markdown("---")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            total_candidates = len(display_data)
                            st.metric("Total Candidates", total_candidates)
                        
                        with col2:
                            scheduled = sum(1 for c in display_data if c.get('Status') == 'scheduled')
                            st.metric("Interviews Scheduled", scheduled)
                        
                        with col3:
                            ranked = sum(1 for c in display_data if isinstance(c.get('Rank'), (int, float)))
                            st.metric("Ranked Candidates", ranked)
                        
                        # Also show job title
                        st.markdown(f"**Job Title:** {job_title}")
                        
                        # Download button
                        csv_data = df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Final Output",
                            data=csv_data,
                            file_name=f"final_output_{session_name.replace(' ', '_')}_{session_id}.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key=f"dl_final_output_{session_id}"
                        )
                    else:
                        st.info("No candidate data available")
                else:
                    st.info("No candidate data found")
            
            # ================================================
            # OTHER TABS (Screening, Ranking, Scheduling, Background)
            # ================================================
            tab_index = 1
            
            # Screening Tab
            if "Resume Screener" in agents_used and tab_index < len(tabs):
                with tabs[tab_index]:
                    st.markdown("## Screening Results")
                    
                    screening_data = output_files.get('screening')
                    
                    if screening_data and isinstance(screening_data, dict):
                        # Get summary
                        summary = screening_data.get('summary', {})
                        total_screened = summary.get('total_screened', 0)
                        eligible_count = summary.get('eligible_count', 0)
                        ineligible_count = summary.get('ineligible_count', 0)
                        
                        # Display summary metrics
                        st.markdown("### 📊 Summary")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Screened", total_screened)
                        with col2:
                            st.metric("✅ Eligible", eligible_count)
                        with col3:
                            st.metric("❌ Ineligible", ineligible_count)
                        
                        # Get candidate lists
                        eligible_candidates_list = screening_data.get('eligible_candidates', [])
                        ineligible_candidates_list = screening_data.get('ineligible_candidates', [])
                        
                        # Display ELIGIBLE candidates
                        st.markdown("---")
                        st.markdown("### ✅ Eligible Candidates")
                        
                        if eligible_candidates_list and isinstance(eligible_candidates_list, list):
                            if len(eligible_candidates_list) > 0:
                                eligible_details = []
                                
                                for candidate in eligible_candidates_list:
                                    if isinstance(candidate, dict):
                                        # Get name from candidate_info
                                        name = None
                                        if 'candidate_info' in candidate and isinstance(candidate['candidate_info'], dict):
                                            candidate_info = candidate['candidate_info']
                                            if 'name' in candidate_info and candidate_info['name']:
                                                name = candidate_info['name'].strip()
                                        
                                        # Also get other details
                                        email = ""
                                        experience = ""
                                        reason = candidate.get('reason', '')
                                        
                                        if 'candidate_info' in candidate and isinstance(candidate['candidate_info'], dict):
                                            email = candidate['candidate_info'].get('email', '')
                                            experience = candidate['candidate_info'].get('total_experience', '')
                                        
                                        # Get skills summary
                                        skills = []
                                        if 'skills_summary' in candidate and isinstance(candidate['skills_summary'], dict):
                                            skills_list = candidate['skills_summary'].get('skills', [])
                                            if isinstance(skills_list, list):
                                                skills = skills_list
                                        
                                        if name:
                                            # Clean the name - capitalize properly
                                            name = ' '.join(word.capitalize() for word in name.split())
                                            
                                            # Add to details for table
                                            eligible_details.append({
                                                'Name': name,
                                                'Email': email,
                                                'Experience': experience,
                                                'Skills': ', '.join(skills[:3]) + ('...' if len(skills) > 3 else ''),
                                                'Reason': reason[:50] + '...' if len(reason) > 50 else reason
                                            })
                                
                                if eligible_details:
                                    # Display as table
                                    df_eligible = pd.DataFrame(eligible_details)
                                    st.dataframe(df_eligible, use_container_width=True, hide_index=True, key=f"screen_df_{session_id}")
                                    
                                    # Download button
                                    csv_data = df_eligible.to_csv(index=False)
                                    st.download_button(
                                        label="📥 Download Eligible Candidates",
                                        data=csv_data,
                                        file_name=f"eligible_candidates_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                        mime="text/csv",
                                        use_container_width=True,
                                        key=f"dl_screen_{session_id}"
                                    )
                                else:
                                    st.info("No candidate details found in eligible candidates list")
                            else:
                                st.info("No eligible candidates found")
                        else:
                            st.info("No eligible candidates data available")
                        
                        # Display INELIGIBLE candidates
                        if ineligible_candidates_list and isinstance(ineligible_candidates_list, list) and len(ineligible_candidates_list) > 0:
                            st.markdown("---")
                            with st.expander(f"❌ View Ineligible Candidates ({ineligible_count})", expanded=False):
                                # Extract names from ineligible candidates
                                ineligible_details = []
                                
                                for candidate in ineligible_candidates_list:
                                    if isinstance(candidate, dict):
                                        # Get name from candidate_info
                                        name = None
                                        if 'candidate_info' in candidate and isinstance(candidate['candidate_info'], dict):
                                            candidate_info = candidate['candidate_info']
                                            if 'name' in candidate_info and candidate_info['name']:
                                                name = candidate_info['name'].strip()
                                        
                                        # Get other details
                                        email = ""
                                        reason = candidate.get('reason', '')
                                        missing_requirements = candidate.get('critical_missing_requirements', [])
                                        
                                        if 'candidate_info' in candidate and isinstance(candidate['candidate_info'], dict):
                                            email = candidate['candidate_info'].get('email', '')
                                        
                                        if name:
                                            # Clean the name
                                            name = ' '.join(word.capitalize() for word in name.split())
                                            
                                            # Add to details
                                            ineligible_details.append({
                                                'Name': name,
                                                'Email': email,
                                                'Missing Requirements': ', '.join(missing_requirements[:2]) + ('...' if len(missing_requirements) > 2 else ''),
                                                'Reason': reason[:50] + '...' if len(reason) > 50 else reason
                                            })
                                
                                if ineligible_details:
                                    # Display as table
                                    df_ineligible = pd.DataFrame(ineligible_details)
                                    st.dataframe(df_ineligible, use_container_width=True, hide_index=True, key=f"ineligible_df_{session_id}")
                                    
                                    # Download button
                                    csv_data = df_ineligible.to_csv(index=False)
                                    st.download_button(
                                        label="📥 Download Ineligible Candidates",
                                        data=csv_data,
                                        file_name=f"ineligible_candidates_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                        mime="text/csv",
                                        use_container_width=True,
                                        key=f"dl_ineligible_{session_id}"
                                    )
                                else:
                                    st.info("No valid details found in ineligible candidates")
                        
                        # Show errors if any (collapsed by default)
                        errors = screening_data.get('errors', [])
                        if errors and len(errors) > 0:
                            st.markdown("---")
                            with st.expander(f"⚠️ View Processing Errors ({len(errors)})", expanded=False):
                                for error in errors:
                                    if isinstance(error, dict):
                                        st.error(f"**{error.get('type', 'Error')}**: {error.get('message', 'Unknown error')}")
                                    else:
                                        st.error(str(error))
                    else:
                        st.info("No screening data available")
                
                tab_index += 1
            
            # Ranking Tab
            if "Candidate Ranker" in agents_used and tab_index < len(tabs):
                with tabs[tab_index]:
                    st.markdown("## Ranking Results")
                    
                    ranking_data = output_files.get('ranking')
                    if ranking_data and isinstance(ranking_data, dict):
                        # Display summary
                        if 'summary' in ranking_data:
                            summary = ranking_data['summary']
                            col1, col2 = st.columns(2)
                            with col1:
                                total = summary.get('total_candidates', 0)
                                st.metric("Total Ranked", total)
                            with col2:
                                # Show top rank instead of top score
                                if 'candidates' in ranking_data and ranking_data['candidates']:
                                    # Find minimum rank (best rank)
                                    ranks = []
                                    for c in ranking_data['candidates']:
                                        if isinstance(c, dict) and c.get('rank'):
                                            try:
                                                ranks.append(int(c.get('rank')))
                                            except:
                                                pass
                                    if ranks:
                                        top_rank = min(ranks)
                                        st.metric("Top Rank", f"#{top_rank}")
                                    else:
                                        st.metric("Top Rank", "N/A")
                        
                        # Display ranked candidates
                        if 'candidates' in ranking_data:
                            candidates = ranking_data['candidates']
                            if candidates:
                                # Sort by rank
                                sorted_candidates = sorted(candidates, key=lambda x: x.get('rank', 999))
                                
                                display_data = []
                                for candidate in sorted_candidates:
                                    if isinstance(candidate, dict):
                                        display_data.append({
                                            'Rank': candidate.get('rank', 'N/A'),
                                            'Name': candidate.get('name', 'Unknown'),
                                            'Email': candidate.get('email', 'N/A')
                                        })
                                
                                if display_data:
                                    df = pd.DataFrame(display_data)
                                    st.dataframe(df, use_container_width=True, hide_index=True, key=f"ranking_df_{session_id}")
                                    
                                    # Download button
                                    csv_data = df.to_csv(index=False)
                                    st.download_button(
                                        label="📥 Download Ranking Results",
                                        data=csv_data,
                                        file_name=f"ranking_results_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                        mime="text/csv",
                                        use_container_width=True,
                                        key=f"dl_ranking_{session_id}"
                                    )
                    else:
                        st.info("No ranking data available")
                
                tab_index += 1
            
            # Scheduling Tab (only if used AND has data)
            if "Interview Scheduler" in agents_used and tab_index < len(tabs):
                with tabs[tab_index]:
                    st.markdown("## Interview Scheduling Results")
                    
                    scheduling_data = output_files.get('scheduling')
                    
                    if scheduling_data and isinstance(scheduling_data, dict):
                        # Try multiple ways to extract interviews
                        interviews = []
                        total_candidates = 0
                        ranked_candidates = 0
                        
                        # Get total and ranked candidates from ranking data for comparison
                        ranking_data = output_files.get('ranking')
                        if ranking_data and isinstance(ranking_data, dict):
                            if 'candidates' in ranking_data and isinstance(ranking_data['candidates'], list):
                                total_candidates = len(ranking_data['candidates'])
                                ranked_candidates = len([c for c in ranking_data['candidates'] if isinstance(c, dict) and c.get('rank')])
                        
                        # Method 1: Check for 'scheduled_interviews'
                        if 'scheduled_interviews' in scheduling_data:
                            if isinstance(scheduling_data['scheduled_interviews'], list):
                                interviews = scheduling_data['scheduled_interviews']
                            elif isinstance(scheduling_data['scheduled_interviews'], dict):
                                # Handle dict format
                                interviews_list = scheduling_data['scheduled_interviews'].get('interviews', [])
                                if isinstance(interviews_list, list):
                                    interviews = interviews_list
                        
                        # Method 2: Check for 'interviews'
                        elif 'interviews' in scheduling_data and isinstance(scheduling_data['interviews'], list):
                            interviews = scheduling_data['interviews']
                        
                        # Method 3: Check for candidates with scheduled flag
                        elif 'candidates' in scheduling_data and isinstance(scheduling_data['candidates'], list):
                            interviews = [c for c in scheduling_data['candidates'] if isinstance(c, dict) and c.get('scheduled', False)]
                        
                        scheduled_count = len(interviews)
                        
                        # Display summary
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Interviews Scheduled", scheduled_count)
                        with col2:
                            st.metric("Total Candidates", total_candidates or scheduled_count)
                        with col3:
                            st.metric("Ranked Candidates", ranked_candidates or total_candidates or scheduled_count)
                        with col4:
                            st.metric("Job Title", job_title)
                        
                        # Display scheduled interviews with PANEL INFORMATION
                        if scheduled_count > 0:
                            st.markdown("### 📅 Scheduled Interviews")
                            
                            display_data = []
                            for i, interview in enumerate(interviews, 1):
                                if isinstance(interview, dict):
                                    # Extract panel information - check multiple possible keys
                                    panel_name = interview.get('panel_name', 
                                                            interview.get('panel', 
                                                                        interview.get('panel_assigned', 
                                                                                    interview.get('assigned_panel', 'Not specified'))))
                                    
                                    display_data.append({
                                        'No.': i,
                                        'Name': interview.get('candidate_name', interview.get('name', 'Unknown')),
                                        'Email': interview.get('candidate_email', interview.get('email', 'N/A')),
                                        'Rank': interview.get('rank', interview.get('candidate_rank', 'N/A')),
                                        'Panel': panel_name,
                                        'Date': interview.get('interview_date', interview.get('date', '')),
                                        'Time': interview.get('interview_time', interview.get('time', '')),
                                        'Duration': f"{interview.get('duration_minutes', interview.get('duration', 0))} min",
                                        'Mode': interview.get('interview_mode', interview.get('mode', 'online')),
                                        'Status': interview.get('status', 'scheduled')
                                    })
                            
                            if display_data:
                                df = pd.DataFrame(display_data)
                                
                                # Apply styling for better visualization
                                def highlight_panels(row):
                                    styles = [''] * len(row)
                                    if row['Panel']:
                                        # Color code different panels
                                        panel_colors = {
                                            'A': 'background-color: #FF6B6B; color: white',
                                            'B': 'background-color: #4ECDC4; color: white',
                                            'C': 'background-color: #FFD166; color: black',
                                            'D': 'background-color: #06D6A0; color: white',
                                            '4': 'background-color: #118AB2; color: white',
                                            'general': 'background-color: #6A0572; color: white'
                                        }
                                        for panel, color_style in panel_colors.items():
                                            if str(row['Panel']).upper() == str(panel).upper():
                                                styles[4] = color_style  # Panel column
                                                break
                                    return styles
                                
                                # Apply styling
                                styled_df = df.style.apply(highlight_panels, axis=1)
                                
                                # Display the styled dataframe
                                st.dataframe(styled_df, use_container_width=True, hide_index=True, key=f"schedule_df_{session_id}")
                                
                                # Download option
                                st.markdown("---")
                                csv_data = df.to_csv(index=False)
                                st.download_button(
                                    label="📥 Download Schedule with Panels",
                                    data=csv_data,
                                    file_name=f"interview_schedule_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                    mime="text/csv",
                                    use_container_width=True,
                                    key=f"dl_schedule_{session_id}"
                                )
                            else:
                                st.info("No interviews found in scheduling data")
                        else:
                            st.info("No interviews scheduled in this session")
                    else:
                        st.info("No scheduling data available")
                    
                    tab_index += 1
            
            # Background Check Tab (only if used AND has data)
            if "Background Verifier" in agents_used and tab_index < len(tabs):
                with tabs[tab_index]:
                    st.markdown("## Background Verification Results")
                    
                    background_data = output_files.get('background')
                    if background_data and isinstance(background_data, dict):
                        # Display summary from the raw data structure
                        col1, col2 = st.columns(2)
                        with col1:
                            total_verified = background_data.get('total_verified_candidates', 0)
                            st.metric("Verified Candidates", total_verified)
                        with col2:
                            # Count actual candidates
                            verified_candidates = background_data.get('verified_candidates', [])
                            actual_count = len(verified_candidates) if isinstance(verified_candidates, list) else 0
                            st.metric("Total Checked", actual_count)
                        
                        # Handle the specific structure from your data
                        verified_candidates = background_data.get('verified_candidates', [])
                        
                        if verified_candidates and isinstance(verified_candidates, list):
                            if len(verified_candidates) > 0:
                                # Create display data with only name and verification status
                                display_data = []
                                for candidate in verified_candidates:
                                    if isinstance(candidate, dict):
                                        name = candidate.get('name', 'Unknown Candidate')
                                        
                                        # All candidates in verified_candidates list are considered verified
                                        display_data.append({
                                            'Name': name,
                                            'Status': '✅ Verified'
                                        })
                                
                                if display_data:
                                    df = pd.DataFrame(display_data)
                                    
                                    # Add styling for verification status
                                    def color_status(val):
                                        if val == '✅ Verified':
                                            return 'background-color: #4CAF50; color: white'
                                        return ''
                                    
                                    # Apply styling
                                    styled_df = df.style.map(color_status, subset=['Status'])
                                    
                                    st.markdown("### Verified Candidates")
                                    st.dataframe(styled_df, use_container_width=True, hide_index=True, key=f"background_df_{session_id}")
                                    
                                    # Download button
                                    st.markdown("---")
                                    csv_data = df.to_csv(index=False)
                                    st.download_button(
                                        label="📥 Download Verification Report",
                                        data=csv_data,
                                        file_name=f"background_verification_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                        mime="text/csv",
                                        use_container_width=True,
                                        key=f"dl_background_{session_id}"
                                    )
                                else:
                                    st.info("No candidate details available in the verification data")
                            else:
                                st.info("No candidates have been verified yet")
                        else:
                            # Show simple message if data exists but no verified_candidates
                            if background_data:
                                st.info("Background verification completed")
                    else:
                        st.info("No background verification data available")
            
            # ================================================
            # JOB DESCRIPTION VIEW (Separate section below tabs)
            # ================================================
            st.markdown("---")
            with st.expander("📋 View Job Description", expanded=False):
                job_description = session_data.get('job_description', 'No job description available')
                if job_description and job_description.strip():
                    st.markdown(f"### Job Description for: {job_title}")
                    st.text_area(
                        "", 
                        job_description, 
                        height=200, 
                        disabled=True, 
                        label_visibility="collapsed",
                        key=f"jd_view_{session_id}"
                    )
                else:
                    st.info("No job description available for this session")
            
            # ================================================
            # ACTION BUTTONS (bottom of session card)
            # ================================================
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col2:
                # Delete button with confirmation
                delete_key = f"delete_{session_id}"
                if delete_key not in st.session_state:
                    st.session_state[delete_key] = False
                
                if not st.session_state[delete_key]:
                    if st.button("🗑️ Delete Session", key=f"del_btn_{session_id}", type="secondary", use_container_width=True):
                        st.session_state[delete_key] = True
                        st.rerun()
                else:
                    st.warning("⚠️ Are you sure you want to delete this session?")
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button("✅ Yes, Delete", key=f"confirm_{session_id}", use_container_width=True):
                            # Delete from database
                            success = delete_session(session_id, st.session_state.user['id'])
                            if success:
                                # Clean up files
                                cleanup_session_files(session_id, session_name)
                                st.success("✅ Session deleted successfully!")
                                time.sleep(1)
                                st.rerun()
                    with cancel_col:
                        if st.button("❌ Cancel", key=f"cancel_{session_id}", use_container_width=True):
                            st.session_state[delete_key] = False
                            st.rerun()
# Add this function to your database module or create it in app.py
def update_session_in_db(session_id, update_data):
    """Update session data in database"""
    try:
        # This is a placeholder - you need to implement based on your database
        # For SQLite example:
        import sqlite3
        
        conn = sqlite3.connect('recruitment.db')
        cursor = conn.cursor()
        
        # Build update query
        set_clauses = []
        values = []
        
        for key, value in update_data.items():
            if key == 'results_data' and isinstance(value, dict):
                value = json.dumps(value)
            set_clauses.append(f"{key} = ?")
            values.append(value)
        
        values.append(session_id)
        query = f"UPDATE sessions SET {', '.join(set_clauses)} WHERE id = ?"
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        return True
    except Exception as e:
        print(f"Error updating session: {e}")
        return False
    
def get_session_with_candidates(session_id):
    """Get complete session data with candidates"""
    try:
        # Get session from database
        session = get_session_details(session_id)
        if not session:
            return None
        
        # Load session data
        session_data = load_session_data(session)
        
        # If no candidates in session_data, try to load from output files
        if not session_data.get('candidates'):
            # Try to load from session folder
            results_data = session_data.get('results_data', {})
            session_folder = results_data.get('session_folder')
            
            if session_folder and os.path.exists(session_folder):
                output_folder = os.path.join(session_folder, 'output')
                if os.path.exists(output_folder):
                    # Load screening results
                    screening_file = os.path.join(output_folder, 'screening_results.json')
                    if os.path.exists(screening_file):
                        with open(screening_file, 'r') as f:
                            screening_data = json.load(f)
                            if 'eligible_candidates' in screening_data:
                                candidates = []
                                for cand in screening_data['eligible_candidates']:
                                    if isinstance(cand, dict) and 'candidate_info' in cand:
                                        info = cand['candidate_info']
                                        candidates.append({
                                            'name': info.get('name', 'Unknown'),
                                            'email': info.get('email', ''),
                                            'status': 'eligible'
                                        })
                                session_data['candidates'] = candidates
                    
                    # Load ranking results
                    ranking_file = os.path.join(output_folder, 'candidate_ranking_report.json')
                    if os.path.exists(ranking_file):
                        with open(ranking_file, 'r') as f:
                            ranking_data = json.load(f)
                            if 'candidates' in ranking_data:
                                # Merge with existing candidates
                                existing_candidates = {c['email']: c for c in session_data.get('candidates', [])}
                                for cand in ranking_data['candidates']:
                                    if isinstance(cand, dict):
                                        email = cand.get('email', '')
                                        if email in existing_candidates:
                                            existing_candidates[email].update({
                                                'rank': cand.get('rank'),
                                                'score': cand.get('score')
                                            })
                                        else:
                                            existing_candidates[email] = {
                                                'name': cand.get('name', 'Unknown'),
                                                'email': email,
                                                'rank': cand.get('rank'),
                                                'score': cand.get('score')
                                            }
                                session_data['candidates'] = list(existing_candidates.values())
        
        return session_data
        
    except Exception as e:
        st.error(f"Error loading session: {e}")
        return None
    
def show_session_detail_page():
    """Simple job description view (if you still want a separate page)"""
    load_css("other")
    
    if not st.session_state.authenticated:
        navigate_to("login")
        return
    
    session_data = st.session_state.get('viewing_session')
    
    if not session_data:
        st.error("Session not found")
        if st.button("← Back to Sessions"):
            navigate_to("previous_sessions")
        return
    
    # Back button
    if st.button("← Back to Sessions"):
        navigate_to("previous_sessions")
        return
    
    # Simple view
    st.markdown(f"### {session_data.get('session_name', 'Session')}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Job Title", session_data.get('job_title', 'N/A'))
    with col2:
        st.metric("Total Resumes", session_data.get('resume_count', 0))
    
    st.markdown("#### Job Description")
    jd = session_data.get('job_description', 'No job description available')
    st.text_area("", jd, height=300, disabled=True, label_visibility="collapsed")

def cleanup_session_files(session_id, session_name=None):
    """Clean up files associated with a specific session only"""
    try:
        deleted_count = 0
        
        # First, look for exact session folder with session_id
        exact_patterns = [
            f"session_{session_id}_*",  # Exact session ID match
            f"*session_{session_id}*",  # Contains session ID
        ]
        
        # Also look by session name if provided
        if session_name:
            session_name_slug = session_name.replace(' ', '_').replace('/', '_')[:50]
            exact_patterns.append(f"*{session_name_slug}*")
        
        # Search and delete ONLY matching folders/files
        for pattern in exact_patterns:
            for item in glob.glob(pattern):
                try:
                    # Skip if it doesn't contain the session ID in a specific way
                    if f"session_{session_id}" not in item and session_id not in item:
                        continue
                    
                    if os.path.isfile(item):
                        os.remove(item)
                        deleted_count += 1
                        print(f"Deleted file: {item}")
                    elif os.path.isdir(item):
                        # Double check it's the right session
                        if f"session_{session_id}" in item or (session_name_slug and session_name_slug in item):
                            shutil.rmtree(item)
                            deleted_count += 1
                            print(f"Deleted folder: {item}")
                except Exception as e:
                    print(f"Could not delete {item}: {e}")
        
        # Also check data and output subfolders
        for base_folder in ['data', 'output', 'temp']:
            if os.path.exists(base_folder):
                for item in os.listdir(base_folder):
                    item_path = os.path.join(base_folder, item)
                    # Only delete if it contains the session ID
                    if str(session_id) in item or (session_name and session_name.replace(' ', '_') in item):
                        try:
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                deleted_count += 1
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                                deleted_count += 1
                        except:
                            pass
        
        return deleted_count > 0
        
    except Exception as e:
        print(f"Error in cleanup_session_files: {e}")
        return False
# Main application
def main():
    """Main application router"""
    
    # Set page config
    st.set_page_config(
        page_title="HireIQ",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Hide sidebar
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Route to page
    if st.session_state.current_page == "login":
        show_login_page()
    elif st.session_state.current_page == "home":
        show_home_page()
    elif st.session_state.current_page == "new_recruitment":
        show_new_recruitment_page()
    elif st.session_state.current_page == "results":
        show_results_page()
    elif st.session_state.current_page == "previous_sessions":
        show_previous_sessions_page()
    elif st.session_state.current_page == "session_detail":
        show_session_detail_page()
    else:
        st.session_state.current_page = "login"
        show_login_page()

if __name__ == "__main__":
    main()