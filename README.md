# AI-Powered WebSocket Chat Application

A real-time chat application with AI capabilities, featuring conversation memory, intent detection, function calling, and automated session summarization. Built with FastAPI, WebSocket, Supabase, and Groq's LLaMA AI model.

## 🌟 Features

- **Real-time WebSocket Communication**: Instant bidirectional messaging
- **AI-Powered Responses**: Using Meta's LLaMA 4 Scout model via Groq
- **Intelligent Intent Detection**: Automatically switches between Chat, Code Assistant, Tutorial, and Technical Support modes
- **Function Calling**: AI can retrieve session statistics, search chat history, and list previous sessions
- **Conversation Memory**: Full context awareness across entire chat sessions
- **Automated Session Summarization**: AI-generated summaries with topics, sentiment analysis, and key metrics
- **Persistent Storage**: All conversations stored in Supabase PostgreSQL
- **Beautiful UI**: Clean, responsive interface with Markdown support

---

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Database Schema](#database-schema)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [API Endpoints](#api-endpoints)
- [Design Choices](#design-choices)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

### System Architecture

```
┌─────────────┐         WebSocket          ┌──────────────┐
│   Browser   │◄──────────────────────────►│   FastAPI    │
│   Client    │         HTTP/WS            │   Server     │
└─────────────┘                            └──────┬───────┘
                                                   │
                                                   │
                          ┌────────────────────────┼────────────────────┐
                          │                        │                    │
                          ▼                        ▼                    ▼
                   ┌─────────────┐         ┌─────────────┐     ┌─────────────┐
                   │   Supabase  │         │   Groq AI   │     │   Memory    │
                   │  PostgreSQL │         │   LLaMA-4   │     │   System    │
                   └─────────────┘         └─────────────┘     └─────────────┘
```

### Key Components

1. **Frontend (HTML/JavaScript)**
   - WebSocket client for real-time communication
   - Markdown rendering for formatted AI responses
   - Session management and UI updates

2. **Backend (FastAPI/Python)**
   - WebSocket endpoint for chat communication
   - Intent detection and routing
   - Function calling system
   - Session management and summarization

3. **Database (Supabase/PostgreSQL)**
   - Session metadata storage
   - Message logging with timestamps
   - JSONB for flexible data storage

4. **AI Integration (Groq/LLaMA)**
   - Streaming responses for better UX
   - Context-aware conversation handling
   - Automated summarization

---

## 🔧 Prerequisites

Before you begin, ensure you have the following installed and configured:

### Required Software

- **Python 3.11+**: [Download Python](https://www.python.org/downloads/)
- **pip**: Python package installer (comes with Python)
- **Git**: For version control

### Required Accounts & API Keys

1. **Supabase Account**
   - Sign up at [https://supabase.com](https://supabase.com)
   - Create a new project
   - Note down your `SUPABASE_URL` and `SUPABASE_KEY` from Project Settings > API

2. **Groq API Key**
   - Sign up at [https://console.groq.com](https://console.groq.com)
   - Generate an API key
   - Note down your `GROQ_API_KEY`

---

## 📦 Installation & Setup

### Step 1: Clone the Repository

```bash
git clone <your-repository-url>
cd GenPy
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Required Dependencies** (from `requirements.txt`):
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
websockets==14.1
supabase==2.11.0
python-dotenv==1.0.1
langchain-groq==0.2.2
aiohttp==3.12.15
```

### Step 4: Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your credentials:
```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# Groq API Configuration
GROQ_API_KEY=your-groq-api-key
```

### Step 5: Set Up Supabase Database

1. Go to your Supabase Dashboard
2. Navigate to **SQL Editor** > **New Query**
3. Copy the entire contents of `database/schema.sql`
4. Paste and execute the SQL script

This will create:
- `sessions` table for chat session metadata
- `session_logs` table for individual messages
- Necessary indexes for performance
- Triggers for automatic timestamp updates

---

## 🗄️ Database Schema

### Tables

#### 1. **sessions**
Stores metadata for each chat session.

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Primary key |
| `session_id` | UUID | Unique session identifier |
| `user_id` | TEXT | User identifier |
| `status` | TEXT | Session status (active/completed) |
| `start_time` | TIMESTAMPTZ | Session start timestamp |
| `end_time` | TIMESTAMPTZ | Session end timestamp |
| `summary` | TEXT | AI-generated summary |
| `topics` | JSONB | Array of discussed topics |
| `sentiment` | TEXT | Overall sentiment (positive/neutral/negative) |
| `metrics` | JSONB | Session metrics (message counts, word counts) |
| `user_rating` | INTEGER | User rating (1-5) |
| `rated_at` | TIMESTAMPTZ | Rating timestamp |
| `key_outcomes` | TEXT | Key outcomes from conversation |
| `created_at` | TIMESTAMPTZ | Record creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

#### 2. **session_logs**
Stores individual messages within sessions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL | Primary key |
| `session_id` | UUID | Foreign key to sessions |
| `event_type` | TEXT | Message type (user/ai/system) |
| `message` | TEXT | Message content |
| `metadata` | JSONB | Additional message metadata |
| `created_at` | TIMESTAMPTZ | Message timestamp |

### Complete SQL Schema

```sql
-- Create sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    summary TEXT,
    topics JSONB DEFAULT '[]'::jsonb,
    sentiment TEXT,
    metrics JSONB DEFAULT '{}'::jsonb,
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    rated_at TIMESTAMPTZ,
    key_outcomes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create session_logs table
CREATE TABLE IF NOT EXISTS session_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('user', 'ai', 'system')),
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time DESC);
CREATE INDEX IF NOT EXISTS idx_session_logs_session_id ON session_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_session_logs_created_at ON session_logs(created_at DESC);

-- Create trigger for automatic updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Note**: The complete schema with all options is available in `database/schema.sql`

---

## 🚀 Running the Application

### Development Server

Start the FastAPI development server with auto-reload:

```bash
uvicorn proj:app --reload --host 0.0.0.0 --port 8001
```

**Startup Logs:**
```
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Access the Application

1. **Chat Interface**: Open your browser and navigate to:
   ```
   http://localhost:8001
   ```

2. **API Documentation**: FastAPI provides automatic API docs at:
   ```
   http://localhost:8001/docs
   ```

3. **Health Check**: Verify the server is running:
   ```
   http://localhost:8001/health
   ```

### Production Deployment

For production, use a production-grade ASGI server:

```bash
uvicorn proj:app --host 0.0.0.0 --port 8001 --workers 4
```

Or with Gunicorn:
```bash
gunicorn proj:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

---

## 🧪 Testing

### Test Files Location

All test files are in the `tests/` directory:
- `tests/check_database.py` - Database connection verification
- `tests/test_post_session.py` - Session management tests

### 1. Database Connection Test

Verify your Supabase connection:

```bash
python tests/check_database.py
```

**Expected Output:**
```
✅ Successfully connected to Supabase
✅ Sessions table exists
✅ Session_logs table exists
📊 Current sessions: 5
📊 Total messages: 127
```

### 2. Session Management Test

Test session creation and retrieval:

```bash
python tests/test_post_session.py
```

### 3. WebSocket Testing

#### Using Browser Console

1. Open the chat interface at `http://localhost:8001`
2. Open browser DevTools (F12)
3. Go to Console tab
4. Send messages and observe WebSocket communication

#### Using Python WebSocket Client

```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8001/ws/session/test-session-123"
    async with websockets.connect(uri) as websocket:
        # Send a message
        await websocket.send("Hello, AI!")
        
        # Receive response
        response = await websocket.recv()
        print(f"Received: {response}")

asyncio.run(test_websocket())
```

### 4. Manual Testing Checklist

- [ ] Start server and access chat interface
- [ ] Send a simple message and receive AI response
- [ ] Test intent switching (ask a coding question, then a technical issue)
- [ ] Use function calling: "How many messages have I sent?"
- [ ] End session and verify summary generation
- [ ] View session summary page
- [ ] Check database for stored sessions and logs

---

## 🔌 API Endpoints

### WebSocket Endpoints

#### Chat Session WebSocket
```
WS /ws/session/{session_id}
```
- **Description**: Real-time bidirectional chat communication
- **Parameters**:
  - `session_id` (UUID): Unique session identifier
- **Events**:
  - Client → Server: User messages (text)
  - Server → Client: AI responses (streaming tokens)

### HTTP Endpoints

#### 1. Home Page
```
GET /
```
Returns the chat interface HTML.

#### 2. Session Summary Page
```
GET /summary/{session_id}
```
Returns formatted summary page for a completed session.

#### 3. Get Session Summary (API)
```
GET /api/session/{session_id}/summary
```
Returns JSON with session summary data.

**Response:**
```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "start_time": "2025-12-18T10:30:00Z",
  "end_time": "2025-12-18T11:15:00Z",
  "summary": "The user asked about Python...",
  "topics": ["Python", "FastAPI", "WebSockets"],
  "sentiment": "positive",
  "metrics": {
    "total_messages": 24,
    "user_messages": 12,
    "ai_messages": 12
  }
}
```

#### 4. List All Sessions
```
GET /api/sessions
```
Returns list of recent sessions.

#### 5. Rate Session
```
POST /api/session/{session_id}/rate
```
**Body:**
```json
{
  "rating": 5
}
```

#### 6. Regenerate Summary
```
POST /api/session/{session_id}/regenerate-summary
```
Manually triggers summary regeneration.

#### 7. Health Check
```
GET /health
```
Returns server and database health status.

---

## 💡 Design Choices

### 1. **Multi-Step Intent Detection**

**Problem**: Generic AI responses don't adapt to different types of user queries.

**Solution**: Implemented a keyword-based intent detection system that classifies messages into four modes:
- **Chat Mode**: General conversation
- **Code Assistant**: Programming questions
- **Tutorial Mode**: Learning and explanations
- **Technical Support**: Troubleshooting and debugging

**Why**: This provides specialized system prompts for each intent, resulting in more appropriate and helpful responses.

**Implementation**:
```python
def detect_intent(message: str) -> str:
    message_lower = message.lower()
    if any(keyword in message_lower for keyword in ['error', 'bug', 'issue']):
        return 'technical_support'
    # ... more intent checks
    return 'casual_chat'
```

### 2. **Function Calling System**

**Problem**: AI needs access to real-time data (session stats, chat history) to answer user questions about their activity.

**Solution**: Implemented a tool-based function calling system where AI can invoke predefined functions:
- `get_session_stats`: Retrieve session metrics
- `search_chat_history`: Search previous messages
- `get_all_sessions`: List user's chat sessions

**Why**: Enables the AI to provide accurate, data-driven answers rather than guessing.

**Implementation**:
```python
def should_use_tool(message: str) -> tuple:
    if 'how many messages' in message.lower():
        return (True, "get_session_stats", {"session_id": session_id})
    return (False, None, None)
```

### 3. **Conversation Memory with Full Context**

**Problem**: AI needs to remember the entire conversation to maintain coherent, context-aware responses.

**Solution**: Load and include all previous messages from the database in each AI request:
```python
history = supabase.from_("session_logs")
                  .select("*")
                  .eq("session_id", session_id)
                  .order("id")
                  .limit(20)
                  .execute()
```

**Why**: Provides true conversational continuity without losing context across multiple exchanges.

**Trade-off**: Limited to last 20 messages to prevent token overflow. For longer conversations, could implement sliding window or summarization strategies.

### 4. **Streaming Responses**

**Problem**: Large AI responses can take several seconds to generate, creating poor UX.

**Solution**: Use token streaming to send response chunks as they're generated:
```python
for chunk in model.stream(messages):
    token = chunk.content
    await websocket.send_text(token)
```

**Why**: Users see responses appear in real-time (like ChatGPT), making the application feel faster and more responsive.

### 5. **Automated Session Summarization**

**Problem**: Users need to quickly understand what was discussed in a chat session without reading every message.

**Solution**: When a session ends, automatically generate an AI-powered summary including:
- Overall summary (3-4 sentences)
- Key topics discussed
- Sentiment analysis
- Metrics (message counts, word counts)
- Key outcomes

**Why**: Provides value-added session history and allows users to quickly review past conversations.

**Implementation**:
```python
async def generate_session_summary(session_id: str):
    # Fetch all messages
    logs = supabase.from_("session_logs").select("*")...
    
    # Build conversation text
    conversation = "\n".join([f"{log['event_type']}: {log['message']}" for log in logs])
    
    # AI generates structured summary
    summary_response = model.invoke(summary_prompt)
    return json.loads(summary_response.content)
```

### 6. **WebSocket vs HTTP**

**Choice**: WebSocket for real-time chat, HTTP for API endpoints.

**Why**:
- WebSocket provides instant bidirectional communication needed for chat
- Maintains persistent connection for streaming responses
- HTTP used for REST API endpoints (summaries, session management)

### 7. **Supabase PostgreSQL Storage**

**Choice**: Supabase (managed PostgreSQL) for data persistence.

**Why**:
- Free tier with generous limits
- Built-in REST API and real-time subscriptions
- PostgreSQL's JSONB for flexible schema (topics, metrics)
- Automatic backups and scaling
- Easy to set up and deploy

**Alternative Considered**: SQLite would work for local/small deployments but lacks the scalability and built-in features of PostgreSQL.

### 8. **JSONB for Flexible Fields**

**Choice**: Store `topics`, `metrics`, and `metadata` as JSONB rather than relational tables.

**Why**:
- Flexible schema allows adding new fields without migrations
- Easy to query with PostgreSQL's JSONB operators
- Natural fit for AI-generated structured data
- Reduces database complexity

### 9. **Error Handling Strategy**

**Approach**: Graceful degradation with user-friendly error messages.

**Examples**:
- If AI generation fails, return error message but keep session active
- If database connection fails, log to console but don't crash server
- If summary generation fails, save session with partial data

**Why**: Maintains system reliability even when components fail.

---

## 📁 Project Structure

```
GenPy/
├── proj.py                      # Main application file
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
│
├── database/                    # Database schema and migrations
│   └── schema.sql              # Complete Supabase schema
│
├── tests/                       # Test files
│   ├── check_database.py       # Database connection test
│   └── test_post_session.py    # Session management test
│
├── docs/                        # Additional documentation (optional)
│   └── ...
│
└── supabase/                    # Legacy schema files (can be removed)
    ├── supabase_schema.sql
    ├── add_metadata_column.sql
    ├── add_missing_columns.sql
    └── fix_session_logs.sql
```

### Key Files

- **proj.py**: Main FastAPI application with WebSocket handling, AI integration, and all endpoints
- **requirements.txt**: All Python package dependencies
- **database/schema.sql**: Complete database schema for Supabase
- **.env.example**: Template for environment variables (copy to `.env`)
- **tests/**: Scripts to verify database connection and test functionality

---

## 🔍 How It Works

### Flow Diagram

```
1. User opens chat interface (/)
   │
2. JavaScript generates/retrieves session UUID
   │
3. WebSocket connection established to /ws/session/{session_id}
   │
4. Session record created in database (if new)
   │
5. User sends message ──────────────────────────┐
   │                                             │
6. Message logged to session_logs               │
   │                                             │
7. Intent Detection (Chat/Code/Tutorial/Tech)   │
   │                                             │
8. Check if function calling needed ────────┐   │
   │                                         │   │
   │ NO                          YES         │   │
   │                              │          │   │
   │                         Execute tool    │   │
   │                         (DB query)      │   │
   │                              │          │   │
   └──────────────────────────────┘          │   │
                                             │   │
9. Load conversation history (last 20 msgs)  │   │
   │                                         │   │
10. Build context with system prompt +       │   │
    history + current message + tool results │   │
   │                                         │   │
11. Stream AI response tokens via WebSocket  │   │
   │                                         │   │
12. User sees real-time response ────────────┘   │
   │                                             │
13. AI response logged to session_logs          │
   │                                             │
14. User can continue conversation ─────────────┘
   │
15. User ends session (closes browser/clicks End)
   │
16. WebSocket disconnect detected
   │
17. Generate AI summary of entire conversation
   │
18. Update session record with:
    - end_time
    - summary
    - topics
    - sentiment
    - metrics
   │
19. User can view summary at /summary/{session_id}
```

### Intent Detection Examples

| User Message | Detected Intent | System Prompt |
|--------------|----------------|---------------|
| "Hello!" | Casual Chat | Friendly assistant |
| "How do I write a Python function?" | Code Assistant | Expert programmer |
| "Explain how loops work" | Tutorial | Patient teacher |
| "My code throws an error" | Technical Support | Systematic troubleshooter |

### Function Calling Examples

| User Query | Tool Called | Parameters |
|------------|-------------|------------|
| "How many messages have I sent?" | `get_session_stats` | `{session_id}` |
| "Did I mention Python?" | `search_chat_history` | `{session_id, keyword: "python"}` |
| "Show my previous chats" | `get_all_sessions` | `{}` |

---

## 🐛 Troubleshooting

### Common Issues

#### 1. **Database Connection Error**

**Error**: `Error checking/creating session`

**Solution**:
- Verify your `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
- Ensure the database schema has been executed
- Check Supabase project is active and not paused

#### 2. **Groq API Error**

**Error**: `Invalid API key` or `Rate limit exceeded`

**Solution**:
- Verify your `GROQ_API_KEY` in `.env`
- Check you haven't exceeded Groq's free tier limits
- Wait a few minutes if rate limited

#### 3. **WebSocket Connection Failed**

**Error**: Browser console shows WebSocket connection error

**Solution**:
- Ensure the server is running (`uvicorn proj:app --reload`)
- Check firewall isn't blocking port 8001
- Try accessing from `http://localhost:8001` instead of `127.0.0.1`

#### 4. **Import Errors**

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt
```

#### 5. **Session Summary Not Generating**

**Issue**: Session ends but summary page shows "No summary available"

**Solution**:
- Check server logs for errors during `finalize_session`
- Verify AI model is accessible
- Try manually regenerating: `POST /api/session/{session_id}/regenerate-summary`



## 📊 Performance Considerations

- **Database Queries**: Indexed on `session_id` for fast lookups
- **Message History**: Limited to 20 most recent messages to prevent context overflow
- **Streaming**: Token-by-token streaming reduces perceived latency
- **Connection Pooling**: Supabase client handles connection pooling automatically

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [Groq API Documentation](https://console.groq.com/docs)
- [WebSocket Protocol](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [LangChain Documentation](https://python.langchain.com/)

---


---

## 👨‍💻 Author

Created as an AI-powered chat application assignment demonstrating real-time WebSocket communication, LLM integration, and database persistence.

---

## 🙋 Support

If you encounter issues:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review server logs for error messages
3. Verify all environment variables are correctly set
4. Test database connection with `python tests/check_database.py`

---

**Happy Chatting! 🎉**
