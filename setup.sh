#!/bin/bash

# AI Drupal Job Search - Setup Script
# This script automates the complete setup process

set -e  # Exit on any error

echo "🚀 Setting up AI Drupal Job Search System..."
echo "=================================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📚 Installing Python packages..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️ Creating .env file from template..."
    cp .env.example .env
    echo "📝 Please edit .env file with your actual API keys!"
else
    echo "✅ .env file already exists"
fi

# Create initial configuration
echo "🔧 Initializing configuration..."
python3 -c "
from config_manager import JobSearchConfiguration
config = JobSearchConfiguration()
print('✅ Configuration initialized')
"

# Initialize database
echo "🗄️ Initializing database..."
python3 -c "
from database_manager import JobDatabase
db = JobDatabase()
print('✅ Database initialized')
"

# Make scripts executable
chmod +x run_daily_search.sh
chmod +x run_search.py

echo ""
echo "🎉 Setup completed successfully!"
echo "=================================================="
echo ""
echo "📋 Next steps:"
echo "1. Edit .env file with your API keys:"
echo "   - SERPER_API_KEY (get from https://serper.dev/)"
echo "   - BRAVE_API_KEY (get from https://api.search.brave.com/)"
echo "   - OPENAI_API_KEY (get from https://platform.openai.com/)"
echo ""
echo "2. Test the setup:"
echo "   ./run_search.py --dashboard"
echo ""
echo "3. Run your first search:"
echo "   ./run_search.py"
echo ""
echo "4. Set up daily automation (optional):"
echo "   crontab -e"
echo "   Add: 0 9 * * * /Users/bobby/Sites/Developer/ai_drupal_job_search/run_daily_search.sh"
echo ""
echo "📖 For detailed instructions, see README.md"
echo "🆘 For help, check the troubleshooting section in README.md"
