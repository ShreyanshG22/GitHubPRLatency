Here's a step-by-step guide to get your code running locally:

Step 1: Get the Code
Option A — Save to GitHub (Recommended)

Click the "Save to GitHub" button on the Emergent platform
It will push all your code to a GitHub repo you choose
Then clone it: git clone https://github.com/your-username/your-repo.git
Option B — Download Directly

Use the Download / Export option in the Emergent interface to get a zip of your project
Step 2: Install Prerequisites
You'll need these on your laptop:

Tool	Install
Python 3.11+	python.org
Node.js 18+	nodejs.org
MongoDB	mongodb.com/try/download or brew install mongodb-community on Mac
Yarn	npm install -g yarn
Step 3: Start MongoDB
# Mac (Homebrew)
brew services start mongodb-community

# Linux
sudo systemctl start mongod

# Or use Docker
docker run -d -p 27017:27017 --name mongo mongo:7
Step 4: Set Up the Backend
cd backend

# Create a virtual environment
python -m venv venv
source venv/bin/activate   # Mac/Linux
# venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Create your .env file
Create/edit backend/.env:

MONGO_URL="mongodb://localhost:27017"
DB_NAME="pr_review_bot"
CORS_ORIGINS="http://localhost:3000"
JWT_SECRET="a3f8c9d2e1b4567890abcdef1234567890abcdef1234567890abcdef12345678"
ADMIN_EMAIL="admin@example.com"
ADMIN_PASSWORD="admin123"
EMERGENT_LLM_KEY="sk-emergent-0F0F3B58a8636B4529"
GITHUB_WEBHOOK_SECRET=""
GITHUB_TOKEN=""
# Start the backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
You should see:
INFO:     PR Review Bot API started
INFO:     Uvicorn running on http://0.0.0.0:8001
Step 5: Set Up the Frontend
cd frontend

# Install dependencies
yarn install

# Create your .env file
Create/edit frontend/.env:

REACT_APP_BACKEND_URL=http://localhost:8001
# Start the frontend
yarn start
Opens at http://localhost:3000

Step 6: Test Locally
Login at http://localhost:3000 with admin@example.com / admin123

Test APIs:

# Health check
curl http://localhost:8001/api/

# Login
curl -c cookies.txt -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}'

# Analyze C++ code
curl -b cookies.txt -X POST http://localhost:8001/api/analyze-cpp \
  -H "Content-Type: application/json" \
  -d '{"code":"void f(std::vector<int> v) { for(int i=0;i<100;++i) { v.push_back(i); } }"}'

# Test webhook
curl -X POST http://localhost:8001/api/github-webhook \
  -H "X-GitHub-Event: ping" \
  -H "Content-Type: application/json" \
  -d '{"zen":"test","repository":{"full_name":"you/repo"}}'
Project Structure on Your Laptop
your-repo/
├── backend/
│   ├── server.py          # Main FastAPI app
│   ├── comment_bot.py     # GitHub comment formatter
│   ├── cpp_analyzer.py    # C++ static analyzer (14 rules)
│   ├── diff_parser.py     # Unified diff parser
│   ├── analyzer.py        # LLM code review (GPT-5.2)
│   ├── models.py          # Pydantic models
│   ├── github_client.py   # GitHub API client
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   ├── package.json
│   └── .env
Note: The EMERGENT_LLM_KEY provided works for LLM-powered analysis. If it runs out of credits, go to your Emergent Profile → Universal Key → Add Balance.
