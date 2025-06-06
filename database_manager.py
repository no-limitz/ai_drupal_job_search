#!/usr/bin/env python3
"""
Database manager for storing and tracking job listings
"""

import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class JobDatabase:
    def __init__(self, db_path='drupal_jobs.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Jobs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_hash TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    url TEXT,
                    description TEXT,
                    salary_range TEXT,
                    posted_date TEXT,
                    source TEXT,
                    relevance_score REAL,
                    first_seen DATE DEFAULT CURRENT_DATE,
                    last_seen DATE DEFAULT CURRENT_DATE,
                    is_active BOOLEAN DEFAULT 1,
                    applied BOOLEAN DEFAULT 0,
                    application_date DATE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Search history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_date DATE,
                    total_jobs_found INTEGER,
                    new_jobs_found INTEGER,
                    search_queries TEXT,
                    execution_time_seconds REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Application tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    application_date DATE,
                    status TEXT DEFAULT 'applied',
                    follow_up_date DATE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs (id)
                )
            ''')
            
            conn.commit()
    
    def generate_job_hash(self, title: str, company: str, url: str) -> str:
        """Generate a unique hash for a job to detect duplicates"""
        job_string = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
        return hashlib.md5(job_string.encode()).hexdigest()
    
    def add_job(self, job_data: Dict) -> bool:
        """Add a new job or update existing one"""
        job_hash = self.generate_job_hash(
            job_data.get('title', ''),
            job_data.get('company', ''),
            job_data.get('url', '')
        )
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if job already exists
            cursor.execute('SELECT id, first_seen FROM jobs WHERE job_hash = ?', (job_hash,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing job
                cursor.execute('''
                    UPDATE jobs SET 
                        last_seen = CURRENT_DATE,
                        relevance_score = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_hash = ?
                ''', (job_data.get('relevance_score', 0), job_hash))
                return False  # Not a new job
            else:
                # Insert new job
                cursor.execute('''
                    INSERT INTO jobs (
                        job_hash, title, company, location, url, description,
                        salary_range, posted_date, source, relevance_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job_hash,
                    job_data.get('title', ''),
                    job_data.get('company', ''),
                    job_data.get('location', ''),
                    job_data.get('url', ''),
                    job_data.get('description', ''),
                    job_data.get('salary_range', ''),
                    job_data.get('posted_date', ''),
                    job_data.get('source', ''),
                    job_data.get('relevance_score', 0)
                ))
                conn.commit()
                return True  # New job added
    
    def get_recent_jobs(self, days: int = 7, min_relevance: float = 6.0) -> List[Dict]:
        """Get recent jobs above relevance threshold"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM jobs 
                WHERE first_seen >= date('now', '-{} days')
                AND relevance_score >= ?
                AND is_active = 1
                ORDER BY relevance_score DESC, first_seen DESC
            '''.format(days), (min_relevance,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_new_jobs_today(self) -> List[Dict]:
        """Get jobs first seen today"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM jobs 
                WHERE first_seen = CURRENT_DATE
                ORDER BY relevance_score DESC
            ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_applied(self, job_id: int, notes: str = "") -> bool:
        """Mark a job as applied to"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Update job
            cursor.execute('''
                UPDATE jobs SET 
                    applied = 1,
                    application_date = CURRENT_DATE,
                    notes = ?
                WHERE id = ?
            ''', (notes, job_id))
            
            # Add to applications table
            cursor.execute('''
                INSERT INTO applications (job_id, application_date, notes)
                VALUES (?, CURRENT_DATE, ?)
            ''', (job_id, notes))
            
            conn.commit()
            return cursor.rowcount > 0
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total jobs
            cursor.execute('SELECT COUNT(*) FROM jobs')
            stats['total_jobs'] = cursor.fetchone()[0]
            
            # New jobs today
            cursor.execute('SELECT COUNT(*) FROM jobs WHERE first_seen = CURRENT_DATE')
            stats['new_today'] = cursor.fetchone()[0]
            
            # Jobs this week
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE first_seen >= date('now', '-7 days')")
            stats['this_week'] = cursor.fetchone()[0]
            
            # Applications
            cursor.execute('SELECT COUNT(*) FROM jobs WHERE applied = 1')
            stats['applications'] = cursor.fetchone()[0]
            
            # Average relevance score
            cursor.execute('SELECT AVG(relevance_score) FROM jobs WHERE relevance_score > 0')
            avg_score = cursor.fetchone()[0]
            stats['avg_relevance'] = round(avg_score, 2) if avg_score else 0
            
            # Top companies
            cursor.execute('''
                SELECT company, COUNT(*) as count 
                FROM jobs 
                GROUP BY company 
                ORDER BY count DESC 
                LIMIT 5
            ''')
            stats['top_companies'] = dict(cursor.fetchall())
            
            return stats
    
    def log_search(self, total_found: int, new_found: int, queries: List[str], execution_time: float):
        """Log search execution details"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO search_history (
                    search_date, total_jobs_found, new_jobs_found, 
                    search_queries, execution_time_seconds
                ) VALUES (CURRENT_DATE, ?, ?, ?, ?)
            ''', (total_found, new_found, json.dumps(queries), execution_time))
            
            conn.commit()
    
    def cleanup_old_jobs(self, days_to_keep: int = 90):
        """Remove old job listings to keep database clean"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM jobs 
                WHERE last_seen < date('now', '-{} days')
                AND applied = 0
            '''.format(days_to_keep))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            return deleted_count
    
    def export_jobs_csv(self, filename: str = None, days: int = 30):
        """Export recent jobs to CSV"""
        import csv
        
        if not filename:
            filename = f"drupal_jobs_export_{datetime.now().strftime('%Y%m%d')}.csv"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT title, company, location, url, salary_range, 
                       posted_date, relevance_score, first_seen, applied
                FROM jobs 
                WHERE first_seen >= date('now', '-{} days')
                ORDER BY relevance_score DESC
            '''.format(days))
            
            jobs = cursor.fetchall()
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['title', 'company', 'location', 'url', 'salary_range', 
                         'posted_date', 'relevance_score', 'first_seen', 'applied']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for job in jobs:
                writer.writerow(dict(job))
        
        return filename, len(jobs)

def main():
    """Initialize database without inserting fake data"""
    db = JobDatabase()
    
    # Get statistics
    stats = db.get_statistics()
    print("\nDatabase Statistics:")
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print("\n✅ Database initialized successfully")
    print("📋 Ready to receive real job data from API searches")

if __name__ == "__main__":
    main()
