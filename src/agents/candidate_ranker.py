import json
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

from src.utils.llm_helper import get_gemini_client, get_gemini_model

load_dotenv()

class CandidateRankingAgent:
    def __init__(self):
        self.client = get_gemini_client()
        self.model = get_gemini_model("gemini-2.0-flash")
        print("✅ Candidate Ranking Agent configured with Gemini semantic analysis.")
    
    def rank_candidates(self, ranking_input: Dict) -> Optional[Dict]:
        """
        Main ranking method that accepts input from orchestration
        DECISION LOGIC:
        1. If background verification was run (has verified_candidates) → Use ONLY verified candidates
        2. If background verification was NOT run → Use ALL screening eligible candidates
        """
        print("\n🎯 Starting SEMANTIC Candidate Ranking...")
        
        # Load job description for semantic analysis
        job_description = self._load_job_description()
        
        # Extract candidates based on workflow decision
        candidates_data = self._extract_candidates_based_on_workflow(ranking_input)
        
        if not candidates_data:
            print("❌ No candidates found for ranking.")
            return self._create_empty_ranking_result()
        
        print(f"📊 Semantically analyzing {len(candidates_data)} candidates...")
        
        # Rank candidates with semantic analysis
        ranked_candidates = []
        for i, candidate in enumerate(candidates_data, 1):
            print(f"   🔍 Analyzing candidate {i}/{len(candidates_data)}: {candidate.get('name', 'Unknown')}")
            
            # Semantic analysis
            semantic_skills_score = self._semantic_skills_match(
                candidate.get("skills", []), 
                job_description
            )
            
            semantic_experience_score = self._semantic_experience_match(
                candidate.get("experience_years", 0),
                job_description
            )
            
            # Get base scores
            verification_score = candidate.get("verification_score", 0)
            resume_score = candidate.get("score", 5.0)
            
            # Calculate comprehensive semantic score
            comprehensive_score = self._calculate_semantic_score(
                verification_score=verification_score,
                resume_score=resume_score,
                semantic_skills_score=semantic_skills_score,
                semantic_experience_score=semantic_experience_score
            )
            
            # Create ranked candidate
            ranked_candidate = {
                "name": candidate.get("name", f"Candidate {i}"),
                "candidate_name": candidate.get("name", f"Candidate {i}"),
                "comprehensive_score": comprehensive_score,
                "semantic_scores": {
                    "verification": verification_score,
                    "resume": resume_score,
                    "skills_semantic": semantic_skills_score,
                    "experience_semantic": semantic_experience_score
                },
                "skills": candidate.get("skills", []),
                "experience_years": candidate.get("experience_years", 0),
                "email": candidate.get("email", ""),
                "verification_score": verification_score,
                "source": candidate.get("source", "unknown"),
                "semantic_analysis": True
            }
            ranked_candidates.append(ranked_candidate)
        
        # Sort by comprehensive score
        ranked_candidates.sort(key=lambda x: x["comprehensive_score"], reverse=True)
        
        # Add ranks
        for i, candidate in enumerate(ranked_candidates, 1):
            candidate["rank"] = i
        
        # Prepare result
        ranking_result = self._prepare_semantic_ranking_result(ranked_candidates)
        
        # Save
        self._save_ranking_results(ranking_result)
        
        return ranking_result
    
    def _extract_candidates_based_on_workflow(self, ranking_input: Dict) -> List[Dict]:
        """
        CRITICAL DECISION: Choose which candidates to rank
        1. If background verification results exist → Use ONLY verified candidates
        2. If NO background results → Use ALL eligible screening candidates
        """
        candidates = []
        
        # Check what data is available
        has_verified_candidates = "verified_candidates" in ranking_input and ranking_input["verified_candidates"]
        has_screening_results = "screening_results" in ranking_input and ranking_input["screening_results"]
        
        print(f"   🔍 Input Analysis:")
        print(f"      • Has verified_candidates: {has_verified_candidates}")
        print(f"      • Has screening_results: {has_screening_results}")
        
        # SCENARIO 1: BACKGROUND VERIFICATION WAS PERFORMED (Technical role)
        if has_verified_candidates:
            print("   📋 WORKFLOW: Background verification performed → Using ONLY verified candidates")
            verified_candidates = ranking_input["verified_candidates"]
            
            for candidate in verified_candidates:
                candidate_name = candidate.get("name", "Unknown")
                verification_score = candidate.get("verification_score", 0)
                
                # Try to enrich with screening data
                screening_data = self._get_screening_data_for_candidate(candidate_name, ranking_input)
                
                candidate_data = {
                    "name": candidate_name,
                    "verification_score": verification_score,
                    "source": "background_verification"
                }
                
                if screening_data:
                    # Enrich with screening data
                    candidate_data.update(screening_data)
                    candidate_data["source"] = "background_and_screening"
                else:
                    # Only background data available
                    candidate_data["score"] = 5.0  # Default score
                    candidate_data["skills"] = []
                    candidate_data["experience_years"] = 0
                    candidate_data["email"] = ""
                
                candidates.append(candidate_data)
            
            print(f"      ✅ Using {len(candidates)} verified candidates from background check")
        
        # SCENARIO 2: NO BACKGROUND VERIFICATION (Non-technical role or background skipped)
        elif has_screening_results:
            print("   📋 WORKFLOW: No background verification → Using ALL eligible screening candidates")
            screening_results = ranking_input["screening_results"]
            eligible_candidates = screening_results.get("eligible_candidates", [])
            
            for candidate in eligible_candidates:
                candidate_info = candidate.get("candidate_info", {})
                candidate_data = {
                    "name": candidate_info.get("name", "Unknown"),
                    "email": candidate_info.get("email", ""),
                    "score": candidate.get("overall_score", 5.0),
                    "skills": candidate.get("skills_summary", {}).get("skills", []),
                    "experience_years": candidate_info.get("total_experience", "0"),
                    "verification_score": 0,  # No verification for non-technical roles
                    "source": "screening_only"
                }
                candidates.append(candidate_data)
            
            print(f"      ✅ Using {len(candidates)} eligible candidates from screening")
        
        # SCENARIO 3: Fallback - read from files if no input provided
        else:
            print("   ⚠️  No direct input, reading from files...")
            candidates = self._extract_candidates_from_files()
        
        return candidates
    
    def _get_screening_data_for_candidate(self, candidate_name: str, ranking_input: Dict) -> Optional[Dict]:
        """Find screening data for a verified candidate (enrichment)"""
        if "screening_results" not in ranking_input:
            return None
        
        screening_results = ranking_input["screening_results"]
        eligible_candidates = screening_results.get("eligible_candidates", [])
        
        # Try to match by name (case-insensitive)
        candidate_name_upper = candidate_name.upper()
        
        for candidate in eligible_candidates:
            candidate_info = candidate.get("candidate_info", {})
            screening_name = candidate_info.get("name", "")
            
            if screening_name.upper() == candidate_name_upper:
                return {
                    "email": candidate_info.get("email", ""),
                    "score": candidate.get("overall_score", 5.0),
                    "skills": candidate.get("skills_summary", {}).get("skills", []),
                    "experience_years": candidate_info.get("total_experience", "0")
                }
        
        return None
    
    def _extract_candidates_from_files(self) -> List[Dict]:
        """Fallback: extract candidates from saved files"""
        candidates = []
        
        # Priority 1: Check background verification file
        background_file = "output/background_verification_report.json"
        if os.path.exists(background_file):
            try:
                with open(background_file, "r", encoding='utf-8') as f:
                    background_data = json.load(f)
                
                verified_candidates = background_data.get("verified_candidates", [])
                if verified_candidates:
                    print("   📋 Found verified candidates in file")
                    for candidate in verified_candidates:
                        candidates.append({
                            "name": candidate.get("name", "Unknown"),
                            "verification_score": candidate.get("verification_score", 0),
                            "score": 5.0,
                            "skills": [],
                            "experience_years": 0,
                            "source": "background_file"
                        })
                    return candidates
            except Exception as e:
                print(f"⚠️ Could not read background file: {e}")
        
        # Priority 2: Check screening file
        screening_file = "output/screening_results.json"
        if os.path.exists(screening_file):
            try:
                with open(screening_file, "r", encoding='utf-8') as f:
                    screening_data = json.load(f)
                
                eligible_candidates = screening_data.get("eligible_candidates", [])
                print(f"   📋 Found {len(eligible_candidates)} candidates in screening file")
                for candidate in eligible_candidates:
                    candidate_info = candidate.get("candidate_info", {})
                    candidates.append({
                        "name": candidate_info.get("name", "Unknown"),
                        "email": candidate_info.get("email", ""),
                        "score": candidate.get("overall_score", 5.0),
                        "skills": candidate.get("skills_summary", {}).get("skills", []),
                        "experience_years": candidate_info.get("total_experience", "0"),
                        "verification_score": 0,
                        "source": "screening_file"
                    })
            except Exception as e:
                print(f"⚠️ Could not read screening file: {e}")
        
        return candidates
    
    def _semantic_skills_match(self, candidate_skills: List[str], job_description: str) -> float:
        """
        Use LLM for semantic skills matching instead of hardcoded keywords
        Returns score 0-10
        """
        if not candidate_skills or not job_description:
            return 5.0  # Default score
        
        try:
            # Prepare skills as text
            skills_text = ", ".join([str(skill) for skill in candidate_skills])
            
            prompt = f"""
            Analyze how well the candidate's skills semantically match the job requirements.
            
            CANDIDATE SKILLS: {skills_text}
            
            JOB DESCRIPTION: {job_description[:1000]}
            
            Semantic Analysis Task:
            1. Understand the meaning and context of each skill
            2. Understand the job requirements semantically
            3. Score semantic match from 0-10 where:
               - 10: Perfect semantic alignment with job requirements
               - 7-9: Strong semantic alignment
               - 4-6: Moderate semantic alignment
               - 0-3: Weak semantic alignment
            
            Return ONLY a JSON object with:
            {{
                "semantic_score": [number between 0-10],
                "reasoning": "[brief semantic analysis in 1-2 sentences]"
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a semantic skills analyzer. Understand meaning, not just keywords."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            
            # Try to parse JSON
            try:
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                    score = analysis.get("semantic_score", 5.0)
                    # Ensure score is within 0-10 range
                    return max(0, min(float(score), 10.0))
            except:
                pass
            
            return 5.0
            
        except Exception as e:
            print(f"⚠️ Semantic skills analysis failed: {e}")
            return 5.0
    
    def _semantic_experience_match(self, experience_years, job_description: str) -> float:
        """
        Use LLM to semantically evaluate experience relevance
        """
        try:
            import re
            numbers = re.findall(r'\d+', str(experience_years))
            exp_num = float(numbers[0]) if numbers else 0.0
        except:
            exp_num = 0.0

        if not job_description:
            # Fallback: linear scaling
            return min(exp_num * 0.8, 10.0)
        
        try:
            prompt = f"""
            Analyze how semantically relevant the candidate's experience is to the job.
            
            CANDIDATE EXPERIENCE: {experience_years}
            
            JOB DESCRIPTION: {job_description[:800]}
            
            Semantic Evaluation:
            - Consider the type of experience needed for this role
            - Years alone don't matter - relevance matters more
            - Score 0-10 based on semantic relevance
            
            Return ONLY a JSON object:
            {{
                "experience_score": [0-10],
                "reasoning": "[brief semantic reasoning]"
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Semantically evaluate experience relevance."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            result = response.choices[0].message.content.strip()
            
            try:
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                    score = analysis.get("experience_score", 5.0)
                    return max(0, min(float(score), 10.0))
            except:
                pass
            
            # Fallback: linear scaling
            return min(exp_num * 0.8, 10.0)
                
        except Exception as e:
            print(f"⚠️ Semantic experience analysis failed: {e}")
            return min(exp_num * 0.8, 10.0)
    
    def _calculate_semantic_score(self, **scores) -> float:
        """
        Calculate comprehensive semantic score
        Dynamically weights based on available data
        """
        verification_score = scores.get("verification_score", 0)
        resume_score = scores.get("resume_score", 0)
        semantic_skills_score = scores.get("semantic_skills_score", 5.0)
        semantic_experience_score = scores.get("semantic_experience_score", 5.0)
        
        # Determine which scores are available
        available_scores = []
        weights = []
        
        if verification_score > 0:
            available_scores.append(verification_score)
            weights.append(0.3)  # 30% for verification
        
        if resume_score > 0:
            available_scores.append(resume_score)
            weights.append(0.3)  # 30% for resume
        
        # Always include semantic scores
        available_scores.append(semantic_skills_score)
        weights.append(0.25)  # 25% for semantic skills
        
        available_scores.append(semantic_experience_score)
        weights.append(0.15)  # 15% for semantic experience
        
        # Normalize weights to sum to 1
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w/total_weight for w in weights]
        
        # Calculate weighted average
        weighted_sum = sum(score * weight for score, weight in zip(available_scores, weights))
        
        return round(weighted_sum, 2)
    
    def _load_job_description(self) -> str:
        """Load job description from file"""
        try:
            if os.path.exists("job_description.txt"):
                with open("job_description.txt", "r", encoding='utf-8') as f:
                    return f.read()
            return ""
        except:
            return ""
    
    def _prepare_semantic_ranking_result(self, ranked_candidates: List[Dict]) -> Dict:
        """Prepare semantic ranking result"""
        return {
            "ranking_report": {
                "total_candidates_ranked": len(ranked_candidates),
                "ranking_method": "semantic_analysis",
                "workflow_note": "Ranked verified candidates only when background check performed",
                "semantic_factors": {
                    "verification_score": "Social proof verification",
                    "resume_score": "Resume quality assessment",
                    "skills_semantic_match": "LLM-based semantic skills alignment",
                    "experience_semantic_match": "LLM-based experience relevance"
                },
                "ranked_candidates": ranked_candidates
            },
            "candidates": ranked_candidates
        }
    
    def _create_empty_ranking_result(self) -> Dict:
        return {
            "ranking_report": {
                "total_candidates_ranked": 0,
                "ranked_candidates": [],
                "ranking_method": "semantic_analysis"
            },
            "candidates": []
        }
    
    def _save_ranking_results(self, ranking_result: Dict):
        """Save semantic ranking results"""
        try:
            os.makedirs("output", exist_ok=True)
            
            output_file = "output/candidate_ranking_report.json"
            with open(output_file, "w", encoding='utf-8') as f:
                json.dump(ranking_result, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Semantic ranking saved to: {output_file}")
            
            # Show semantic ranking results
            ranked_candidates = ranking_result.get("ranking_report", {}).get("ranked_candidates", [])
            if ranked_candidates:
                print(f"\n🏆 SEMANTIC RANKING RESULTS:")
                print(f"   (Using LLM-based semantic analysis)")
                
                # Show workflow decision
                source = ranked_candidates[0].get("source", "")
                if "background" in source.lower():
                    print(f"   📋 Background verification performed → Ranked {len(ranked_candidates)} verified candidates")
                else:
                    print(f"   📋 No background verification → Ranked {len(ranked_candidates)} screening candidates")
                
                for candidate in ranked_candidates[:5]:
                    name = candidate.get('name', candidate.get('candidate_name', 'Unknown'))
                    score = candidate['comprehensive_score']
                    verification = candidate.get('verification_score', 0)
                    
                    print(f"   #{candidate['rank']}: {name}")
                    print(f"      Overall: {score}/10")
                    if verification > 0:
                        print(f"      Verification: {verification}/10")
                    print()
            else:
                print("⚠️ No candidates ranked")
                
        except Exception as e:
            print(f"❌ Failed to save ranking results: {e}")