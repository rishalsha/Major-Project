import os
import re
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv
from datetime import datetime

import requests

load_dotenv()


class BackgroundVerifierLocalAgent:
    def __init__(self):
        print("✅ Local background verifier configured successfully with GitHub API.")

    def _fetch_github_profile_data(self, github_username: str) -> Optional[Dict]:
        """Fetch GitHub profile data using the public GitHub API."""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "HireIQ/1.0",
        }

        try:
            profile_response = requests.get(
                f"https://api.github.com/users/{github_username}",
                headers=headers,
                timeout=20,
            )
            if not profile_response.ok:
                return None

            profile_data = profile_response.json()

            repos_response = requests.get(
                f"https://api.github.com/users/{github_username}/repos?per_page=100&sort=updated",
                headers=headers,
                timeout=20,
            )

            languages: List[str] = []
            if repos_response.ok:
                repo_items = repos_response.json()
                language_counts: Dict[str, int] = {}

                for repo in repo_items:
                    language = repo.get("language")
                    if language:
                        language_counts[language] = language_counts.get(language, 0) + 1

                languages = [
                    language
                    for language, _ in sorted(
                        language_counts.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )[:5]
                ]

            return {
                "repositories": int(profile_data.get("public_repos", 0)),
                "followers": int(profile_data.get("followers", 0)),
                "languages_used": languages,
            }

        except Exception as e:
            print(f"      ❌ GitHub API lookup failed for {github_username}: {e}")
            return None

    async def verify_candidates(self, screening_output: Dict) -> Dict:
        """Main async method to verify all candidates using public profile data."""
        eligible_candidates = screening_output.get("eligible_candidates", [])
        verified_candidates_output = []

        print(f"\n📋 Processing {len(eligible_candidates)} candidates with the GitHub API verifier...")

        for i, candidate in enumerate(eligible_candidates, 1):
            candidate_name = candidate.get("candidate_info", {}).get("name", "Unknown")

            github_username = self.extract_github_username(candidate)
            github_verified = False
            github_score = 0

            if github_username:
                print(f"   🐙 Checking GitHub API for {github_username}...")
                api_result = self._fetch_github_profile_data(github_username)

                if api_result:
                    repos = int(api_result.get("repositories", 0))
                    followers = int(api_result.get("followers", 0))
                    github_score = self.calculate_github_score(repos, followers)
                    github_verified = True

            linkedin_url = self.extract_linkedin_url(candidate)
            linkedin_verified = bool(linkedin_url)
            linkedin_score = 3 if linkedin_url else 0

            is_verified = github_verified or linkedin_verified
            verification_score = self.calculate_verification_score(
                github_verified,
                github_score,
                linkedin_verified,
                linkedin_score,
            )

            if is_verified:
                verified_candidates_output.append(
                    {
                        "name": candidate_name,
                        "verification_score": verification_score,
                    }
                )

            status = "✅ VERIFIED" if is_verified else "❌ NOT VERIFIED"
            print(f"   [{i}/{len(eligible_candidates)}] {status} - {candidate_name} - Score: {verification_score}/10")

        self._save_verified_candidates(verified_candidates_output)

        return {
            "status": "completed",
            "verified_count": len(verified_candidates_output),
            "verified_candidates": verified_candidates_output,
        }

    def _save_verified_candidates(self, verified_candidates: List[Dict]):
        """Save only verified candidate names and scores to output file"""
        try:
            os.makedirs("output", exist_ok=True)

            output_data = {
                "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_verified_candidates": len(verified_candidates),
                "verified_candidates": verified_candidates,
            }

            output_file = "output/background_verification_report.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            print(f"✅ Verified candidates saved to: {output_file}")
            print("\n📊 VERIFIED CANDIDATES SUMMARY:")
            print(f"   Total Verified: {len(verified_candidates)}")
            for candidate in verified_candidates:
                print(f"   👤 {candidate['name']} - Score: {candidate['verification_score']}/10")

        except Exception as e:
            print(f"❌ Failed to save verified candidates: {e}")

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