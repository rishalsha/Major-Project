"""
AI Recruitment System - LangGraph Orchestration
Handles dynamic workflow based on JD analysis
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Any, List
from typing_extensions import TypedDict
import asyncio
import json
import os
from config.workflow_config import WorkflowConfig, WorkflowType

# Define the state that flows between agents
class RecruitmentState(TypedDict):
    candidates: list
    screening_results: Dict[str, Any]
    background_results: Dict[str, Any]
    ranking_results: Dict[str, Any]
    scheduled_interviews: Dict[str, Any]
    communication_results: Dict[str, Any]
    current_step: str
    error: str
    workflow_config: Dict[str, Any]
    jd_analysis: Dict[str, Any]
    requires_frontend_action: bool
    frontend_action: Dict[str, Any]
    reasoning: Dict[str, str]  # Added for ReAct reasoning

class RecruitmentOrchestrator:
    def __init__(self, workflow_config: WorkflowConfig):
        # Import agents here to avoid circular imports
        from src.agents.resume_screener import ResumeScreeningAgent
        from src.agents.background_analyzer import BackgroundVerifierLocalAgent
        from src.agents.candidate_ranker import CandidateRankingAgent
        from src.agents.calendar_scheduling_agent import CalendarSchedulingAgent
        from src.agents.communication_agent import CommunicationAgent
        from src.utils.jd_analyzer import SemanticJDAnalyzer
        
        self.screening_agent = ResumeScreeningAgent(use_llm=True)
        self.background_agent = BackgroundVerifierLocalAgent()
        self.ranking_agent = CandidateRankingAgent()
        self.scheduling_agent = CalendarSchedulingAgent()
        self.communication_agent = CommunicationAgent()
        self.jd_analyzer = SemanticJDAnalyzer()
        self.workflow_config = workflow_config
        
        self.workflow = self._create_workflow()
    
    def _create_workflow(self):
        """Create dynamic ReAct-based workflow using conditional edges"""
        workflow = StateGraph(RecruitmentState)
        
        # Add all possible nodes
        workflow.add_node("jd_reasoner", self._run_jd_reasoner)
        workflow.add_node("screening", self._run_screening)
        workflow.add_node("background_check", self._run_background_check)
        workflow.add_node("ranking", self._run_ranking)
        workflow.add_node("scheduling", self._run_scheduling)
        workflow.add_node("communication", self._run_communication)
        
        # Set entry point
        workflow.set_entry_point("jd_reasoner")
        
        # Edge from jd_reasoner always goes to screening
        workflow.add_edge("jd_reasoner", "screening")
        
        # Define conditional routing from screening
        workflow.add_conditional_edges(
            "screening",
            self._router_after_screening,
            {
                "run_background": "background_check",
                "skip_background": "ranking"
            }
        )
        
        # Edge from background check always goes to ranking
        workflow.add_edge("background_check", "ranking")
        
        # Define conditional routing from ranking
        workflow.add_conditional_edges(
            "ranking",
            self._router_after_ranking,
            {
                "run_scheduling": "scheduling",
                "skip_scheduling": END
            }
        )
        
        # Edge from scheduling always goes to communication
        workflow.add_edge("scheduling", "communication")
        
        # Communication is the final step
        workflow.add_edge("communication", END)
        
        return workflow.compile()
    
    async def _run_jd_reasoner(self, state: RecruitmentState) -> RecruitmentState:
        """Analyze Job Description at the start of the flow to inform reasoning"""
        print("\n🧠 AGENTIC REASONING: Analyzing Job Description...")
        
        try:
            # Read JD from file (common practice in this project)
            jd_path = "job_description.txt"
            if os.path.exists(jd_path):
                with open(jd_path, "r", encoding='utf-8') as f:
                    job_description = f.read()
            else:
                # Fallback to config
                job_description = self.workflow_config.jd_text or ""
            
            if not job_description:
                print("⚠️ No job description found for analysis.")
                return state
                
            # Perform semantic analysis - This is the ONLY place this happens now
            user_prefs = {
                "is_just_ranking": self.workflow_config.config.get("is_just_ranking", False),
                "needs_scheduling": self.workflow_config.config.get("run_scheduling", True)
            }
            
            semantic_analysis = self.jd_analyzer.reason_about_workflow(job_description, user_prefs)
            
            # Store in state for routers to use
            state["jd_analysis"] = semantic_analysis
            state["current_step"] = "jd_analyzed"
            
            if semantic_analysis.get('semantic_reasoning'):
                print(f"   • Reasoning: {semantic_analysis['semantic_reasoning']}")
            
            print(f"   • Detected Position: {semantic_analysis.get('job_title', 'Not specified')}")
            print(f"   • Analysis: {'Technical' if semantic_analysis.get('is_technical') else 'General'} role, " + 
                  f"{'Interview' if semantic_analysis.get('has_interview') else 'Ranking only'} path")
                
        except Exception as e:
            print(f"❌ JD Analysis error: {e}")
            state["error"] = f"JD Analysis failed: {str(e)}"
            
        return state

    def _router_after_screening(self, state: RecruitmentState) -> str:
        """Reason whether background check is needed after screening"""
        print("\n🤔 REASONING: Is background check needed?")
        
        # Get data for reasoning
        jd_analysis = state.get("jd_analysis", {})
        is_technical = jd_analysis.get("is_technical", False)
        
        # Get user preference from workflow config
        config = state.get("workflow_config", {})
        user_wants_background = config.get("run_background", False)
        
        # ReAct reasoning logic
        decision = ""
        reason = ""
        
        print(f"   • Context: Technical Role={is_technical}, User Preference={user_wants_background}")
        
        if is_technical:
            reason = "Role identified as technical. Reasoning: Technical profiles (GitHub/Portfolio) require verification for accuracy."
            decision = "run_background"
        elif user_wants_background:
            reason = "User explicitly requested background check for this recruitment session."
            decision = "run_background"
        else:
            reason = "Role is non-technical and no explicit background check was requested. Skipping to ranking."
            decision = "skip_background"
            
        print(f"   💡 Reasoning: {reason}")
        print(f"   🎯 Decision: {decision}")
        
        # Store reasoning in state
        if "reasoning" not in state or state["reasoning"] is None:
            state["reasoning"] = {}
        state["reasoning"]["after_screening"] = reason
        
        return decision

    def _router_after_ranking(self, state: RecruitmentState) -> str:
        """Reason whether interview scheduling is needed after ranking"""
        print("\n🤔 REASONING: Is interview scheduling needed?")
        
        # Get data for reasoning
        jd_analysis = state.get("jd_analysis", {})
        just_ranking = jd_analysis.get("just_ranking", False)
        has_interview = jd_analysis.get("has_interview", True)
        
        # Get user preference from workflow config
        config = state.get("workflow_config", {})
        user_wants_scheduling = config.get("run_scheduling", False)
        is_just_ranking_config = config.get("is_just_ranking", False)
        
        # ReAct reasoning logic
        reason = ""
        decision = ""
        
        print(f"   • Context: Just Ranking={just_ranking or is_just_ranking_config}, Has Interview={has_interview}, Scheduling Enabled={user_wants_scheduling}")
        
        if just_ranking or is_just_ranking_config:
            reason = "User requested 'Just Ranking' or JD excludes interview process. Finalizing after ranking."
            decision = "skip_scheduling"
        elif not has_interview:
            reason = "JD analysis indicates no primary interview process is required for this specific role."
            decision = "skip_scheduling"
        elif user_wants_scheduling:
            reason = "Interview process is required and automated scheduling is active. Proceeding to calendar agent."
            decision = "run_scheduling"
        else:
            reason = "Scheduling was not enabled for this session. Completing recruitment flow."
            decision = "skip_scheduling"
            
        print(f"   💡 Reasoning: {reason}")
        print(f"   🎯 Decision: {decision}")
        
        # Store reasoning in state
        if "reasoning" not in state or state["reasoning"] is None:
            state["reasoning"] = {}
        state["reasoning"]["after_ranking"] = reason
        
        return decision
    
    async def _run_screening(self, state: RecruitmentState) -> RecruitmentState:
        """Run resume screening agent"""
        print("\n" + "="*50)
        print("🚀 STEP 1: RESUME SCREENING")
        print("="*50)
        
        try:
            # Extract resumes from uploaded zip
            resume_paths = self._extract_resumes_from_zip()
            if not resume_paths:
                state["error"] = "No resumes found to process."
                return state
            
            # Read job description
            if not os.path.exists("job_description.txt"):
                state["error"] = "Job description file not found."
                return state
            
            with open("job_description.txt", "r", encoding='utf-8') as f:
                job_description = f.read()

            # Run screening
            screening_results = self.screening_agent.bulk_screen(resume_paths, job_description)
            
            # Save results
            os.makedirs("output", exist_ok=True)
            with open("output/screening_results.json", "w", encoding='utf-8') as f:
                json.dump(screening_results, f, indent=2, ensure_ascii=False)
            
            # Update state
            state["screening_results"] = screening_results
            state["current_step"] = "screening_completed"
            
            # JD analysis is now done by the jd_reasoner node
            # We just ensure it's in the state, falling back to config if needed
            if not state.get("jd_analysis"):
                jd_analysis = self.workflow_config.config.get("jd_analysis", {})
                state["jd_analysis"] = jd_analysis
            
            # Store eligible candidates
            eligible_candidates = screening_results.get('eligible_candidates', [])
            state["candidates"] = eligible_candidates
            
            # Initialize frontend action flags
            state["requires_frontend_action"] = False
            state["frontend_action"] = {}
            
            # Show summary
            eligible_count = screening_results.get('summary', {}).get('eligible_count', 0)
            print(f"✅ Screening completed. Eligible candidates: {eligible_count}")
            
        except Exception as e:
            state["error"] = f"Screening failed: {str(e)}"
            print(f"❌ Screening error: {e}")
        
        return state
    
    async def _run_background_check(self, state: RecruitmentState) -> RecruitmentState:
        """Run background verification agent - only if enabled in workflow"""
        print("\n" + "="*50)
        print("🔍 STEP 2: BACKGROUND VERIFICATION")
        print("="*50)
        
        try:
            # Background check run is now determined by the router, 
            # but we still check the flag here for extra safety if called directly
            run_background = self.workflow_config.config.get("run_background", False)
            jd_analysis = state.get("jd_analysis", {})
            is_technical = jd_analysis.get("is_technical", False)
            
            if not run_background and not is_technical:
                print("   ⏭️ Skipping background check (not needed based on Reasoning)")
                state["background_results"] = {"status": "skipped", "reason": "reasoning_decided_skip"}
                return state
            
            # Run background check
            screening_results = state.get("screening_results", {})
            if not screening_results:
                print("   ⚠️ No screening results found")
                state["background_results"] = {"status": "skipped", "reason": "no_screening_results"}
                return state
            
            background_results = await self.background_agent.verify_candidates(screening_results)
            state["background_results"] = background_results
            state["current_step"] = "background_check_completed"
            print("✅ Background verification completed")
            
        except Exception as e:
            state["error"] = f"Background verification failed: {str(e)}"
            print(f"❌ Background verification error: {e}")
        
        return state
    
    async def _run_ranking(self, state: RecruitmentState) -> RecruitmentState:
        """Run ranking agent with dynamic input based on workflow"""
        print("\n" + "="*50)
        print("📊 STEP 3: CANDIDATE RANKING")
        print("="*50)
        
        try:
            # Get workflow decisions
            jd_analysis = state.get("jd_analysis", {})
            run_background = self.workflow_config.config.get("run_background", False)
            is_technical = jd_analysis.get("is_technical", False)
            
            print(f"🤖 RANKING SETUP:")
            print(f"   • Is Technical Role: {is_technical}")
            print(f"   • Background Check Enabled: {run_background}")
            
            # Prepare ranking input based on what's available
            ranking_input = {}
            background_results = state.get("background_results", {})
            
            # SCENARIO 1: Background check data is available in state
            if background_results and "verified_candidates" in background_results and background_results["verified_candidates"]:
                print("   📋 Using background verification results")
                ranking_input = {
                    "verified_candidates": background_results.get("verified_candidates", []),
                    "screening_results": state.get("screening_results", {})
                }
            
            # SCENARIO 2: No background data, use screening results
            else:
                if background_results:
                     print("   📋 Background run but no verified candidates, using screening")
                else:
                     print("   📋 Using screening results (background check not performed)")
                     
                ranking_input = {
                    "screening_results": state.get("screening_results", {})
                }
            
            # Check if we have data to rank
            if not ranking_input.get("screening_results") and not ranking_input.get("verified_candidates"):
                print("⚠️ No candidate data available for ranking")
                state["ranking_results"] = {
                    "ranking_report": {
                        "ranked_candidates": [],
                        "total_candidates_ranked": 0
                    }
                }
                state["current_step"] = "ranking_skipped"
                return state
            
            # Run ranking with the prepared input
            print(f"🤖 Calling ranking agent...")
            ranking_results = self.ranking_agent.rank_candidates(ranking_input)
            
            if not ranking_results:
                print("⚠️ Ranking returned empty")
                # Create minimal ranking from screening results
                screening_results = state.get("screening_results", {})
                eligible_candidates = screening_results.get("eligible_candidates", [])
                
                basic_ranking = {
                    "ranking_report": {
                        "ranked_candidates": [],
                        "total_candidates_ranked": 0
                    }
                }
                if eligible_candidates:
                    # Create simple ranking
                    ranked = []
                    for i, candidate in enumerate(eligible_candidates[:10], 1):
                        candidate_info = candidate.get("candidate_info", {})
                        ranked.append({
                            "name": candidate_info.get("name", f"Candidate {i}"),
                            "candidate_name": candidate_info.get("name", f"Candidate {i}"),
                            "rank": i,
                            "comprehensive_score": candidate.get("overall_score", 5.0),
                            "source": "screening_fallback"
                        })
                    
                    basic_ranking["ranking_report"]["ranked_candidates"] = ranked
                    basic_ranking["ranking_report"]["total_candidates_ranked"] = len(ranked)
                
                ranking_results = basic_ranking
            
            # Update state
            state["ranking_results"] = ranking_results
            state["current_step"] = "ranking_completed"
            
            # Show results
            ranked_candidates = ranking_results.get("ranking_report", {}).get("ranked_candidates", [])
            print(f"✅ Ranking completed: {len(ranked_candidates)} candidates ranked")
            
            if ranked_candidates:
                print(f"\n🏆 TOP 5 CANDIDATES:")
                for i, candidate in enumerate(ranked_candidates[:5], 1):
                    name = candidate.get("name", candidate.get("candidate_name", f"Candidate {i}"))
                    score = candidate.get("comprehensive_score", candidate.get("score", 0))
                    print(f"   {i}. {name} - Score: {score:.1f}/10")
            
        except Exception as e:
            state["error"] = f"Ranking failed: {str(e)}"
            print(f"❌ Ranking error: {e}")
            import traceback
            traceback.print_exc()
        
        return state
    
    async def _run_scheduling(self, state: RecruitmentState) -> RecruitmentState:
        """Run scheduling agent - FIXED VERSION"""
        print("\n" + "="*50)
        print("🗓️ STEP 4: CALENDAR SCHEDULING")
        print("="*50)
        
        try:
            # Check if interviews are needed
            jd_analysis = state.get("jd_analysis", {})
            has_interview = jd_analysis.get("has_interview", True)
            just_ranking = jd_analysis.get("just_ranking", False)
            
            if just_ranking or not has_interview:
                print(f"   ⏭️ Skipping scheduling")
                state["scheduled_interviews"] = {"scheduled_interviews": []}
                state["current_step"] = "scheduling_skipped"
                return state
            
            # Check if we have candidates to schedule
            ranking_results = state.get("ranking_results", {})
            if not ranking_results:
                print("   ⚠️ No ranking results available")
                state["scheduled_interviews"] = {"scheduled_interviews": []}
                state["current_step"] = "scheduling_completed"
                return state
            
            # Get calendar URL
            calendar_url = self.workflow_config.ical_url
            if not calendar_url:
                print("   ⚠️ No calendar URL provided")
                state["scheduled_interviews"] = {"scheduled_interviews": []}
                state["current_step"] = "scheduling_completed"
                return state
            
            # Get interview mode
            interview_mode = self.workflow_config.config.get("interview_mode", "online")
            
            print(f"   📅 Using calendar: {calendar_url[:50]}...")
            print(f"   💻 Interview mode: {interview_mode}")
            
            # Run scheduling
            scheduling_results = await self.scheduling_agent.schedule_interviews(
                ranking_results,
                calendar_url=calendar_url,
                interview_mode=interview_mode
            )
            
            # Update state
            state["scheduled_interviews"] = scheduling_results
            
            # Check scheduling status
            status = scheduling_results.get("status", "unknown")
            
            if status == "complete":
                print(f"\n✅ SCHEDULING COMPLETE")
                state["current_step"] = "scheduling_completed"
            elif status == "partial":
                print(f"\n⚠️ SCHEDULING PARTIAL")
                state["current_step"] = "scheduling_partial"
                state["requires_frontend_action"] = True
                state["frontend_action"] = scheduling_results.get("frontend_action", {})
            else:
                print(f"\n⚠️ SCHEDULING ISSUE")
                state["current_step"] = "scheduling_issue"
                state["requires_frontend_action"] = True
                state["frontend_action"] = scheduling_results.get("frontend_action", {})
            
            return state
            
        except Exception as e:
            print(f"❌ Scheduling error: {e}")
            state["error"] = f"Scheduling failed: {str(e)}"
            return state
    
    async def _run_communication(self, state: RecruitmentState) -> RecruitmentState:
        """Send confirmation emails - only if interviews were scheduled"""
        print("\n" + "="*50)
        print("📧 STEP 5: SENDING CONFIRMATION EMAILS")
        print("="*50)
        
        try:
            # Get scheduled interviews
            scheduled_interviews = state.get("scheduled_interviews", {}).get("scheduled_interviews", [])
            
            if not scheduled_interviews:
                print("   ⚠️ No interviews scheduled, skipping communication")
                state["current_step"] = "communication_skipped"
                return state
            
            # Get configuration
            job_title = self.workflow_config.config.get("job_title", "Position")
            interview_mode = self.workflow_config.config.get("interview_mode", "online")
            location = self.workflow_config.config.get("location", "")
            company_name = self.workflow_config.config.get("company_name", "Our Company")
            panel_members = self.workflow_config.config.get("panel_members", "Interview Panel")
            
            print(f"   📧 Sending emails for {len(scheduled_interviews)} interviews")
            print(f"   🏢 Company: {company_name}")
            print(f"   📋 Job: {job_title}")
            
            # Send emails
            communication_results = await self.communication_agent.send_interview_confirmation(
                scheduled_interviews=scheduled_interviews,
                interview_mode=interview_mode,
                location=location,
                company_name=company_name,
                panel_members=panel_members,
                job_title=job_title
            )
            
            state["communication_results"] = communication_results
            state["current_step"] = "communication_completed"
            
            # Show results
            status = communication_results.get("status", "unknown")
            emails_sent = communication_results.get("emails_sent", 0)
            
            if status == "success":
                print(f"✅ {emails_sent} emails sent successfully")
            elif status == "test_mode":
                print(f"🧪 TEST MODE: {emails_sent} emails logged (not sent)")
            else:
                print(f"⚠️ Email status: {status}")
            
        except Exception as e:
            state["error"] = f"Communication failed: {str(e)}"
            print(f"❌ Communication error: {e}")
        
        return state
    
    async def continue_scheduling_with_new_calendar(self, new_calendar_url: str) -> Dict[str, Any]:
        """
        Reschedule ALL candidates with new calendar URL - WORKING VERSION
        """
        print("\n" + "="*60)
        print("🔄 RESCHEDULING ALL CANDIDATES WITH NEW CALENDAR")
        print("="*60)
        
        try:
            # Get interview mode from config
            interview_mode = self.workflow_config.config.get("interview_mode", "online")
            
            print(f"   📅 New calendar: {new_calendar_url[:50]}...")
            print(f"   💻 Interview mode: {interview_mode}")
            
            # Call the scheduling agent's rescheduling method
            result = await self.scheduling_agent.update_calendar_and_continue(
                new_calendar_url=new_calendar_url,
                interview_mode=interview_mode
            )
            
            # Check result status
            status = result.get("status", "unknown")
            
            if status == "complete":
                print(f"\n✅ RESCHEDULING COMPLETE: {result.get('message', 'All candidates scheduled')}")
                
                # Send emails for ALL newly scheduled interviews
                scheduled_interviews = result.get("scheduled_interviews", [])
                if scheduled_interviews:
                    print(f"\n📧 Sending confirmation emails for {len(scheduled_interviews)} interviews")
                    
                    # Get configuration
                    job_title = self.workflow_config.config.get("job_title", "Position")
                    location = self.workflow_config.config.get("location", "")
                    company_name = self.workflow_config.config.get("company_name", "Our Company")
                    panel_members = self.workflow_config.config.get("panel_members", "Interview Panel")
                    
                    communication_results = await self.communication_agent.send_interview_confirmation(
                        scheduled_interviews=scheduled_interviews,
                        interview_mode=interview_mode,
                        location=location,
                        company_name=company_name,
                        panel_members=panel_members,
                        job_title=job_title
                    )
                    
                    result["communication_results"] = communication_results
                    print(f"✅ Email communication completed: {communication_results.get('emails_sent', 0)} emails sent")
            
            elif status == "partial":
                print(f"\n⚠️ RESCHEDULING PARTIAL: {result.get('message', 'Some candidates scheduled')}")
                print(f"   ⏸️  Frontend action required for remaining candidates")
                
            elif status in ["no_slots", "need_more_slots"]:
                print(f"\n❌ RESCHEDULING FAILED: {result.get('message', 'No slots available')}")
                print(f"   ⚠️  Need another calendar with more slots")
                
            elif status == "error":
                print(f"\n❌ RESCHEDULING ERROR: {result.get('message', 'Error occurred')}")
                
            return result
            
        except Exception as e:
            print(f"❌ Error rescheduling: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "status": "error",
                "message": str(e),
                "scheduled_interviews": []
            }
    def _extract_resumes_from_zip(self) -> List[str]:
        """Extract resumes from uploaded zip file"""
        zip_path = "data/resumes.zip"
        extract_path = "data/resumes_extracted"
        
        if not os.path.exists(zip_path):
            # Check for alternative paths
            if os.path.exists("resumes.zip"):
                zip_path = "resumes.zip"
            else:
                raise FileNotFoundError("No resume zip file found")
        
        import zipfile
        
        os.makedirs(extract_path, exist_ok=True)
        resume_files = []
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        for root, _, files in os.walk(extract_path):
            for file in files:
                if file.lower().endswith(('.pdf', '.docx', '.txt')):
                    resume_files.append(os.path.join(root, file))
        
        return resume_files
    
    async def run_recruitment_pipeline(self) -> Dict[str, Any]:
        """Run the complete recruitment pipeline"""
        print("\n" + "="*60)
        print("🎯 STARTING RECRUITMENT PIPELINE")
        print("="*60)
        
        # Get configuration
        config = self.workflow_config.config
        
        print(f"\n🏢 Company: {config.get('company_name', 'Not specified')}")
        print(f"💻 Interview Mode: {config.get('interview_mode', 'online')}")
        print("\n🚀 STARTING AGENTIC REASONING FLOW (Autonomous JD Analysis)...")
        print("="*60)
        
        # Create initial state
        initial_state = RecruitmentState(
            candidates=[],
            screening_results={},
            background_results={},
            ranking_results={},
            scheduled_interviews={},
            communication_results={},
            current_step="started",
            error="",
            workflow_config=config,
            jd_analysis={},  # Will be populated by jd_reasoner node
            requires_frontend_action=False,
            frontend_action={},
            reasoning={}
        )
        
        try:
            # Run the workflow
            final_state = await self.workflow.ainvoke(initial_state)
            
            # Display final results
            self._display_final_results(final_state)
            
            return final_state
            
        except Exception as e:
            print(f"❌ Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            
            initial_state["error"] = str(e)
            return initial_state
    
    def _display_final_results(self, state: RecruitmentState):
        """Display final pipeline results"""
        print("\n" + "="*60)
        print("🎉 PIPELINE COMPLETED")
        print("="*60)
        
        if state.get("error"):
            print(f"❌ Error: {state['error']}")
            return
        
        # Get results
        ranking_results = state.get("ranking_results", {})
        scheduled_interviews = state.get("scheduled_interviews", {}).get("scheduled_interviews", [])
        communication_results = state.get("communication_results", {})
        
        # Show summary
        ranked_candidates = ranking_results.get("ranking_report", {}).get("ranked_candidates", [])
        
        print(f"📊 FINAL RESULTS:")
        print(f"   • Candidates Ranked: {len(ranked_candidates)}")
        print(f"   • Interviews Scheduled: {len(scheduled_interviews)}")
        
        if communication_results:
            emails_sent = communication_results.get("emails_sent", 0)
            print(f"   • Emails Processed: {emails_sent}")
        
        print(f"\n🔚 Final Status: {state.get('current_step', 'unknown')}")
        
        # Check if frontend action is needed
        if state.get("requires_frontend_action"):
            print(f"\n⏸️  ACTION REQUIRED:")
            frontend_action = state.get("frontend_action", {})
            print(f"   • {frontend_action.get('title', 'Action needed')}")
            print(f"   • {frontend_action.get('message', '')}")