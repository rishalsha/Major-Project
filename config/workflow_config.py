"""
Simple Workflow Configuration
1. Try to auto-determine from JD using LLM
2. If fails, use default full pipeline
"""

from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass, field
import json
import os

# Workflow types
class WorkflowType(Enum):
    AUTO_DETERMINED = "auto_determined"
    FULL_PIPELINE = "full_pipeline"
    SKIP_BACKGROUND = "skip_background"
    SKIP_SCREENING = "skip_screening"
    RANKING_ONLY = "ranking_only"
    QUICK_SCHEDULE = "quick_schedule"

# Try to import JD analyzer
try:
    from src.utils.jd_analyzer import analyze_job_description, extract_job_title_llm
    JD_ANALYZER_AVAILABLE = True
except ImportError:
    JD_ANALYZER_AVAILABLE = False
    print("⚠️  JD analyzer not available, will use default full pipeline")


@dataclass
class WorkflowConfig:
    workflow_type: WorkflowType = WorkflowType.AUTO_DETERMINED
    ical_url: Optional[str] = None
    jd_text: Optional[str] = None
    config: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Pure data container - Reasoning happens in Orchestrator"""
        # Default flags, will be refined by Orchestrator reasoning node
        if not self.config:
            self.config = {
                "run_screening": True,
                "run_background": False,
                "run_ranking": True,
                "run_scheduling": False,
                "run_communication": False
            }
    
    def _use_default(self):
        """Use default full pipeline"""
        print("📋 Using default full pipeline")
        
        self.config = {
            "description": "Default Full Pipeline",
            "run_screening": True,
            "run_background": True,  # Default to true for safety
            "run_ranking": True,
            "run_scheduling": True,
            "run_communication": True,
            "jd_analysis": {},
            "semantic_decisions": {
                "is_technical": True,
                "has_interview": True,
                "just_ranking": False,
                "needs_background_verification": True,
                "semantic_reasoning": "Default workflow - assuming technical role with interviews and verification"
            }
        }
    
    def get_workflow_steps(self) -> List[str]:
        """Get steps to execute"""
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
    
    def get_job_title(self) -> str:
        """Extract job title from JD or use default"""
        if not self.jd_text or not JD_ANALYZER_AVAILABLE:
            return "Position"
        
        try:
            return extract_job_title_llm(self.jd_text)
        except:
            return "Position"


# Simple helper function
def create_workflow(jd_text: str = None, ical_url: str = None) -> WorkflowConfig:
    """Create workflow config"""
    return WorkflowConfig(
        ical_url=ical_url,
        jd_text=jd_text
    )