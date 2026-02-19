#!/bin/bash
# ============================================================
#  AI Codebase Assistant - Quick Setup
# ============================================================
set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   AI Codebase Assistant — Setup       ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
  echo "❌ Docker not found. Install from https://docs.docker.com/get-docker/"
  exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
  echo "❌ Docker Compose not found."
  exit 1
fi

# Set projects path
PROJECTS_PATH="${1:-$(pwd)/sample_project}"
echo -e "${YELLOW}📁 Projects path: ${PROJECTS_PATH}${NC}"

# Create a sample project if none exists
if [ ! -d "$PROJECTS_PATH" ]; then
  echo "Creating sample project at $PROJECTS_PATH..."
  mkdir -p "$PROJECTS_PATH"
  cat > "$PROJECTS_PATH/app.py" << 'EOF'
"""Sample Flask app for demo purposes."""
from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect('database.db')
    return conn

@app.route('/login', methods=['POST'])
def login():
    """User authentication endpoint."""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password)
    ).fetchone()
    
    if user:
        return jsonify({"token": "jwt_token_here", "user_id": user[0]})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/users', methods=['GET'])
def get_users():
    """Get all users from database."""
    db = get_db()
    users = db.execute("SELECT id, username, email FROM users").fetchall()
    return jsonify([{"id": u[0], "username": u[1], "email": u[2]} for u in users])

if __name__ == '__main__':
    app.run(debug=True)
EOF
  echo "✓ Sample project created"
fi

export PROJECTS_PATH

echo ""
echo -e "${CYAN}🐳 Starting Docker services...${NC}"
docker compose up -d --build

echo ""
echo -e "${CYAN}⏳ Waiting for Ollama to start...${NC}"
sleep 10

echo ""
echo -e "${CYAN}📥 Pulling AI models (this may take a few minutes on first run)...${NC}"

# Pull the LLM
MODEL="${OLLAMA_MODEL:-llama3}"
echo "  → Pulling ${MODEL}..."
docker exec codebase-ollama ollama pull "$MODEL" || true

# Pull the embedding model
echo "  → Pulling nomic-embed-text..."
docker exec codebase-ollama ollama pull nomic-embed-text || true

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "  🌐 Frontend:  http://localhost:3000"
echo "  🔌 API Docs:  http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}👉 Next steps:${NC}"
echo "  1. Open http://localhost:3000"
echo "  2. Enter path: /projects  (maps to ${PROJECTS_PATH})"
echo "  3. Click 'Index Directory'"
echo "  4. Ask questions about your code!"
echo ""
echo "  To add YOUR project:"
echo "    PROJECTS_PATH=/path/to/your/project ./setup.sh"
echo ""