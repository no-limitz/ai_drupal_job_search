#!/usr/bin/env python3
"""
Main orchestrator for the enhanced Drupal job search system
Integrates all components: search, database, notifications, and configuration
"""

import time
import argparse
import re
import json
import requests
import logging
from datetime import datetime
from urllib.parse import urlparse
from drupal_job_search import DrupalJobSearchCrew
from database_manager import JobDatabase
from config_manager import JobSearchConfiguration
from enhanced_job_search import NotificationManager
from dotenv import load_dotenv

load_dotenv()

class DrupalJobSearchOrchestrator:
    def __init__(self, config_file='config.json'):
        self.config = JobSearchConfiguration(config_file)
        self.database = JobDatabase()
        self.notification_manager = NotificationManager()
        self.search_crew = DrupalJobSearchCrew()
        
    def run_comprehensive_search(self, send_notifications=True):
        """Run a comprehensive job search with all features"""
        start_time = time.time()
        
        print("🚀 Starting comprehensive Drupal job search...")
        print(f"📅 Search date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Get current statistics
            before_stats = self.database.get_statistics()
            print(f"📊 Jobs in database before search: {before_stats['total_jobs']}")
            
            # Run the CrewAI search
            print("🔍 Running CrewAI job search...")
            search_result = self.search_crew.run_daily_search()
            
            # Parse and store results
            new_jobs_count = self.process_search_results(search_result)
            
            # Get updated statistics
            after_stats = self.database.get_statistics()
            execution_time = time.time() - start_time
            
            # Log search execution
            queries = self.config.get_search_queries()
            self.database.log_search(
                total_found=after_stats['total_jobs'],
                new_found=new_jobs_count,
                queries=queries[:10],  # Log first 10 queries
                execution_time=execution_time
            )
            
            # Generate comprehensive report
            report = self.generate_comprehensive_report(new_jobs_count, after_stats, execution_time)
            
            # Send notifications if enabled
            if send_notifications and new_jobs_count > 0:
                self.send_notifications(report, new_jobs_count)
            
            # Cleanup old jobs
            deleted_count = self.database.cleanup_old_jobs(days_to_keep=90)
            if deleted_count > 0:
                print(f"🧹 Cleaned up {deleted_count} old job listings")
            
            print(f"✅ Search completed successfully in {execution_time:.1f} seconds")
            print(f"🆕 Found {new_jobs_count} new job opportunities")
            
            return report
            
        except Exception as e:
            print(f"❌ Search failed: {e}")
            # Send error notification
            if send_notifications:
                error_msg = f"Drupal job search failed: {str(e)}"
                self.notification_manager.send_slack_notification(error_msg, 0)
            raise
    
    def process_search_results(self, search_result):
        """Process CrewAI search results and store in database"""
        print("📝 Processing search results...")
        
        new_jobs_count = 0
        
        try:
            # Parse the CrewAI search result string to extract real job data
            parsed_jobs = self._parse_crew_ai_output(search_result)
            
            for job_data in parsed_jobs:
                # Validate job data before storing
                if self._validate_job_data(job_data):
                    # Add to database only if it's a new job
                    is_new = self.database.add_job(job_data)
                    if is_new:
                        new_jobs_count += 1
                        print(f"✅ Added new job: {job_data['title']} at {job_data['company']}")
                    else:
                        print(f"📄 Duplicate job skipped: {job_data['title']}")
                else:
                    print(f"❌ Invalid job data skipped: {job_data.get('title', 'Unknown')}")
                    
        except Exception as e:
            print(f"⚠️ Error processing search results: {e}")
            logging.error(f"Search result processing error: {e}")
        
        return new_jobs_count
    
    def generate_comprehensive_report(self, new_jobs_count, stats, execution_time):
        """Generate a comprehensive report"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        report = f"""# Comprehensive Drupal Jobs Report - {today}

## Executive Summary
- 🎯 **New opportunities found:** {new_jobs_count}
- 📊 **Total jobs in database:** {stats['total_jobs']}
- 📈 **Jobs this week:** {stats['this_week']}
- 📝 **Applications submitted:** {stats['applications']}
- ⭐ **Average relevance score:** {stats['avg_relevance']}
- ⏱️ **Search execution time:** {execution_time:.1f} seconds

## Today's New Opportunities

"""
        
        # Get today's new jobs
        new_jobs = self.database.get_new_jobs_today()
        
        if new_jobs:
            high_priority = [job for job in new_jobs if job['relevance_score'] >= 8]
            medium_priority = [job for job in new_jobs if 6 <= job['relevance_score'] < 8]
            
            if high_priority:
                report += "### 🔥 High Priority Jobs (Score 8-10)\n\n"
                for job in high_priority:
                    report += f"""**{job['title']}** - {job['company']}
- 📍 Location: {job['location']}
- 💰 Rate: {job['salary_range']}
- ⭐ Score: {job['relevance_score']}/10
- 🔗 [Apply Here]({job['url']})

"""
            
            if medium_priority:
                report += "### 📋 Medium Priority Jobs (Score 6-7)\n\n"
                for job in medium_priority:
                    report += f"""**{job['title']}** - {job['company']}
- 📍 Location: {job['location']}
- 💰 Rate: {job['salary_range']}
- ⭐ Score: {job['relevance_score']}/10
- 🔗 [Apply Here]({job['url']})

"""
        else:
            report += "No new opportunities found today. Keep your skills sharp! 💪\n\n"
        
        # Add market insights
        report += "## 📈 Market Insights\n\n"
        if stats['top_companies']:
            report += "### Top Hiring Companies:\n"
            for company, count in list(stats['top_companies'].items())[:5]:
                report += f"- **{company}**: {count} positions\n"
            report += "\n"
        
        # Add application tips
        report += """## 💡 Application Tips

1. **Tailor your proposal** to mention specific Drupal versions and modules
2. **Highlight relevant experience** with similar projects
3. **Include portfolio links** showcasing Drupal work
4. **Respond quickly** to high-priority opportunities
5. **Follow up professionally** within 3-5 business days

## 🎯 Next Steps

- Review high-priority opportunities first
- Update your portfolio with recent Drupal projects
- Consider skill development in trending technologies
- Track your application success rate

---
*Report generated by AI Drupal Job Search System*
"""
        
        return report
    
    def _parse_crew_ai_output(self, search_result):
        """Parse CrewAI output to extract structured job data"""
        jobs = []
        
        if not search_result or not isinstance(search_result, str):
            print("⚠️ No valid search results to parse")
            return jobs
        
        try:
            # CrewAI returns text output, we need to extract job information
            # Look for job patterns in the text
            job_patterns = [
                # Pattern for job titles and companies
                r'(?i)(?:job|position|role)\s*:?\s*([^\n]+?)\s*(?:at|@|\-|company)\s*([^\n]+?)(?:\n|$|location)',
                # Pattern for URLs
                r'https?://[^\s]+',
                # Pattern for salary information
                r'\$[\d,]+-?[\d,]*(?:/hour|/hr|per hour|annually)?',
                # Pattern for location
                r'(?i)(?:location|remote|onsite)\s*:?\s*([^\n]+?)(?:\n|$)',
            ]
            
            # Extract URLs first
            urls = re.findall(r'https?://[^\s\)\]]+', search_result)
            valid_urls = [url for url in urls if self._validate_job_url(url)]
            
            # If we found valid URLs, try to extract job information around them
            if valid_urls:
                lines = search_result.split('\n')
                current_job = {}
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Check if line contains a URL
                    url_in_line = None
                    for url in valid_urls:
                        if url in line:
                            url_in_line = url
                            break
                    
                    if url_in_line:
                        # Extract job details from surrounding lines
                        job_data = self._extract_job_details(lines, i, url_in_line)
                        if job_data:
                            jobs.append(job_data)
            
            # If no jobs found through URL extraction, try general text parsing
            if not jobs:
                jobs = self._parse_general_job_text(search_result)
                
        except Exception as e:
            print(f"⚠️ Error parsing CrewAI output: {e}")
            logging.error(f"CrewAI parsing error: {e}")
        
        return jobs
    
    def _extract_job_details(self, lines, url_line_index, url):
        """Extract job details from lines around a URL"""
        try:
            # Look at lines before and after the URL for job details
            start_idx = max(0, url_line_index - 3)
            end_idx = min(len(lines), url_line_index + 3)
            context_lines = lines[start_idx:end_idx]
            context_text = ' '.join(context_lines)
            
            # Extract title (usually appears before URL)
            title_patterns = [
                r'(?i)(?:title|position|job|role)\s*:?\s*([^\n]+?)(?=\s*(?:at|@|company|location|\$))',
                r'([A-Za-z\s]+(?:Developer|Engineer|Architect|Manager)[^\n]*?)(?=\s*(?:at|@|\-|company))',
            ]
            
            title = None
            for pattern in title_patterns:
                match = re.search(pattern, context_text)
                if match:
                    title = match.group(1).strip()
                    break
            
            # Extract company
            company_patterns = [
                r'(?i)(?:at|@|company)\s*:?\s*([A-Za-z\s&.,]+?)(?=\s*(?:location|remote|\$|http))',
                r'(?i)company\s*:?\s*([^\n]+?)(?:\n|$)',
            ]
            
            company = None
            for pattern in company_patterns:
                match = re.search(pattern, context_text)
                if match:
                    company = match.group(1).strip()
                    break
            
            # Extract location
            location_match = re.search(r'(?i)(?:location|remote)\s*:?\s*([^\n$]+?)(?=\s*(?:\$|http|\n|$))', context_text)
            location = location_match.group(1).strip() if location_match else 'Not specified'
            
            # Extract salary
            salary_match = re.search(r'\$[\d,]+-?[\d,]*(?:/hour|/hr|per hour|annually)?', context_text)
            salary = salary_match.group(0) if salary_match else 'Not specified'
            
            # If we have at least title or company, create a job entry
            if title or company:
                return {
                    'title': title or 'Drupal Developer Position',
                    'company': company or 'Company Name Not Found',
                    'location': location,
                    'url': url,
                    'description': context_text[:500],  # First 500 chars as description
                    'salary_range': salary,
                    'posted_date': datetime.now().strftime('%Y-%m-%d'),
                    'source': urlparse(url).netloc if url else 'Unknown',
                    'relevance_score': self._calculate_relevance_score(title, company, context_text)
                }
        except Exception as e:
            print(f"⚠️ Error extracting job details: {e}")
        
        return None
    
    def _parse_general_job_text(self, text):
        """Parse general text for job information when URL extraction fails"""
        jobs = []
        
        # This is a fallback - return empty list since we only want real jobs
        # In production, this could attempt to parse unstructured text for job info
        print("📝 No valid job URLs found in search results")
        
        return jobs
    
    def _validate_job_data(self, job_data):
        """Validate job data before storing in database"""
        required_fields = ['title', 'company', 'url']
        
        # Check required fields
        for field in required_fields:
            if not job_data.get(field) or job_data[field].strip() == '':
                return False
        
        # Validate URL format and accessibility
        if not self._validate_job_url(job_data['url']):
            return False
        
        # Check for Drupal relevance
        text_to_check = f"{job_data.get('title', '')} {job_data.get('description', '')}".lower()
        drupal_keywords = ['drupal', 'cms', 'php', 'symfony', 'twig']
        
        if not any(keyword in text_to_check for keyword in drupal_keywords):
            print(f"⚠️ Job not Drupal-related: {job_data['title']}")
            return False
        
        return True
    
    def _validate_job_url(self, url):
        """Validate that a job URL is accessible and real"""
        if not url or 'example.com' in url or url.startswith('#'):
            return False
        
        try:
            # Parse URL to ensure it's valid
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Make a HEAD request to check if URL is accessible
            response = requests.head(url, timeout=10, allow_redirects=True)
            return response.status_code < 400
            
        except Exception as e:
            print(f"⚠️ URL validation failed for {url}: {e}")
            return False
    
    def _calculate_relevance_score(self, title, company, description):
        """Calculate relevance score for a job based on various factors"""
        score = 5.0  # Base score
        
        text = f"{title} {company} {description}".lower()
        
        # Drupal-specific keywords
        high_value_keywords = ['senior', 'lead', 'architect', 'drupal 10', 'drupal 9']
        medium_value_keywords = ['drupal', 'cms', 'php', 'symfony', 'twig', 'mysql']
        location_bonus = ['remote', 'work from home', 'telecommute']
        
        # Add points for high-value keywords
        for keyword in high_value_keywords:
            if keyword in text:
                score += 1.5
        
        # Add points for medium-value keywords
        for keyword in medium_value_keywords:
            if keyword in text:
                score += 0.5
        
        # Bonus for remote work
        for keyword in location_bonus:
            if keyword in text:
                score += 1.0
        
        # Cap the score at 10
        return min(score, 10.0)
    
    def send_notifications(self, report, job_count):
        """Send notifications via configured channels"""
        print("📧 Sending notifications...")
        
        # Email notification
        try:
            self.notification_manager.send_email_notification(report, job_count)
        except Exception as e:
            print(f"Failed to send email: {e}")
        
        # Slack notification
        try:
            summary = f"Found {job_count} new Drupal job opportunities today!"
            self.notification_manager.send_slack_notification(summary, job_count)
        except Exception as e:
            print(f"Failed to send Slack notification: {e}")
    
    def get_dashboard_summary(self):
        """Get a quick dashboard summary"""
        stats = self.database.get_statistics()
        config_summary = self.config.get_config_summary()
        
        return {
            'database_stats': stats,
            'config_summary': config_summary,
            'recent_jobs': self.database.get_recent_jobs(days=7, min_relevance=7.0)
        }

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='AI-Powered Drupal Job Search System')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    parser.add_argument('--no-notifications', action='store_true', help='Disable notifications')
    parser.add_argument('--dashboard', action='store_true', help='Show dashboard summary')
    parser.add_argument('--export', action='store_true', help='Export recent jobs to CSV')
    parser.add_argument('--cleanup', action='store_true', help='Cleanup old job listings')
    
    args = parser.parse_args()
    
    try:
        orchestrator = DrupalJobSearchOrchestrator(args.config)
        
        if args.dashboard:
            print("📊 Dashboard Summary:")
            summary = orchestrator.get_dashboard_summary()
            print(f"Total jobs: {summary['database_stats']['total_jobs']}")
            print(f"New today: {summary['database_stats']['new_today']}")
            print(f"This week: {summary['database_stats']['this_week']}")
            print(f"Applications: {summary['database_stats']['applications']}")
            
        elif args.export:
            filename, count = orchestrator.database.export_jobs_csv(days=30)
            print(f"📁 Exported {count} jobs to {filename}")
            
        elif args.cleanup:
            deleted = orchestrator.database.cleanup_old_jobs()
            print(f"🧹 Cleaned up {deleted} old job listings")
            
        else:
            # Run main search
            send_notifications = not args.no_notifications
            report = orchestrator.run_comprehensive_search(send_notifications)
            
            # Save report to file
            today = datetime.now().strftime("%Y-%m-%d")
            filename = f"comprehensive_report_{today}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"📄 Report saved to {filename}")
            
    except Exception as e:
        print(f"❌ System error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
