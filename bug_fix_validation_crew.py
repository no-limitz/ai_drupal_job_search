#!/usr/bin/env python3
"""
CrewAI Bug Fix Validation System
Creates specialized agents for testing and evaluating bug fixes

This system includes:
1. Test Script Writer Agent - Creates comprehensive test scripts
2. Bug Evaluation Agent - Validates bug fix completion
3. Quality Assurance Agent - Ensures no regressions introduced
"""

import os
import sys
from datetime import datetime
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

class BugFixValidationCrew:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.1,
            openai_api_key=os.getenv('OPENAI_API_KEY')
        )
    
    def create_agents(self):
        """Create specialized agents for bug fix validation"""
        
        # Test Script Writer Agent
        test_writer = Agent(
            role='Test Script Development Specialist',
            goal='Create comprehensive test scripts to validate bug fixes and prevent regressions',
            backstory="""You are an expert software testing engineer who specializes in creating 
            thorough, automated test scripts. You understand how to test both positive and negative 
            scenarios, edge cases, and integration points. You write clean, maintainable test code 
            that clearly validates expected behavior.""",
            tools=[],
            llm=self.llm,
            verbose=True
        )
        
        # Bug Evaluation Agent
        bug_evaluator = Agent(
            role='Bug Fix Evaluation Specialist',
            goal='Evaluate whether bug fixes are complete and effective',
            backstory="""You are a senior QA engineer with expertise in validating bug fixes. 
            You thoroughly analyze code changes, test results, and system behavior to determine 
            if bugs have been properly resolved. You check for completeness, correctness, and 
            potential side effects.""",
            tools=[],
            llm=self.llm,
            verbose=True
        )
        
        # Quality Assurance Agent
        qa_specialist = Agent(
            role='Quality Assurance Specialist',
            goal='Ensure bug fixes maintain code quality and introduce no regressions',
            backstory="""You are a quality assurance expert who reviews code changes for 
            maintainability, performance impact, and regression prevention. You analyze the 
            broader impact of bug fixes on the system architecture and user experience.""",
            tools=[],
            llm=self.llm,
            verbose=True
        )
        
        return test_writer, bug_evaluator, qa_specialist
    
    def create_tasks(self, test_writer, bug_evaluator, qa_specialist, bug_info):
        """Create tasks for bug fix validation"""
        
        # Task 1: Create test scripts
        test_creation_task = Task(
            description=f"""
            Create comprehensive test scripts for Bug #{bug_info['number']}: {bug_info['title']}
            
            Bug Details:
            - File: {bug_info['file']}
            - Issue: {bug_info['issue']}
            - Impact: {bug_info['impact']}
            - Fix: {bug_info['fix_description']}
            
            Create test scripts that:
            1. Reproduce the original bug condition
            2. Verify the fix resolves the issue
            3. Test edge cases and boundary conditions
            4. Ensure no data corruption or system instability
            5. Validate API integration points
            6. Check error handling and recovery
            
            Output Python test scripts with:
            - Clear test case descriptions
            - Setup and teardown procedures
            - Assertions that verify expected behavior
            - Mock data for testing scenarios
            - Performance validation if applicable
            """,
            agent=test_writer,
            expected_output="Complete Python test scripts with comprehensive test cases"
        )
        
        # Task 2: Evaluate bug fix completion
        evaluation_task = Task(
            description=f"""
            Evaluate the completion of Bug #{bug_info['number']}: {bug_info['title']}
            
            Code Changes Made:
            {bug_info['changes_made']}
            
            Evaluation Criteria:
            1. Original bug symptoms are eliminated
            2. Root cause has been addressed (not just symptoms)
            3. Fix is implemented correctly and completely
            4. No workarounds or temporary patches
            5. Code follows best practices and standards
            6. Documentation is updated if needed
            
            Review the code changes and determine:
            - Is the bug completely fixed?
            - Are there any remaining issues?
            - Is the implementation robust?
            - Are there potential edge cases not addressed?
            
            Provide a detailed evaluation with recommendations.
            """,
            agent=bug_evaluator,
            context=[test_creation_task],
            expected_output="Detailed evaluation report with pass/fail determination and recommendations"
        )
        
        # Task 3: Quality assurance review
        qa_review_task = Task(
            description=f"""
            Conduct quality assurance review for Bug #{bug_info['number']} fix
            
            Review Areas:
            1. Code Quality
               - Readability and maintainability
               - Following coding standards
               - Proper error handling
               - Performance considerations
            
            2. Regression Analysis
               - Impact on existing functionality
               - Compatibility with other components
               - Database integrity
               - API contract compliance
            
            3. System Impact
               - Performance implications
               - Resource usage changes
               - Scalability considerations
               - Security implications
            
            4. Documentation and Testing
               - Test coverage adequacy
               - Documentation updates needed
               - Deployment considerations
               - Monitoring requirements
            
            Provide comprehensive QA sign-off or list of issues to address.
            """,
            agent=qa_specialist,
            context=[test_creation_task, evaluation_task],
            expected_output="Complete QA review with sign-off status and action items"
        )
        
        return [test_creation_task, evaluation_task, qa_review_task]
    
    def validate_bug_fix(self, bug_number: str, bug_title: str, bug_file: str, 
                        bug_issue: str, bug_impact: str, fix_description: str, 
                        changes_made: str):
        """Run the bug fix validation process"""
        
        print(f"🔍 Starting Bug Fix Validation for Bug #{bug_number}")
        print(f"📋 Bug: {bug_title}")
        print("=" * 80)
        
        bug_info = {
            'number': bug_number,
            'title': bug_title,
            'file': bug_file,
            'issue': bug_issue,
            'impact': bug_impact,
            'fix_description': fix_description,
            'changes_made': changes_made
        }
        
        try:
            # Create agents and tasks
            test_writer, bug_evaluator, qa_specialist = self.create_agents()
            tasks = self.create_tasks(test_writer, bug_evaluator, qa_specialist, bug_info)
            
            # Create and run crew
            crew = Crew(
                agents=[test_writer, bug_evaluator, qa_specialist],
                tasks=tasks,
                process=Process.sequential,
                verbose=True
            )
            
            # Execute validation
            result = crew.kickoff()
            
            # Save validation report
            self.save_validation_report(bug_number, result)
            
            print(f"✅ Bug Fix Validation completed for Bug #{bug_number}")
            return result
            
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            raise
    
    def save_validation_report(self, bug_number: str, validation_result):
        """Save the validation report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bug_{bug_number}_validation_report_{timestamp}.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Bug #{bug_number} Validation Report\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## Validation Results\n\n")
            f.write(str(validation_result))
            f.write("\n\n---\n*Generated by AI Bug Fix Validation System*")
        
        print(f"📄 Validation report saved to {filename}")
        return filename

def main():
    """Run bug fix validation for Bug #001"""
    
    # Initialize validation crew
    validation_crew = BugFixValidationCrew()
    
    # Run validation for Bug #001
    result = validation_crew.validate_bug_fix(
        bug_number='001',
        bug_title='Fake Job Data Generation',
        bug_file='database_manager.py lines 283-315',
        bug_issue='System generates completely fake job listings instead of real ones',
        bug_impact='Users receive fake job opportunities that don\'t exist',
        fix_description='Remove fake job generation, implement real API parsing',
        changes_made='''
        1. Removed sample job data insertion from database_manager.py main() function
        2. Modified main() to only initialize database without inserting fake data
        3. Cleaned existing database by removing drupal_jobs.db file
        4. Enhanced URL validation to reject example.com URLs
        5. Strengthened job data validation to require real URLs and Drupal relevance
        '''
    )
    
    print("\n" + "="*80)
    print("BUG FIX VALIDATION COMPLETED")
    print("="*80)
    
    return result

if __name__ == "__main__":
    main()