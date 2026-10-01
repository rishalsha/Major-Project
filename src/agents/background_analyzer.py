import os
import re
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv
from datetime import datetime

from browser_use import Agent, ChatOpenAI

load_dotenv()

class BackgroundVerifierLocalAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini")
        print("✅ Local Browser Agent configured successfully with the new Agent class.")

    async def _run_browser_task(self, objective: str) -> Optional[Dict]:
        """
        A private async helper method to run a task using the new Agent class.
        """
        try:
            print("      🤖 Creating and running local agent for the task...")
            agent = Agent(task=objective, llm=self.llm)
            result_history = await agent.run()

            # Extract JSON from agent history
            history_str = str(result_history)
            
            # Look for JSON pattern in the history
            json_patterns = [
                r'\{\s*"repositories"\s*:\s*\d+.*?\}',
                r'\{\s*"repositories"\s*:.*?\}',
                r'\{.*"repositories".*?\}',
                r'\{.*\}'
            ]
            
            result_output = None
            for pattern in json_patterns:
                json_match = re.search(pattern, history_str, re.DOTALL)
                if json_match:
                    result_output = json_match.group()
                    break
            
            if not result_output:
                print(f"      ❌ Could not find JSON in agent output")
                return None

            try:
                parsed_json = json.loads(result_output)
                return parsed_json
            except json.JSONDecodeError:
                # Try to clean the JSON string
                try:
                    cleaned_json = re.sub(r'^[^{]*', '', result_output)
                    cleaned_json = re.sub(r'[^}]*$', '', cleaned_json)
                    return json.loads(cleaned_json)
                except json.JSONDecodeError:
                    return None
                    
        except Exception as e:
            print(f"      ❌ An error occurred during the local agent task: {e}")
            return None

    async def verify_candidates(self, screening_output: Dict) -> Dict:
        """
        Main async method to verify all candidates using the local browser agent.
        """
        eligible_candidates = screening_output.get("eligible_candidates", [])
        
        # Store only verified candidate names and scores
        verified_candidates_output = []

        print(f"\n📋 Processing {len(eligible_candidates)} candidates with the Local Browser Agent...")

        for i, candidate in enumerate(eligible_candidates, 1):
            candidate_name = candidate.get("candidate_info", {}).get("name", "Unknown")

            # --- GitHub Verification ---
            github_username = self.extract_github_username(candidate)
            github_verified = False
            github_score = 0
            
            if github_username:
                print(f"   🐙 AI Agent checking GitHub for {github_username}...")

                objective_prompt = (
                    "You are a strict data extraction bot. Your ONLY job is to return a single, valid JSON object. "
                    f"First, go to https://github.com/{github_username}. "
                    "Then, analyze the page to find the number of public repositories and the number of followers. "
                    "Also, find a list of the top programming languages displayed on the profile page. "
                    "Your entire response MUST be ONLY the JSON object. Example format: "
                    "{\"repositories\": 8, \"followers\": \"2.8k\", \"languages_used\": [\"Python\", \"JavaScript\"]}"
                )

                api_result = await self._run_browser_task(objective_prompt)

                if api_result:
                    repos_str = str(api_result.get("repositories", "0"))
                    followers_str = str(api_result.get("followers", "0"))
                    repos, followers = self.clean_numbers(repos_str, followers_str)
                    github_score = self.calculate_github_score(repos, followers)
                    github_verified = True

            # --- LinkedIn Verification ---
            linkedin_url = self.extract_linkedin_url(candidate)
            linkedin_verified = bool(linkedin_url)
            linkedin_score = 3 if linkedin_url else 0

            # --- Overall Verification ---
            is_verified = github_verified or linkedin_verified
            verification_score = self.calculate_verification_score(github_verified, github_score, linkedin_verified, linkedin_score)

            # Only store verified candidates in output
            if is_verified:
                verified_candidates_output.append({
                    "name": candidate_name,
                    "verification_score": verification_score
                })

            status = "✅ VERIFIED" if is_verified else "❌ NOT VERIFIED"
            print(f"   [{i}/{len(eligible_candidates)}] {status} - {candidate_name} - Score: {verification_score}/10")

        # Save only verified candidates with scores
        self._save_verified_candidates(verified_candidates_output)
        
        # Return minimal data for main process
        return {
            "status": "completed", 
            "verified_count": len(verified_candidates_output),
            "verified_candidates": verified_candidates_output  # ADD THIS LINE
            }

    def _save_verified_candidates(self, verified_candidates: List[Dict]):
        """Save only verified candidate names and scores to output file"""
        try:
            os.makedirs("output", exist_ok=True)
            
            output_data = {
                "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_verified_candidates": len(verified_candidates),
                "verified_candidates": verified_candidates
            }
            
            output_file = "output/background_verification_report.json"
            with open(output_file, "w", encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Verified candidates saved to: {output_file}")
            
            # Print summary
            print(f"\n📊 VERIFIED CANDIDATES SUMMARY:")
            print(f"   Total Verified: {len(verified_candidates)}")
            for candidate in verified_candidates:
                print(f"   👤 {candidate['name']} - Score: {candidate['verification_score']}/10")
                
        except Exception as e:
            print(f"❌ Failed to save verified candidates: {e}")

    def clean_numbers(self, repos_str, followers_str):
        repos = 0
        followers = 0
        
        cleaned_repos_str = re.sub(r'[^\d]', '', str(repos_str))
        if cleaned_repos_str.isdigit():
            repos = int(cleaned_repos_str)
        
        followers_str_clean = str(followers_str).lower().strip()
        
        if 'not available' in followers_str_clean or 'n/a' in followers_str_clean or followers_str_clean == 'na':
            followers = 0
        elif 'k' in followers_str_clean:
            numeric_part = re.sub(r'[^\d.]', '', followers_str_clean)
            if numeric_part:
                try: 
                    followers = int(float(numeric_part) * 1000)
                except ValueError: 
                    followers = 0
        else:
            numeric_part = re.sub(r'[^\d]', '', followers_str_clean)
            if numeric_part.isdigit():
                followers = int(numeric_part)
            else:
                followers = 0
        
        return repos, followers

    def calculate_github_score(self, repos, followers):
        score = 0
        
        if repos > 0:
            score += 1
        if repos >= 5:
            score += 1
        if repos >= 10:
            score += 1
        if repos >= 20:
            score += 1
        
        if followers >= 1:
            score += 1
        if followers >= 5:
            score += 1
        if followers >= 10:
            score += 1
        if followers >= 50:
            score += 1
        
        return min(score, 5)

    def calculate_verification_score(self, github_verified: bool, github_score: int, linkedin_verified: bool, linkedin_score: int) -> int:
        base_score = max(github_score, linkedin_score) * 2
        if github_verified and linkedin_verified: 
            base_score = min(base_score + 2, 10)
        return base_score

    def extract_github_username(self, candidate: Dict) -> Optional[str]:
        github_url = candidate.get("profile_links", {}).get("github")
        if github_url:
            match = re.search(r"github\.com/([\w-]+)", github_url, re.IGNORECASE)
            if match: 
                return match.group(1).strip()
        return None

    def extract_linkedin_url(self, candidate: Dict) -> Optional[str]:
        return candidate.get("profile_links", {}).get("linkedin")