#!/bin/bash
# Setup script for VorLoop Crypto Prediction Terminal

set -e

echo "🔮 VorLoop Setup Script"
echo "========================"

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required but not installed."; exit 1; }

# Setup backend
echo ""
echo "📦 Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created virtual environment"
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p models/trained

echo "✅ Backend setup complete"

# Setup frontend
echo ""
echo "📦 Setting up frontend..."
cd ../frontend

npm install

echo "✅ Frontend setup complete"

# Setup environment file
cd ..
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "📝 Created .env file - please update with your API keys"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To start development:"
echo "  Backend:  cd backend && source venv/bin/activate && python main.py"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Or use Docker:"
echo "  cd docker && docker-compose up -d"

