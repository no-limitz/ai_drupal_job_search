#!/usr/bin/env python3
"""
Configuration manager for Drupal Job Search
Allows easy customization of search parameters
"""

import json
import os
from datetime import datetime, timedelta

class JobSearchConfiguration:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.default_config = {
            "search_parameters": {
                "keywords": [
                    "Senior Drupal Developer",
                    "Drupal Developer Contract",
                    "Drupal Backend Developer",
                    "Drupal CMS Developer",
                    "Drupal Architect",
                    "Drupal Site Builder",
                    "Drupal Module Developer"
                ],
                "job_boards": [
                    "indeed.com",
                    "linkedin.com/jobs",
                    "dice.com",
                    "flexjobs.com",
                    "upwork.com",
                    "freelancer.com",
                    "toptal.com",
                    "gun.io",
                    "arc.dev",
                    "stackoverflow.com/jobs",
                    "angel.co",
                    "remoteok.io",
                    "weworkremotely.com"
                ],
                "locations": [
                    "United States",
                    "Remote USA",
                    "US Remote",
                    "Remote",
                    "Anywhere"
                ],
                "experience_levels": [
                    "Senior",
                    "Lead",
                    "Principal",
                    "Expert",
                    "Architect"
                ],
                "contract_types": [
                    "Contract",
                    "Freelance",
                    "Consulting",
                    "Part-time",
                    "Project-based"
                ]
            },
            "search_settings": {
                "days_back": 7,
                "max_results_per_board": 20,
                "minimum_relevance_score": 6,
                "exclude_keywords": [
                    "intern",
                    "junior",
                    "entry level",
                    "trainee",
                    "graduate"
                ]
            },
            "notification_settings": {
                "email_enabled": True,
                "slack_enabled": True,
                "minimum_jobs_for_notification": 1,
                "daily_digest_time": "09:00"
            },
            "report_settings": {
                "include_job_descriptions": True,
                "include_salary_info": True,
                "include_application_links": True,
                "group_by_location": False,
                "sort_by_relevance": True
            }
        }
        self.config = self.load_config()
    
    def load_config(self):
        """Load configuration from file or create default"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                # Merge with defaults for any missing keys
                return self.merge_configs(self.default_config, config)
            except Exception as e:
                print(f"Error loading config: {e}, using defaults")
                return self.default_config
        else:
            self.save_config(self.default_config)
            return self.default_config
    
    def save_config(self, config=None):
        """Save configuration to file"""
        config_to_save = config or self.config
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=2)
            print(f"Configuration saved to {self.config_file}")
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def merge_configs(self, default, user):
        """Recursively merge user config with defaults"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def get_search_queries(self):
        """Generate search queries based on configuration"""
        queries = []
        keywords = self.config['search_parameters']['keywords']
        job_boards = self.config['search_parameters']['job_boards']
        contract_types = self.config['search_parameters']['contract_types']
        
        for keyword in keywords:
            for board in job_boards:
                for contract_type in contract_types:
                    query = f'"{keyword}" {contract_type} site:{board} remote USA'
                    queries.append(query)
        
        return queries
    
    def update_keywords(self, new_keywords):
        """Update search keywords"""
        self.config['search_parameters']['keywords'] = new_keywords
        self.save_config()
    
    def add_job_board(self, board_url):
        """Add a new job board to search"""
        if board_url not in self.config['search_parameters']['job_boards']:
            self.config['search_parameters']['job_boards'].append(board_url)
            self.save_config()
    
    def set_relevance_threshold(self, score):
        """Set minimum relevance score"""
        self.config['search_settings']['minimum_relevance_score'] = score
        self.save_config()
    
    def get_config_summary(self):
        """Get a summary of current configuration"""
        return {
            'keywords_count': len(self.config['search_parameters']['keywords']),
            'job_boards_count': len(self.config['search_parameters']['job_boards']),
            'days_back': self.config['search_settings']['days_back'],
            'min_relevance': self.config['search_settings']['minimum_relevance_score'],
            'notifications_enabled': {
                'email': self.config['notification_settings']['email_enabled'],
                'slack': self.config['notification_settings']['slack_enabled']
            }
        }

def create_sample_config():
    """Create a sample configuration file"""
    config_manager = JobSearchConfiguration('sample_config.json')
    
    # Customize for specific use case
    config_manager.config['search_parameters']['keywords'] = [
        "Senior Drupal Developer",
        "Drupal Technical Lead",
        "Drupal Solutions Architect"
    ]
    
    config_manager.config['search_settings']['minimum_relevance_score'] = 8
    config_manager.config['search_settings']['days_back'] = 3
    
    config_manager.save_config()
    print("Sample configuration created as sample_config.json")

if __name__ == "__main__":
    # Demo usage
    config = JobSearchConfiguration()
    print("Current configuration summary:")
    print(json.dumps(config.get_config_summary(), indent=2))
    
    print(f"\nGenerated {len(config.get_search_queries())} search queries")
    
    # Create sample config
    create_sample_config()
