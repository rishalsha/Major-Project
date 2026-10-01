import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
import os
import asyncio

class CommunicationAgent:
    """Agent for sending REAL interview confirmation emails"""
    
    def __init__(self, smtp_config: Optional[Dict] = None):
        # Load SMTP configuration
        self.smtp_config = smtp_config or self._load_smtp_config()
        
        # Email configuration
        self.sender_email = self.smtp_config.get("sender_email", "noreply@recruitmentsystem.com")
        self.sender_name = self.smtp_config.get("sender_name", "AI Recruitment System")
        self.smtp_server = self.smtp_config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = self.smtp_config.get("smtp_port", 587)
        self.use_tls = self.smtp_config.get("use_tls", True)
        
        # Load email templates
        self.templates = self._load_email_templates()
        
        print("✅ Communication Agent - REAL EMAIL SYSTEM")
        print(f"   📧 Sender: {self.sender_name} <{self.sender_email}>")
        print(f"   📮 SMTP: {self.smtp_server}:{self.smtp_port}")
    
    def _load_smtp_config(self) -> Dict:
        """Load SMTP configuration from file"""
        config_path = "config/smtp_config.json"
        default_config = {
            "sender_email": "noreply@yourcompany.com",
            "sender_name": "Recruitment System",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "use_tls": True,
            "test_mode": False  # Set to True for testing (won't send real emails)
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                print(f"   📋 Loaded SMTP config from {config_path}")
                return {**default_config, **config}
            else:
                print(f"   ⚠️ SMTP config not found, using defaults")
                return default_config
        except Exception as e:
            print(f"   ❌ Error loading SMTP config: {e}")
            return default_config
    
    def _load_email_templates(self) -> Dict:
        """Load email templates"""
        try:
            with open("config/email_templates.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print("⚠️ Email templates not found, using defaults")
            return self._get_default_templates()
    
    def _get_default_templates(self) -> Dict:
        """Default email templates"""
        return {
            "in_person": {
                "subject": "Interview Confirmed: {job_title} at {company_name}",
                "body": "Dear {candidate_name},\n\nYour interview has been scheduled.\n\n**Interview Details:**\n- Position: {job_title}\n- Date: {interview_date}\n- Time: {interview_time}\n- Duration: {duration_minutes} minutes\n- Location: {location}\n- Interview Panel: {panel_members}\n\n**Location:**\n{location_details}\n\n**Please Bring:**\n1. Resume copy\n2. ID proof\n3. Relevant documents\n\n**Reschedule:** Contact us 24 hours before.\n\nBest regards,\n{company_name} Hiring Team\n\n---\nAutomated message - Do not reply"
            },
            "online": {
                "subject": "Interview Confirmed: {job_title} at {company_name}",
                "body": "Dear {candidate_name},\n\nYour online interview has been scheduled.\n\n**Interview Details:**\n- Position: {job_title}\n- Date: {interview_date}\n- Time: {interview_time}\n- Duration: {duration_minutes} minutes\n- Join Link: {meeting_link}\n- Interview Panel: {panel_members}\n\n**To Join:**\n1. Click link at scheduled time: {meeting_link}\n2. Test audio/video beforehand\n3. Join 5 minutes early\n\n**Preparation:**\n1. Review job description\n2. Have resume ready\n3. Stable internet connection\n\n**Reschedule:** Contact us 24 hours before.\n\nBest regards,\n{company_name} Hiring Team\n\n---\nAutomated message - Do not reply"
            }
        }
    
    async def send_interview_confirmation(self,
                                         scheduled_interviews: List[Dict],
                                         interview_mode: str = "online",
                                         location: str = None,
                                         company_name: str = "Our Company",
                                         panel_members: str = "Interview Panel",
                                         job_title: str = "Position") -> Dict:
        """
        Send REAL interview confirmation emails
        
        Args:
            scheduled_interviews: From CalendarSchedulingAgent
            interview_mode: "online" or "in_person"
            location: Physical address (for in-person)
            company_name: Company name
            panel_members: Interview panel info
            job_title: Job position title
        """
        print(f"\n📧 SENDING REAL CONFIRMATION EMAILS")
        print(f"   Mode: {interview_mode}")
        print(f"   Company: {company_name}")
        
        if interview_mode == "in_person" and location:
            print(f"   Location: {location}")
        
        # Get correct template
        template_key = "online" if interview_mode == "online" else "in_person"
        template = self.templates.get(template_key)
        
        if not template:
            return {"error": f"Template {template_key} not found"}
        
        # Results tracking
        results = {
            "status": "started",
            "template_used": template_key,
            "total_candidates": len(scheduled_interviews),
            "emails_sent": 0,
            "failed_emails": [],
            "sent_emails": []
        }
        
        # Check test mode
        test_mode = self.smtp_config.get("test_mode", False)
        if test_mode:
            print("   ⚠️ TEST MODE: Emails logged but not sent")
        else:
            print("   🚀 REAL MODE: Sending actual emails")
        
        # Send emails
        for interview in scheduled_interviews:
            candidate_email = interview.get("candidate_email", "").strip()
            candidate_name = interview.get("candidate_name", "Candidate")
            
            if not candidate_email:
                print(f"   ❌ No email for {candidate_name}")
                results["failed_emails"].append({
                    "candidate": candidate_name,
                    "reason": "No email address"
                })
                continue
            
            try:
                # Prepare email content
                email_content = self._prepare_email_content(
                    template=template,
                    interview=interview,
                    interview_mode=interview_mode,
                    location=location,
                    company_name=company_name,
                    panel_members=panel_members,
                    job_title=job_title
                )
                
                # Send or simulate email
                if test_mode:
                    # Test mode - log only
                    print(f"   📨 [TEST] Would send to: {candidate_name} <{candidate_email}>")
                    print(f"   📝 Subject: {email_content['subject']}")
                    email_status = "test_mode"
                else:
                    # REAL email sending
                    email_status = await self._send_real_email(
                        to_email=candidate_email,
                        subject=email_content['subject'],
                        body=email_content['body']
                    )
                
                # Track results
                if email_status in ["sent", "test_mode"]:
                    results["emails_sent"] += 1
                    results["sent_emails"].append({
                        "candidate": candidate_name,
                        "email": candidate_email,
                        "subject": email_content['subject'],
                        "status": email_status
                    })
                    status_icon = "📝" if email_status == "test_mode" else "✅"
                    print(f"   {status_icon} {candidate_name}")
                else:
                    results["failed_emails"].append({
                        "candidate": candidate_name,
                        "reason": email_status
                    })
                    print(f"   ❌ {candidate_name}: {email_status}")
                    
            except Exception as e:
                error_msg = str(e)
                results["failed_emails"].append({
                    "candidate": candidate_name,
                    "reason": f"Exception: {error_msg}"
                })
                print(f"   ❌ Error for {candidate_name}: {error_msg}")
        
        # Final status
        if results["failed_emails"] and results["emails_sent"]:
            results["status"] = "partial_success"
        elif results["emails_sent"] == results["total_candidates"]:
            results["status"] = "success"
        else:
            results["status"] = "failed"
        
        print(f"   📊 Results: {results['emails_sent']} sent, {len(results['failed_emails'])} failed")
        return results
    
    def _prepare_email_content(self, 
                              template: Dict, 
                              interview: Dict,
                              interview_mode: str,
                              location: str = None,
                              company_name: str = "Our Company",
                              panel_members: str = "Interview Panel",
                              job_title: str = "Position") -> Dict:
        """Prepare email subject and body"""
        
        # Get Google Meet link
        meeting_link = interview.get("meeting_link", "")
        
        # Prepare location details
        location_details = location or "Details will be shared separately"
        if interview_mode == "online" and not meeting_link:
            meeting_link = "Link will be provided separately"
        
        # Format subject
        subject = template["subject"].format(
            job_title=job_title,
            company_name=company_name
        )
        
        # Format body
        body = template["body"].format(
            candidate_name=interview.get("candidate_name", "Candidate"),
            job_title=job_title,
            interview_date=interview.get("interview_date", "Date"),
            interview_time=interview.get("interview_time", "Time"),
            duration_minutes=interview.get("duration_minutes", 60),
            location=location or "To be determined",
            location_details=location_details,
            meeting_link=meeting_link,
            panel_members=panel_members,
            company_name=company_name
        )
        
        return {
            "subject": subject,
            "body": body,
            "to_email": interview.get("candidate_email"),
            "candidate_name": interview.get("candidate_name")
        }
    
    async def _send_real_email(self, to_email: str, subject: str, body: str) -> str:
        """Send REAL email using SMTP"""
        try:
            # Create message

            await asyncio.sleep(1)
            
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Reply-To'] = "noreply@example.com"  # No replies
            
            # Create plain text version
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)
            
            # Check SMTP credentials
            smtp_username = self.smtp_config.get("smtp_username")
            smtp_password = self.smtp_config.get("smtp_password")
            
            if not smtp_username or not smtp_password:
                return "SMTP credentials not configured"
            
            # Connect and send
            context = ssl.create_default_context()
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                if self.use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                
                # Login with credentials
                server.login(smtp_username, smtp_password)
                
                # Send email
                server.send_message(msg)
            
            return "sent"
            
        except smtplib.SMTPAuthenticationError:
            return "SMTP authentication failed - check username/password"
        except smtplib.SMTPException as e:
            return f"SMTP error: {str(e)}"
        except Exception as e:
            return f"Email error: {str(e)}"
    
    async def send_test_email(self, to_email: str = "test@example.com") -> Dict:
        """Send test email to verify SMTP setup"""
        print("\n🧪 SENDING TEST EMAIL")
        
        test_interview = {
            "candidate_name": "Test Candidate",
            "candidate_email": to_email,
            "interview_date": "2024-12-31",
            "interview_time": "02:00 PM",
            "duration_minutes": 60,
            "meeting_link": "https://meet.google.com/test-room"
        }
        
        return await self.send_interview_confirmation(
            scheduled_interviews=[test_interview],
            interview_mode="online",
            company_name="Test Company",
            panel_members="Test Interviewer",
            job_title="Test Position"
        )

# Test function
async def main():
    """Test the CommunicationAgent"""
    agent = CommunicationAgent()
    
    # Test with sample data
    test_interviews = [
        {
            "candidate_name": "John Doe",
            "candidate_email": "test@example.com",
            "interview_date": "2024-12-15",
            "interview_time": "10:00 AM",
            "duration_minutes": 60,
            "meeting_link": "https://meet.google.com/abc-defg-hij"
        }
    ]
    
    print("Testing online interview emails...")
    result = await agent.send_interview_confirmation(
        scheduled_interviews=test_interviews,
        interview_mode="online",
        company_name="TechCorp Inc.",
        panel_members="Technical Lead & HR Manager",
        job_title="Senior Developer"
    )
    
    print(f"\nTest result: {result['status']}")
    print(f"Emails sent: {result['emails_sent']}")

if __name__ == "__main__":
    asyncio.run(main())