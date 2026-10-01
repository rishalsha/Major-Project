import pdfplumber
import docx
import os
import re
import zipfile
from typing import Optional, List

class ResumeParser:
    @staticmethod
    def extract_zip(zip_path: str, extract_to: str) -> List[str]:
        """Extract resumes from zip file (handles nested folders)"""
        all_files = []
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
                # Get all extracted files
                for root, dirs, files in os.walk(extract_to):
                    for file in files:
                        if file.lower().endswith(('.pdf', '.docx', '.txt')):
                            full_path = os.path.join(root, file)
                            all_files.append(full_path)
            print(f"✅ Extracted {len(all_files)} resume files from zip")
            return all_files
        except Exception as e:
            print(f"❌ Error extracting zip: {e}")
            return []

    @staticmethod
    def parse_pdf(file_path: str) -> Optional[str]:
        """Extract text from PDF resume"""
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip() if text else None
        except Exception as e:
            print(f"Error parsing PDF {file_path}: {e}")
            return None

    @staticmethod
    def parse_docx(file_path: str) -> Optional[str]:
        """Extract text from DOCX resume"""
        try:
            doc = docx.Document(file_path)
            full_text = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    full_text.append(paragraph.text)
            return "\n".join(full_text).strip() if full_text else None
        except Exception as e:
            print(f"Error parsing DOCX {file_path}: {e}")
            return None

    @staticmethod
    def parse_resume(file_path: str) -> Optional[str]:
        """Main method to parse any resume format"""
        if not os.path.exists(file_path):
            return None
        
        file_ext = file_path.lower().split('.')[-1]
        text = None
        
        if file_ext == 'pdf':
            text = ResumeParser.parse_pdf(file_path)
        elif file_ext == 'docx':
            text = ResumeParser.parse_docx(file_path)
        elif file_ext == 'txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        
        return text

    @staticmethod
    def get_all_resumes(folder_path: str) -> List[str]:
        """Get all resume files from folder (including subfolders)"""
        resume_files = []
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if filename.lower().endswith(('.pdf', '.docx', '.txt')):
                    full_path = os.path.join(root, filename)
                    resume_files.append(full_path)
        return resume_files