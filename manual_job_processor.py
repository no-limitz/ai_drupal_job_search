#!/usr/bin/env python3
"""
Manual job processor to directly extract and store real job data
This bypasses the CrewAI agent issues and directly processes the job URLs
"""

import asyncio
import json
from datetime import datetime
from browser_job_scraper import HumanBehaviorScraper
from database_manager import JobDatabase
from main_orchestrator import DrupalJobSearchOrchestrator

class ManualJobProcessor:
    def __init__(self):
        self.database = JobDatabase()
        self.orchestrator = DrupalJobSearchOrchestrator()
    
    async def process_urls_directly(self, job_urls):
        """Process job URLs directly with browser automation"""
        print(f"🎯 Processing {len(job_urls)} job URLs directly...")
        
        jobs_added = 0
        
        async with HumanBehaviorScraper() as scraper:
            for i, url in enumerate(job_urls, 1):
                print(f"\n📋 Job {i}/{len(job_urls)}: {url}")
                
                try:
                    # Extract job details
                    result = await scraper.extract_job_details_browser(url)
                    
                    if result.get('title') and result.get('company') and not result.get('error'):
                        # Calculate relevance score
                        relevance_score = self.calculate_relevance_score(result)
                        
                        # Prepare job data for database
                        job_data = {
                            'title': result['title'],
                            'company': result['company'],
                            'location': result.get('location', 'Not specified'),
                            'url': url,
                            'description': result.get('description', ''),
                            'salary_range': result.get('salary', 'Not specified'),
                            'posted_date': datetime.now().strftime('%Y-%m-%d'),
                            'source': result.get('source', 'browser_extraction'),
                            'relevance_score': relevance_score
                        }
                        
                        # Validate job data
                        if self.orchestrator._validate_job_data(job_data):
                            # Add to database
                            is_new = self.database.add_job(job_data)
                            if is_new:
                                jobs_added += 1
                                print(f"✅ ADDED: {job_data['title']} at {job_data['company']}")
                                print(f"   Location: {job_data['location']}")
                                print(f"   Relevance: {relevance_score}/10")
                                print(f"   Drupal-related: {'✅' if relevance_score >= 6 else '❌'}")
                            else:
                                print(f"📄 DUPLICATE: {job_data['title']} at {job_data['company']}")
                        else:
                            print(f"❌ INVALID: Job data didn't pass validation")
                    else:
                        print(f"❌ FAILED: {result.get('error', 'No data extracted')}")
                        
                except Exception as e:
                    print(f"❌ ERROR: {e}")
        
        return jobs_added
    
    def calculate_relevance_score(self, job_data):
        """Calculate relevance score for a job"""
        score = 5.0  # Base score
        
        text = f"{job_data.get('title', '')} {job_data.get('description', '')}".lower()
        
        # Drupal-specific keywords
        high_value_keywords = ['drupal', 'senior drupal', 'drupal developer', 'drupal architect']
        medium_value_keywords = ['cms', 'php', 'symfony', 'twig', 'mysql', 'web developer']
        contract_keywords = ['contract', 'freelance', 'temporary', 'consulting', 'part-time']
        location_bonus = ['remote', 'work from home', 'telecommute']
        
        # Add points for high-value keywords
        for keyword in high_value_keywords:
            if keyword in text:
                score += 2.0
        
        # Add points for medium-value keywords
        for keyword in medium_value_keywords:
            if keyword in text:
                score += 0.5
        
        # Bonus for contract work
        for keyword in contract_keywords:
            if keyword in text:
                score += 1.0
        
        # Bonus for remote work
        for keyword in location_bonus:
            if keyword in text:
                score += 1.0
        
        # Cap the score at 10
        return min(score, 10.0)

async def main():
    """Main function to process jobs directly"""
    print("🚀 Manual Job Processor - Direct URL Processing")
    print("=" * 60)
    
    # Job URLs found in recent search results
    job_urls = [
        'https://www.indeed.com/viewjob?jk=fa6834a1d5f7a675',
        'https://www.linkedin.com/jobs/view/senior-drupal-developer-remote-usa-at-fullstack-labs-4092146149',
        'https://www.linkedin.com/jobs/view/senior-drupal-developer-at-gravity-infosolutions-4235001609',
        'https://www.linkedin.com/jobs/view/senior-drupal-developer-at-madden-media-4215926399',
        'https://www.linkedin.com/jobs/view/senior-drupal-developer-temporary-assignment-at-halo-media-4234299056',
        'https://www.linkedin.com/jobs/view/senior-web-developer-senior-drupal-developer-arts-sciences-remote-at-washington-university-in-st-louis-4110570619',
        'https://in.linkedin.com/jobs/view/senior-drupal-developer-part-time-contract-at-upbott-consulting-inc-4235645962',
        'https://www.linkedin.com/jobs/view/sr-drupal-developer-at-inadev-4174443858',
        'https://www.dice.com/jobs/detail/Senior-Drupal-Developer-%26%2345-Remote-Staffigo-Technical-Services%2C-LLC-Atlanta%2C-GA-30301/10466827/722601'
    ]
    
    processor = ManualJobProcessor()
    
    # Show initial database stats
    initial_stats = processor.database.get_statistics()
    print(f"📊 Initial database stats: {initial_stats['total_jobs']} jobs")
    
    # Process all URLs
    jobs_added = await processor.process_urls_directly(job_urls)
    
    # Show final stats
    final_stats = processor.database.get_statistics()
    print(f"\n🎉 RESULTS:")
    print(f"📊 Total jobs in database: {final_stats['total_jobs']}")
    print(f"🆕 New jobs added: {jobs_added}")
    print(f"⭐ Average relevance score: {final_stats['avg_relevance']}")
    
    # Show recent jobs
    recent_jobs = processor.database.get_recent_jobs(days=1, min_relevance=0)
    if recent_jobs:
        print(f"\n📋 Recent jobs added:")
        for job in recent_jobs[:5]:
            print(f"• {job['title']} at {job['company']} (Score: {job['relevance_score']}/10)")
    
    return jobs_added

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\n✅ Manual processing completed! Added {result} jobs to database.")