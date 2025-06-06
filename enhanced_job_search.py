#!/usr/bin/env python3
"""
Enhanced Drupal Job Search with Email and Slack Notifications
"""

import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from drupal_job_search import DrupalJobSearchCrew
import os
from datetime import datetime

class NotificationManager:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.notification_email = os.getenv('NOTIFICATION_EMAIL')
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
    
    def send_email_notification(self, report_content, job_count):
        """Send email notification with job report"""
        if not all([self.email_user, self.email_password, self.notification_email]):
            print("Email settings not configured, skipping email notification")
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.notification_email
            msg['Subject'] = f"Daily Drupal Jobs Report - {job_count} New Opportunities"
            
            # Create HTML version of the report
            html_content = self.markdown_to_html(report_content)
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.send_message(msg)
            server.quit()
            
            print("Email notification sent successfully")
            
        except Exception as e:
            print(f"Failed to send email: {e}")
    
    def send_slack_notification(self, report_summary, job_count):
        """Send Slack notification"""
        if not self.slack_webhook:
            print("Slack webhook not configured, skipping Slack notification")
            return
        
        try:
            payload = {
                "text": f"🔍 Daily Drupal Jobs Report",
                "attachments": [
                    {
                        "color": "good" if job_count > 0 else "warning",
                        "fields": [
                            {
                                "title": "New Opportunities Found",
                                "value": str(job_count),
                                "short": True
                            },
                            {
                                "title": "Date",
                                "value": datetime.now().strftime("%Y-%m-%d"),
                                "short": True
                            }
                        ],
                        "text": report_summary[:500] + "..." if len(report_summary) > 500 else report_summary
                    }
                ]
            }
            
            response = requests.post(self.slack_webhook, json=payload)
            response.raise_for_status()
            print("Slack notification sent successfully")
            
        except Exception as e:
            print(f"Failed to send Slack notification: {e}")
    
    def markdown_to_html(self, markdown_content):
        """Convert markdown to basic HTML for email"""
        html = markdown_content.replace('\n# ', '\n<h1>').replace('\n## ', '\n<h2>')
        html = html.replace('\n### ', '\n<h3>').replace('\n**', '\n<strong>')
        html = html.replace('**', '</strong>').replace('\n- ', '\n<li>')
        html = html.replace('\n\n', '\n<br><br>\n')
        return f"<html><body>{html}</body></html>"

class EnhancedDrupalJobSearch(DrupalJobSearchCrew):
    def __init__(self):
        super().__init__()
        self.notification_manager = NotificationManager()
    
    def run_daily_search_with_notifications(self):
        """Run daily search and send notifications"""
        try:
            # Run the main search
            report = self.run_daily_search()
            
            # Extract job count from report (basic parsing)
            job_count = self.extract_job_count(str(report))
            
            # Send notifications
            if job_count > 0:
                # Send email
                self.notification_manager.send_email_notification(str(report), job_count)
                
                # Send Slack notification
                summary = self.create_summary(str(report))
                self.notification_manager.send_slack_notification(summary, job_count)
                
                print(f"✅ Found {job_count} new Drupal job opportunities!")
            else:
                print("ℹ️ No new Drupal jobs found today")
            
            return report
            
        except Exception as e:
            # Send error notification
            error_msg = f"❌ Drupal job search failed: {str(e)}"
            if self.notification_manager.slack_webhook:
                requests.post(self.notification_manager.slack_webhook, 
                            json={"text": error_msg})
            raise
    
    def extract_job_count(self, report_content):
        """Extract number of jobs from report content"""
        # Basic extraction - can be enhanced
        lines = report_content.lower().split('\n')
        for line in lines:
            if 'found' in line and 'job' in line:
                words = line.split()
                for i, word in enumerate(words):
                    if word.isdigit():
                        return int(word)
        return 0
    
    def create_summary(self, report_content):
        """Create a brief summary for notifications"""
        lines = report_content.split('\n')
        summary_lines = []
        
        for line in lines[:10]:  # First 10 lines
            if line.strip() and not line.startswith('#'):
                summary_lines.append(line.strip())
                if len(summary_lines) >= 3:
                    break
        
        return '\n'.join(summary_lines)

def main():
    """Main function with enhanced notifications"""
    try:
        enhanced_search = EnhancedDrupalJobSearch()
        report = enhanced_search.run_daily_search_with_notifications()
        
        print("\n" + "="*60)
        print("ENHANCED DRUPAL JOBS SEARCH COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"Enhanced search failed: {e}")

if __name__ == "__main__":
    main()
