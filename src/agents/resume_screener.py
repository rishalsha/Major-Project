import os
import json
from typing import Dict, List, Any
from src.utils.file_parser import ResumeParser
from src.utils.llm_helper import LLMHelper

class ResumeScreeningAgent:
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        if use_llm:
            self.llm_helper = LLMHelper()
        self.parser = ResumeParser()
        
        if use_llm and self.llm_helper.is_available():
            print("✅ LLM screening enabled and available")
        elif use_llm:
            print("⚠️ LLM screening enabled but not available")

    def screen_resume(self, resume_path: str, job_description: str) -> Dict[str, Any]:
        """Screen a single resume and extract comprehensive information"""
        try:
            # Parse resume
            resume_text = self.parser.parse_resume(resume_path)
            if not resume_text:
                return {
                    "file": resume_path,
                    "filename": os.path.basename(resume_path),
                    "eligible": False,
                    "reason": "Could not parse resume text",
                    "error": True
                }

            # Use LLM for screening if available
            if self.use_llm and self.llm_helper.is_available():
                result = self.llm_helper.screen_eligibility(resume_text, job_description)
                result["file"] = resume_path
                result["filename"] = os.path.basename(resume_path)
                result["resume_text_preview"] = resume_text[:500] + "..." if len(resume_text) > 500 else resume_text
                return result
            else:
                # Fallback if LLM not available
                return {
                    "file": resume_path,
                    "filename": os.path.basename(resume_path),
                    "eligible": False,
                    "reason": "LLM screening not available",
                    "meets_minimum_requirements": False
                }
                
        except Exception as e:
            return {
                "file": resume_path,
                "filename": os.path.basename(resume_path),
                "eligible": False,
                "reason": f"Screening error: {str(e)}",
                "error": True
            }

    def bulk_screen(self, resume_paths: List[str], job_description: str) -> Dict[str, Any]:
        """Bulk screen all resumes - returns ONLY eligible candidates"""
        eligible_resumes = []
        ineligible_resumes = []
        errors = []
        total = len(resume_paths)
        
        print(f"🔍 Screening {total} resumes for eligibility...")
        print("🎯 Output: ONLY eligible resumes will be passed to Background Check Agent")
        
        for i, resume_path in enumerate(resume_paths, 1):
            filename = os.path.basename(resume_path)
            print(f"   {i}/{total}: {filename}")
            
            result = self.screen_resume(resume_path, job_description)
            
            if result.get("error"):
                errors.append(result)
                print(f"      ❌ ERROR - {result.get('reason', 'Unknown error')}")
            elif result.get("eligible"):
                eligible_resumes.append(result)
                # Show profile links if available
                profile_info = ""
                if result.get("profile_links", {}).get("linkedin"):
                    profile_info += " | LinkedIn: ✅"
                if result.get("profile_links", {}).get("github"):
                    profile_info += " | GitHub: ✅"
                
                print(f"      ✅ ELIGIBLE{profile_info}")
            else:
                ineligible_resumes.append(result)
                print(f"      ❌ INELIGIBLE - {result.get('reason', 'Does not meet requirements')}")
        
        return {
            "eligible_candidates": eligible_resumes,  # Only these go to background agent
            "ineligible_candidates": ineligible_resumes,
            "errors": errors,
            "summary": {
                "total_screened": total,
                "eligible_count": len(eligible_resumes),
                "ineligible_count": len(ineligible_resumes),
                "error_count": len(errors)
            }
        }