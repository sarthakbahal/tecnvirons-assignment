from dotenv import load_dotenv
import os
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from supabase import create_client, Client
from langchain_groq import ChatGroq
from datetime import datetime
import json

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)


app = FastAPI()

model = ChatGroq(
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    temperature=0,
    max_tokens=None,
    max_retries=2
)

# ============================================================
# TOOL DEFINITIONS - These are functions the AI can call
# ============================================================

# Define available tools that the AI can use
TOOLS = [
    {
        "name": "get_session_stats",
        "description": "Retrieves statistics about the current chat session including message count, start time, and duration. Use this when user asks about their activity, message count, or session information.",
        "parameters": {
            "session_id": {
                "type": "string",
                "description": "The current session ID"
            }
        }
    },
    {
        "name": "search_chat_history",
        "description": "Searches through previous messages in the current session for specific keywords or topics. Use this when user asks 'what did we discuss about X' or 'did I mention Y'.",
        "parameters": {
            "session_id": {
                "type": "string",
                "description": "The current session ID"
            },
            "keyword": {
                "type": "string",
                "description": "The keyword or topic to search for"
            }
        }
    },
    {
        "name": "get_all_sessions",
        "description": "Gets a list of all previous chat sessions. Use when user asks about their chat history or previous conversations.",
        "parameters": {}
    }
]

# ============================================================
# SYSTEM PROMPTS FOR DIFFERENT INTENTS (Multi-Step Routing)
# ============================================================

# Default conversational assistant
CASUAL_CHAT_PROMPT = """You are a friendly and helpful AI assistant. When responding:
- Write in clear, well-structured paragraphs
- Use markdown formatting for better readability
- Keep responses warm and conversational
- Break up long responses into multiple paragraphs
- Be engaging and personable"""

# Technical support specialist
TECHNICAL_SUPPORT_PROMPT = """You are a technical support specialist. When responding:
- Be systematic and methodical in troubleshooting
- Ask clarifying questions to understand the issue
- Provide step-by-step solutions
- Use clear, numbered instructions
- Offer to help with follow-up questions
- Use code blocks for technical examples"""

# Code assistant for programming questions
CODE_ASSISTANT_PROMPT = """You are an expert programming assistant. When responding:
- Provide clear, well-commented code examples
- Explain the logic behind your solutions
- Use proper markdown with code blocks (```language)
- Suggest best practices and optimizations
- Point out potential issues or edge cases
- Be precise and technical"""

# Tutorial/Teaching mode
TUTORIAL_PROMPT = """You are a patient teacher and tutor. When responding:
- Break down complex concepts into simple steps
- Use analogies and real-world examples
- Check for understanding by asking questions
- Provide clear explanations with examples
- Start with basics before advancing
- Encourage learning and experimentation"""

# System prompt to ensure proper formatting (Default)
SYSTEM_PROMPT = CASUAL_CHAT_PROMPT

# ============================================================
# TOOL EXECUTION FUNCTIONS
# ============================================================

async def execute_tool(tool_name: str, parameters: dict) -> dict:
    """
    Execute a tool based on its name and parameters.
    This is called when the AI decides it needs to use a tool.
    
    Args:
        tool_name: Name of the tool to execute
        parameters: Dictionary of parameters for the tool
        
    Returns:
        Dictionary with the tool's result
    """
    print(f"[TOOL] Executing tool: {tool_name} with params: {parameters}")
    
    try:
        if tool_name == "get_session_stats":
            return await get_session_stats(parameters.get("session_id"))
        
        elif tool_name == "search_chat_history":
            return await search_chat_history(
                parameters.get("session_id"),
                parameters.get("keyword")
            )
        
        elif tool_name == "get_all_sessions":
            return await get_all_sessions()
        
        else:
            return {"error": f"Unknown tool: {tool_name}"}
            
    except Exception as e:
        print(f"[TOOL] Error executing {tool_name}: {e}")
        return {"error": str(e)}


async def get_session_stats(session_id: str) -> dict:
    """
    Tool Function: Get statistics about the current session.
    
    Returns message counts, duration, start time, etc.
    """
    try:
        # Get session info
        session = supabase.from_("sessions").select("*").eq("session_id", session_id).execute()
        
        if not session.data:
            return {"error": "Session not found"}
        
        session_data = session.data[0]
        
        # Count messages
        logs = supabase.from_("session_logs").select("*").eq("session_id", session_id).execute()
        
        user_messages = [log for log in logs.data if log['event_type'] == 'user']
        ai_messages = [log for log in logs.data if log['event_type'] == 'ai']
        
        # Calculate duration - handle timezone-aware and timezone-naive datetimes
        try:
            start_time = datetime.fromisoformat(session_data['start_time'].replace('Z', '+00:00'))
            # Make sure both datetimes are timezone-aware
            if start_time.tzinfo is None:
                # If start_time is naive, make current time naive too
                current_time = datetime.utcnow()
            else:
                # If start_time is aware, make current time aware too
                from datetime import timezone
                current_time = datetime.now(timezone.utc)
            
            duration_minutes = (current_time - start_time).total_seconds() / 60
        except Exception as date_error:
            print(f"[TOOL] Date calculation error: {date_error}")
            duration_minutes = 0  # Default to 0 if calculation fails
        
        return {
            "session_id": session_id,
            "start_time": session_data['start_time'],
            "duration_minutes": round(duration_minutes, 2),
            "total_messages": len(logs.data),
            "user_messages": len(user_messages),
            "ai_messages": len(ai_messages),
            "status": session_data.get('status', 'active')
        }
    except Exception as e:
        return {"error": str(e)}


async def search_chat_history(session_id: str, keyword: str) -> dict:
    """
    Tool Function: Search through chat history for a keyword.
    
    Returns messages containing the keyword.
    """
    try:
        # Get all messages from session
        logs = supabase.from_("session_logs").select("*").eq("session_id", session_id).execute()
        
        if not logs.data:
            return {"found": False, "message": "No messages in this session yet"}
        
        # Search for keyword (case-insensitive)
        matching_messages = []
        for log in logs.data:
            if keyword.lower() in log['message'].lower():
                matching_messages.append({
                    "type": log['event_type'],
                    "message": log['message'],
                    "id": log['id']
                })
        
        if matching_messages:
            return {
                "found": True,
                "keyword": keyword,
                "matches": len(matching_messages),
                "messages": matching_messages[:5]  # Return top 5 matches
            }
        else:
            return {
                "found": False,
                "keyword": keyword,
                "message": f"No messages found containing '{keyword}'"
            }
    except Exception as e:
        return {"error": str(e)}


async def get_all_sessions() -> dict:
    """
    Tool Function: Get list of all previous sessions.
    
    Returns recent sessions with basic info.
    """
    try:
        # Get recent sessions (last 10)
        sessions = supabase.from_("sessions").select("*").order("start_time", desc=True).limit(10).execute()
        
        if not sessions.data:
            return {"message": "No previous sessions found"}
        
        session_list = []
        for session in sessions.data:
            session_list.append({
                "session_id": session['session_id'],
                "start_time": session['start_time'],
                "status": session.get('status', 'unknown'),
                "summary": session.get('summary', 'No summary available')[:100]  # First 100 chars
            })
        
        return {
            "total_sessions": len(session_list),
            "sessions": session_list
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# INTENT DETECTION (Multi-Step Routing)
# ============================================================

def detect_intent(message: str) -> str:
    """
    Detect the user's intent from their message.
    This determines which system prompt to use.
    
    Returns one of: 'technical_support', 'code_assistant', 'tutorial', 'casual_chat'
    """
    message_lower = message.lower()
    
    # Technical Support keywords
    technical_keywords = ['error', 'bug', 'not working', 'broken', 'issue', 'problem', 
                         'fix', 'help', 'troubleshoot', 'debug', "doesn't work", 'failing']
    
    # Code Assistant keywords
    code_keywords = ['code', 'function', 'python', 'javascript', 'programming', 
                    'algorithm', 'syntax', 'class', 'variable', 'loop', 'api',
                    'write a', 'create a function', 'how to code']
    
    # Tutorial keywords
    tutorial_keywords = ['how to', 'teach me', 'explain', 'what is', 'tutorial',
                        'learn', 'understand', 'show me how', 'step by step',
                        'can you explain', 'help me understand']
    
    # Check for technical support intent
    if any(keyword in message_lower for keyword in technical_keywords):
        return 'technical_support'
    
    # Check for code assistant intent
    if any(keyword in message_lower for keyword in code_keywords):
        return 'code_assistant'
    
    # Check for tutorial intent
    if any(keyword in message_lower for keyword in tutorial_keywords):
        return 'tutorial'
    
    # Default to casual chat
    return 'casual_chat'


def get_system_prompt_for_intent(intent: str) -> str:
    """
    Get the appropriate system prompt based on detected intent.
    """
    prompts = {
        'technical_support': TECHNICAL_SUPPORT_PROMPT,
        'code_assistant': CODE_ASSISTANT_PROMPT,
        'tutorial': TUTORIAL_PROMPT,
        'casual_chat': CASUAL_CHAT_PROMPT
    }
    
    return prompts.get(intent, CASUAL_CHAT_PROMPT)

# ============================================================
# TOOL DETECTION & PARAMETER EXTRACTION
# ============================================================

def should_use_tool(message: str, session_id: str) -> tuple:
    """
    Determine if a tool should be used based on the user's message.
    
    Returns: (should_use: bool, tool_name: str, parameters: dict)
    """
    message_lower = message.lower()
    
    # Check for session stats queries
    stats_keywords = ['how many messages', 'message count', 'how long', 'duration',
                     'session stats', 'my activity', 'how many times']
    if any(keyword in message_lower for keyword in stats_keywords):
        return (True, "get_session_stats", {"session_id": session_id})
    
    # Check for history search queries
    history_keywords = ['did i mention', 'what did we discuss', 'did we talk about',
                       'search for', 'find in history', 'previous conversation']
    if any(keyword in message_lower for keyword in history_keywords):
        # Try to extract keyword (simple approach)
        keyword = extract_search_keyword(message)
        return (True, "search_chat_history", {"session_id": session_id, "keyword": keyword})
    
    # Check for session list queries
    session_list_keywords = ['my previous chats', 'chat history', 'all sessions',
                            'past conversations', 'show my sessions']
    if any(keyword in message_lower for keyword in session_list_keywords):
        return (True, "get_all_sessions", {})
    
    # No tool needed
    return (False, None, None)


def extract_search_keyword(message: str) -> str:
    """
    Simple keyword extraction from search queries.
    Looks for words after 'about', 'for', 'mention' etc.
    """
    message_lower = message.lower()
    
    # Common patterns: "what did we discuss about X", "did I mention Y"
    patterns = [
        'about ', 'mention ', 'discuss ', 'talk about ', 'said about ',
        'for ', 'regarding '
    ]
    
    for pattern in patterns:
        if pattern in message_lower:
            # Extract text after the pattern
            parts = message_lower.split(pattern, 1)
            if len(parts) > 1:
                # Get first few words after pattern
                keyword = parts[1].strip().split()[0] if parts[1].strip() else "unknown"
                return keyword.strip('?,.')
    
    # Default: use last word of message
    words = message.split()
    return words[-1].strip('?,.') if words else "unknown"

# Helper function to generate session summary
async def generate_session_summary(session_id: str) -> dict:
    """
    Generate a comprehensive summary of the chat session using AI.
    """
    try:
        print(f"[SUMMARY] Starting summary generation for session: {session_id}")
        
        # Fetch all messages from the session (order by id if created_at doesn't exist)
        try:
            logs = supabase.from_("session_logs").select("*").eq("session_id", session_id).order("id").execute()
        except Exception as e:
            print(f"[SUMMARY] Error ordering by id, trying without order: {e}")
            logs = supabase.from_("session_logs").select("*").eq("session_id", session_id).execute()
        
        print(f"[SUMMARY] Found {len(logs.data) if logs.data else 0} log entries")
        
        if not logs.data or len(logs.data) == 0:
            print(f"[SUMMARY] No messages found in session")
            return {"summary": "No messages in session", "topics": [], "sentiment": "neutral", "metrics": {}}
        
        # Build conversation history
        conversation = []
        user_messages = []
        ai_messages = []
        
        for log in logs.data:
            if log['event_type'] == 'user':
                conversation.append(f"User: {log['message']}")
                user_messages.append(log['message'])
            elif log['event_type'] == 'ai':
                conversation.append(f"AI: {log['message']}")
                ai_messages.append(log['message'])
        
        print(f"[SUMMARY] User messages: {len(user_messages)}, AI messages: {len(ai_messages)}")
        
        conversation_text = "\n".join(conversation)
        
        # Generate summary using AI
        summary_prompt = f"""Analyze the following conversation and provide a professional summary.

Conversation:
{conversation_text}

Create a comprehensive analysis with:
1. A clear, readable summary (3-4 sentences describing what was discussed and accomplished)
2. Main topics discussed (3-5 key topics as a simple array)
3. Overall sentiment (choose one: positive, neutral, or negative)
4. Key outcomes or conclusions (1-2 sentences about what was learned or achieved)

IMPORTANT: Respond with ONLY valid JSON. No markdown, no code blocks, no extra text. Just the raw JSON object.

Example format:
{{
  "summary": "The user asked about Python programming concepts. We discussed variables, data types, and control structures. The conversation covered practical examples and best practices for beginners.",
  "topics": ["Python basics", "Variables", "Data types", "Control structures"],
  "sentiment": "positive",
  "key_outcomes": "User gained understanding of fundamental Python concepts and received code examples for practice."
}}"""

        print(f"[SUMMARY] Calling AI for analysis...")
        summary_response = model.invoke([("human", summary_prompt)])
        print(f"[SUMMARY] AI response received: {summary_response.content[:100]}...")
        
        # Parse AI response
        try:
            summary_data = json.loads(summary_response.content)
            print(f"[SUMMARY] Successfully parsed JSON response")
        except json.JSONDecodeError as je:
            print(f"[SUMMARY] Failed to parse JSON: {je}")
            # Fallback if AI doesn't return valid JSON
            summary_data = {
                "summary": summary_response.content[:200] if len(summary_response.content) > 0 else "Conversation completed",
                "topics": ["General conversation"],
                "sentiment": "neutral",
                "key_outcomes": "Session completed"
            }
            print(f"[SUMMARY] Using fallback summary data")
        
        # Calculate metrics
        metrics = {
            "total_messages": len(logs.data),
            "user_messages": len(user_messages),
            "ai_messages": len(ai_messages),
            "total_user_words": sum(len(msg.split()) for msg in user_messages),
            "total_ai_words": sum(len(msg.split()) for msg in ai_messages),
        }
        
        return {
            **summary_data,
            "metrics": metrics
        }
        
    except Exception as e:
        print(f"[SUMMARY] ERROR generating session summary: {e}")
        import traceback
        print(f"[SUMMARY] Traceback: {traceback.format_exc()}")
        return {
            "summary": f"Error generating summary: {str(e)}",
            "topics": [],
            "sentiment": "neutral",
            "metrics": {}
        }

# Helper function to update session with end time and summary
async def finalize_session(session_id: str):
    """
    Finalize the session by generating summary and updating the database.
    """
    try:
        print(f"[FINALIZE] ============================================")
        print(f"[FINALIZE] Starting finalization for session: {session_id}")
        print(f"[FINALIZE] ============================================")
        
        # Generate comprehensive summary
        session_analysis = await generate_session_summary(session_id)
        
        print(f"[FINALIZE] Summary generated: {session_analysis.get('summary', 'N/A')[:100]}...")
        
        # Update session record with end time and summary
        update_data = {
            "end_time": datetime.utcnow().isoformat(),
            "summary": session_analysis.get("summary", ""),
            "topics": json.dumps(session_analysis.get("topics", [])),
            "sentiment": session_analysis.get("sentiment", "neutral"),
            "metrics": json.dumps(session_analysis.get("metrics", {})),
            "status": "completed"
        }
        
        print(f"[FINALIZE] Updating database with summary data...")
        result = supabase.from_("sessions").update(update_data).eq("session_id", session_id).execute()
        print(f"[FINALIZE] Database updated. Rows affected: {len(result.data) if result.data else 0}")
        
        print(f"[FINALIZE] ✅ Session {session_id[:8]}... finalized successfully")
        print(f"[FINALIZE] ============================================")
        
        return session_analysis
        
    except Exception as e:
        print(f"[FINALIZE] ❌ ERROR finalizing session {session_id}: {e}")
        import traceback
        print(f"[FINALIZE] Traceback: {traceback.format_exc()}")
        # Try to at least update the end time
        try:
            supabase.from_("sessions").update({
                "end_time": datetime.utcnow().isoformat(),
                "status": "completed_with_errors"
            }).eq("session_id", session_id).execute()
            print(f"[FINALIZE] Updated end_time with error status")
        except Exception as e2:
            print(f"[FINALIZE] Failed to update end_time: {e2}")

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1 {
                color: #333;
                border-bottom: 2px solid #007bff;
                padding-bottom: 10px;
            }
            #chatContainer {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                padding: 20px;
                margin-bottom: 20px;
                max-height: 600px;
                overflow-y: auto;
            }
            .message {
                margin-bottom: 20px;
                padding: 12px;
                border-radius: 8px;
                line-height: 1.6;
            }
            .user-message {
                background-color: #e3f2fd;
                border-left: 4px solid #2196f3;
            }
            .ai-message {
                background-color: #f5f5f5;
                border-left: 4px solid #4caf50;
            }
            .system-message {
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                font-style: italic;
            }
            .message-content {
                margin: 0;
            }
            .message-content h2, .message-content h3 {
                margin-top: 10px;
                margin-bottom: 8px;
            }
            .message-content p {
                margin: 8px 0;
            }
            .message-content ul, .message-content ol {
                margin: 8px 0;
                padding-left: 20px;
            }
            .message-content code {
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }
            .message-content pre {
                background: #f4f4f4;
                padding: 12px;
                border-radius: 6px;
                overflow-x: auto;
            }
            .message-content pre code {
                background: none;
                padding: 0;
            }
            form {
                display: flex;
                gap: 10px;
                margin-top: 20px;
            }
            #messageText {
                flex: 1;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 6px;
                font-size: 16px;
            }
            #messageText:focus {
                outline: none;
                border-color: #007bff;
            }
            button {
                padding: 12px 24px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 16px;
                font-weight: 500;
            }
            button:hover {
                background-color: #0056b3;
            }
            button:disabled {
                background-color: #ccc;
                cursor: not-allowed;
            }
            /* Intent Mode Badge Styles */
            .intent-badge {
                display: inline-block;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 600;
                margin-bottom: 10px;
                animation: slideIn 0.3s ease-out;
            }
            .intent-technical {
                background-color: #ff6b6b;
                color: white;
            }
            .intent-code {
                background-color: #4ecdc4;
                color: white;
            }
            .intent-tutorial {
                background-color: #95e1d3;
                color: #333;
            }
            .intent-chat {
                background-color: #a8dadc;
                color: #333;
            }
            .tool-indicator {
                background-color: #ffd93d;
                color: #333;
                padding: 8px 15px;
                border-radius: 6px;
                margin: 10px 0;
                font-size: 14px;
                display: flex;
                align-items: center;
                gap: 8px;
                animation: fadeIn 0.5s ease-in;
            }
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(-10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
        </style>
    </head>
    <body>
        <h1>💬 WebSocket Chat</h1>
        <div id="sessionInfo" style="background: #f0f0f0; padding: 10px; border-radius: 6px; margin-bottom: 15px; font-size: 14px; display: none;">
            <strong>Session ID:</strong> <span id="sessionIdDisplay"></span>
            <a id="summaryLink" href="#" style="margin-left: 15px; color: #667eea; text-decoration: none; font-weight: 500;">📊 View Summary</a>
        </div>
        <div id="chatContainer"></div>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off" placeholder="Type your message here..."/>
            <button id="sendButton">Send</button>
            <button type="button" id="endSessionButton" style="background-color: #dc3545; margin-left: 10px;">End Session</button>
        </form>
        <script>
            // Generate a proper UUID v4
            function generateUUID() {
                return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                    return v.toString(16);
                });
            }
            
            // Get or create session ID
            var sessionId = sessionStorage.getItem('sessionId');
            if (!sessionId) {
                sessionId = generateUUID();
                sessionStorage.setItem('sessionId', sessionId);
            }
            
            var currentAIMessage = null;
            var currentAIContent = '';
            
            // Use window.location.host to automatically use the correct port
            var wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            var ws = new WebSocket(wsProtocol + "//" + window.location.host + "/ws/session/" + sessionId);
            var chatContainer = document.getElementById('chatContainer');
            var sendButton = document.getElementById('sendButton');
            
            function addMessage(content, type) {
                var messageDiv = document.createElement('div');
                messageDiv.className = 'message ' + type + '-message';
                
                var contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                
                if (type === 'ai') {
                    // Render markdown for AI messages
                    contentDiv.innerHTML = marked.parse(content);
                } else {
                    contentDiv.textContent = content;
                }
                
                messageDiv.appendChild(contentDiv);
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
                
                return messageDiv;
            }
            
            function addIntentBadge(intentText) {
                var badgeDiv = document.createElement('div');
                var intentClass = 'intent-chat'; // default
                
                if (intentText.includes('Technical Support')) {
                    intentClass = 'intent-technical';
                } else if (intentText.includes('Code Assistant')) {
                    intentClass = 'intent-code';
                } else if (intentText.includes('Tutorial')) {
                    intentClass = 'intent-tutorial';
                }
                
                badgeDiv.className = 'intent-badge ' + intentClass;
                badgeDiv.textContent = intentText;
                chatContainer.appendChild(badgeDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            function addToolIndicator(toolText) {
                var toolDiv = document.createElement('div');
                toolDiv.className = 'tool-indicator';
                toolDiv.textContent = toolText;
                chatContainer.appendChild(toolDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            function updateAIMessage(token) {
                if (!currentAIMessage) {
                    currentAIMessage = addMessage('', 'ai');
                    currentAIContent = '';
                }
                
                currentAIContent += token;
                var contentDiv = currentAIMessage.querySelector('.message-content');
                contentDiv.innerHTML = marked.parse(currentAIContent);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            function finalizeAIMessage() {
                currentAIMessage = null;
                currentAIContent = '';
            }
            
            ws.onopen = function(event) {
                console.log('WebSocket connected');
                document.title = 'Chat - Connected';
                sendButton.disabled = false;
                addMessage('Connected! You can start chatting.', 'system');
                
                // Show session info with summary link
                document.getElementById('sessionInfo').style.display = 'block';
                document.getElementById('sessionIdDisplay').textContent = sessionId.substring(0, 8) + '...';
                document.getElementById('summaryLink').href = '/summary/' + sessionId;
            };
            
            ws.onmessage = function(event) {
                var data = event.data;
                
                // Check for intent mode badge
                if (data.includes('Mode]')) {
                    addIntentBadge(data.replace('[', '').replace(']', '').trim());
                    return;
                }
                
                // Check for tool indicators
                if (data.includes('🔍 Fetching data') || data.includes('✅ Data retrieved')) {
                    addToolIndicator(data);
                    return;
                }
                
                // Check if it's an acknowledgment message
                if (data.startsWith('Message received:')) {
                    // Finalize any previous AI message
                    if (currentAIMessage) {
                        finalizeAIMessage();
                    }
                    return; // Don't display acknowledgment
                }
                
                // It's AI response token - accumulate and render
                updateAIMessage(data);
            };
            
            ws.onclose = function(event) {
                console.log('WebSocket disconnected');
                document.title = 'Chat - Disconnected';
                sendButton.disabled = true;
                
                if (currentAIMessage) {
                    finalizeAIMessage();
                }
                
                addMessage('Session ended. Generating summary...', 'system');
                
                // Fetch and display brief summary
                setTimeout(function() {
                    fetch('/api/session/' + sessionId + '/summary')
                        .then(response => response.json())
                        .then(data => {
                            if (data.summary) {
                                var brief = '## Session Summary\\n\\n' + data.summary;
                                if (data.topics && data.topics.length > 0) {
                                    brief += '\\n\\n**Topics:** ' + data.topics.join(', ');
                                }
                                if (data.metrics && data.metrics.total_messages) {
                                    brief += '\\n\\n**Messages:** ' + data.metrics.total_messages;
                                }
                                brief += '\\n\\n[View Full Summary](/summary/' + sessionId + ') | [Start New Chat](/)';
                                addMessage(brief, 'system');
                            } else {
                                addMessage('Session ended. [View Summary](/summary/' + sessionId + ') | [Start New Chat](/)', 'system');
                            }
                        })
                        .catch(function() {
                            addMessage('Session ended. Thank you for chatting!', 'system');
                        });
                }, 3000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                sendButton.disabled = true;
            };
            
            function sendMessage(event) {
                event.preventDefault();
                var input = document.getElementById("messageText");
                var message = input.value.trim();
                
                if (!message) return;
                
                if (ws.readyState === WebSocket.OPEN) {
                    // Display user message
                    addMessage(message, 'user');
                    
                    // Send to server
                    ws.send(message);
                    input.value = '';
                    
                    // Finalize any previous AI message before new one
                    if (currentAIMessage) {
                        finalizeAIMessage();
                    }
                } else {
                    alert('Connection is not open. Please refresh the page.');
                }
            }
            
            // End Session button handler
            document.getElementById('endSessionButton').addEventListener('click', function() {
                if (confirm('End this session and generate summary?')) {
                    console.log('User clicked End Session - closing WebSocket');
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.close();
                        console.log('WebSocket close() called');
                    }
                }
            });
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.get("/summary/{session_id}")
async def get_summary_page(session_id: str):
    """
    Display a formatted summary page for a completed session
    """
    summary_html = f"""
<!DOCTYPE html>
<html>
    <head>
        <title>Session Summary - {session_id[:8]}</title>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f7fa;
                min-height: 100vh;
                line-height: 1.6;
            }}
            .container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 2px 12px rgba(0,0,0,0.08);
                padding: 40px;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #1a202c;
                font-size: 28px;
                font-weight: 700;
                margin-bottom: 10px;
                margin-top: 0;
            }}
            .subtitle {{
                color: #718096;
                font-size: 14px;
                margin-bottom: 30px;
            }}
            .loading {{
                text-align: center;
                padding: 60px 40px;
                color: #718096;
                font-size: 16px;
            }}
            .loading::after {{
                content: '...';
                animation: dots 1.5s infinite;
            }}
            @keyframes dots {{
                0%, 20% {{ content: '.'; }}
                40% {{ content: '..'; }}
                60%, 100% {{ content: '...'; }}
            }}
            .error {{
                background: #fff5f5;
                border: 1px solid #fc8181;
                border-left: 4px solid #f56565;
                padding: 20px;
                border-radius: 8px;
                color: #742a2a;
            }}
            .summary-section {{
                margin-bottom: 24px;
                padding: 24px;
                background: #fafbfc;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
                transition: all 0.2s;
            }}
            .summary-section:hover {{
                border-color: #cbd5e0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            }}
            .summary-section h2 {{
                margin-top: 0;
                margin-bottom: 16px;
                color: #2d3748;
                font-size: 18px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .summary-content {{
                color: #4a5568;
                font-size: 15px;
                line-height: 1.7;
            }}
            .summary-text {{
                position: relative;
            }}
            .summary-text.collapsed {{
                max-height: 150px;
                overflow: hidden;
            }}
            .summary-text.collapsed::after {{
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 60px;
                background: linear-gradient(transparent, #fafbfc);
            }}
            .expand-btn {{
                background: none;
                border: none;
                color: #5a67d8;
                cursor: pointer;
                padding: 8px 0;
                font-size: 14px;
                font-weight: 500;
                margin-top: 8px;
                display: inline-flex;
                align-items: center;
                gap: 4px;
            }}
            .expand-btn:hover {{
                color: #4c51bf;
                text-decoration: underline;
            }}
            .stat-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                gap: 16px;
                margin-top: 16px;
            }}
            .stat-card {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
                text-align: center;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            .stat-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }}
            .stat-value {{
                font-size: 28px;
                font-weight: 700;
                color: #5a67d8;
                margin: 8px 0;
            }}
            .stat-label {{
                color: #718096;
                font-size: 13px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .topics {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 12px;
            }}
            .topic-tag {{
                background: #edf2f7;
                color: #2d3748;
                padding: 6px 14px;
                border-radius: 16px;
                font-size: 13px;
                font-weight: 500;
                border: 1px solid #e2e8f0;
            }}
            .sentiment {{
                display: inline-flex;
                align-items: center;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 14px;
                text-transform: capitalize;
            }}
            .sentiment-positive {{ background: #c6f6d5; color: #22543d; }}
            .sentiment-neutral {{ background: #bee3f8; color: #2c5282; }}
            .sentiment-negative {{ background: #fed7d7; color: #742a2a; }}
            .session-info-grid {{
                display: grid;
                gap: 12px;
                color: #4a5568;
                font-size: 14px;
            }}
            .session-info-item {{
                display: flex;
                padding: 8px 0;
                border-bottom: 1px solid #e2e8f0;
            }}
            .session-info-item:last-child {{
                border-bottom: none;
            }}
            .session-info-label {{
                font-weight: 600;
                color: #2d3748;
                min-width: 120px;
            }}
            .rating-section {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 32px;
                border-radius: 12px;
                text-align: center;
                margin-top: 32px;
            }}
            .rating-section h2 {{
                color: white;
                margin-top: 0;
                margin-bottom: 16px;
                font-size: 22px;
            }}
            .rating-section p {{
                opacity: 0.95;
                margin-bottom: 24px;
            }}
            .rating-stars {{
                display: flex;
                justify-content: center;
                gap: 12px;
                margin-bottom: 20px;
            }}
            .star {{
                font-size: 36px;
                cursor: pointer;
                transition: all 0.2s;
                filter: grayscale(100%);
                opacity: 0.5;
            }}
            .star:hover,
            .star.selected {{
                filter: grayscale(0%);
                opacity: 1;
                transform: scale(1.2);
            }}
            .rating-feedback {{
                margin-top: 16px;
                padding: 12px 20px;
                background: rgba(255,255,255,0.2);
                border-radius: 8px;
                font-weight: 500;
                display: none;
            }}
            .rating-feedback.show {{
                display: block;
                animation: fadeIn 0.3s;
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(-10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .back-link {{
                display: inline-block;
                margin-top: 24px;
                padding: 12px 32px;
                background: white;
                color: #5a67d8;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                border: 2px solid #e2e8f0;
                transition: all 0.2s;
            }}
            .back-link:hover {{
                background: #5a67d8;
                color: white;
                border-color: #5a67d8;
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(90, 103, 216, 0.3);
            }}
            .conversation {{
                margin-top: 20px;
                max-height: 400px;
                overflow-y: auto;
                background: white;
                padding: 20px;
                border-radius: 8px;
            }}
            .conv-message {{
                margin-bottom: 15px;
                padding: 10px;
                border-radius: 6px;
            }}
            .conv-user {{
                background: #e3f2fd;
                border-left: 3px solid #2196f3;
            }}
            .conv-ai {{
                background: #f5f5f5;
                border-left: 3px solid #4caf50;
            }}
            .conv-label {{
                font-weight: bold;
                font-size: 12px;
                text-transform: uppercase;
                color: #666;
                margin-bottom: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Session Complete</h1>
            <div class="subtitle">Here's a comprehensive summary of your conversation</div>
            <div id="content" class="loading">
                Loading session summary
            </div>
        </div>
        <script>
            const sessionId = '{session_id}';
            
            function formatSummary(text) {{
                // Clean up any JSON formatting
                if (!text) return '';
                
                // If it looks like JSON, try to parse it
                if (text.trim().startsWith('{{')) {{
                    try {{
                        const parsed = JSON.parse(text);
                        text = parsed.summary || parsed.text || text;
                    }} catch(e) {{
                        // Not valid JSON, use as is
                        console.log('Could not parse as JSON:', e);
                    }}
                }}
                
                // Convert to proper paragraphs
                return text
                    .replace(/\\\\n/g, '\\n')
                    .split('\\n')
                    .filter(p => p.trim())
                    .map(p => '<p>' + p.trim() + '</p>')
                    .join('');
            }}
            
            function toggleSummary() {{
                const summaryText = document.getElementById('summaryText');
                const expandBtn = document.getElementById('expandBtn');
                
                if (summaryText.classList.contains('collapsed')) {{
                    summaryText.classList.remove('collapsed');
                    expandBtn.textContent = '▼ Show less';
                }} else {{
                    summaryText.classList.add('collapsed');
                    expandBtn.textContent = '▶ Read full summary';
                }}
            }}
            
            console.log('Fetching summary for session:', sessionId);
            fetch('/api/session/' + sessionId + '/summary')
                .then(response => {{
                    console.log('Response received:', response.status);
                    return response.json();
                }})
                .then(data => {{
                    console.log('Summary data:', data);
                    if (data.error) {{
                        console.error('Error in response:', data.error);
                        document.getElementById('content').innerHTML = 
                            '<div class="error">❌ ' + data.error + '</div>' +
                            '<a href="/" class="back-link">← Back to Chat</a>';
                        return;
                    }}
                    
                    let html = '';
                    
                    // Summary section with expand/collapse
                    if (data.summary) {{
                        const formattedSummary = formatSummary(data.summary);
                        const needsExpand = data.summary.length > 300;
                        
                        html += '<div class="summary-section">';
                        html += '<h2>💬 Conversation Summary</h2>';
                        html += '<div id="summaryText" class="summary-text summary-content ' + (needsExpand ? 'collapsed' : '') + '">';
                        html += formattedSummary;
                        html += '</div>';
                        
                        if (needsExpand) {{
                            html += '<button class="expand-btn" id="expandBtn" onclick="toggleSummary()">▶ Read full summary</button>';
                        }}
                        
                        html += '</div>';
                    }}
                    
                    // Topics section
                    if (data.topics && data.topics.length > 0) {{
                        html += '<div class="summary-section">';
                        html += '<h2>🏷️ Key Topics</h2>';
                        html += '<div class="topics">';
                        data.topics.forEach(topic => {{
                            html += '<span class="topic-tag">' + topic + '</span>';
                        }});
                        html += '</div></div>';
                    }}
                    
                    // Key outcomes section
                    if (data.key_outcomes) {{
                        html += '<div class="summary-section">';
                        html += '<h2>✨ Key Outcomes</h2>';
                        html += '<div class="summary-content">';
                        html += '<p>' + data.key_outcomes + '</p>';
                        html += '</div></div>';
                    }}
                    
                    // Sentiment section
                    if (data.sentiment) {{
                        html += '<div class="summary-section">';
                        html += '<h2>� Overall Sentiment</h2>';
                        const sentimentEmoji = {{
                            'positive': '😊',
                            'neutral': '😐',
                            'negative': '😟'
                        }};
                        const sentimentClass = 'sentiment sentiment-' + data.sentiment;
                        html += '<span class="' + sentimentClass + '">';
                        html += (sentimentEmoji[data.sentiment] || '') + ' ' + data.sentiment;
                        html += '</span>';
                        html += '</div>';
                    }}
                    
                    // Stats section
                    if (data.metrics) {{
                        html += '<div class="summary-section">';
                        html += '<h2>� Session Statistics</h2>';
                        html += '<div class="stat-grid">';
                        
                        if (data.metrics.total_messages) {{
                            html += '<div class="stat-card">';
                            html += '<div class="stat-label">Total Messages</div>';
                            html += '<div class="stat-value">' + data.metrics.total_messages + '</div>';
                            html += '</div>';
                        }}
                        
                        if (data.metrics.user_messages) {{
                            html += '<div class="stat-card">';
                            html += '<div class="stat-label">Your Messages</div>';
                            html += '<div class="stat-value">' + data.metrics.user_messages + '</div>';
                            html += '</div>';
                        }}
                        
                        if (data.metrics.ai_messages) {{
                            html += '<div class="stat-card">';
                            html += '<div class="stat-label">AI Responses</div>';
                            html += '<div class="stat-value">' + data.metrics.ai_messages + '</div>';
                            html += '</div>';
                        }}
                        
                        if (data.metrics.total_user_words) {{
                            html += '<div class="stat-card">';
                            html += '<div class="stat-label">Words Spoken</div>';
                            html += '<div class="stat-value">' + data.metrics.total_user_words + '</div>';
                            html += '</div>';
                        }}
                        
                        html += '</div></div>';
                    }}
                    
                    // Session info
                    html += '<div class="summary-section">';
                    html += '<h2>ℹ️ Session Details</h2>';
                    html += '<div class="session-info-grid">';
                    
                    html += '<div class="session-info-item">';
                    html += '<span class="session-info-label">Session ID</span>';
                    html += '<span>' + sessionId.substring(0, 13) + '...</span>';
                    html += '</div>';
                    
                    html += '<div class="session-info-item">';
                    html += '<span class="session-info-label">Status</span>';
                    html += '<span>' + (data.status || 'Completed').charAt(0).toUpperCase() + (data.status || 'Completed').slice(1) + '</span>';
                    html += '</div>';
                    
                    if (data.start_time) {{
                        html += '<div class="session-info-item">';
                        html += '<span class="session-info-label">Started At</span>';
                        html += '<span>' + new Date(data.start_time).toLocaleString() + '</span>';
                        html += '</div>';
                    }}
                    
                    if (data.end_time) {{
                        html += '<div class="session-info-item">';
                        html += '<span class="session-info-label">Ended At</span>';
                        html += '<span>' + new Date(data.end_time).toLocaleString() + '</span>';
                        html += '</div>';
                    }}
                    
                    // Calculate duration
                    if (data.start_time && data.end_time) {{
                        const duration = Math.floor((new Date(data.end_time) - new Date(data.start_time)) / 60000);
                        html += '<div class="session-info-item">';
                        html += '<span class="session-info-label">Duration</span>';
                        html += '<span>' + duration + ' minutes</span>';
                        html += '</div>';
                    }}
                    
                    html += '</div></div>';
                    
                    // Add back link
                    html += '<div style="text-align: center; margin-top: 40px;">';
                    html += '<a href="/" class="back-link">← Start New Chat</a>';
                    html += '</div>';
                    
                    document.getElementById('content').innerHTML = html;
                }})
                .catch(error => {{
                    console.error('Fetch error:', error);
                    document.getElementById('content').innerHTML = 
                        '<div class="error">❌ Failed to load summary: ' + error + '</div>' +
                        '<p>Please check the console for more details.</p>' +
                        '<a href="/" class="back-link">← Back to Chat</a>';
                }});
        </script>
    </body>
</html>
"""
    return HTMLResponse(summary_html)

@app.get("/api/session/{session_id}/summary")
async def get_session_summary(session_id: str):
    """
    Get the summary of a completed session.
    """
    try:
        session = supabase.from_("sessions").select("*").eq("session_id", session_id).execute()
        
        if not session.data:
            return {"error": "Session not found"}
        
        session_data = session.data[0]
        
        # Parse JSON fields if they exist
        if session_data.get('topics'):
            try:
                session_data['topics'] = json.loads(session_data['topics'])
            except:
                pass
        
        if session_data.get('metrics'):
            try:
                session_data['metrics'] = json.loads(session_data['metrics'])
            except:
                pass
        
        return {
            "session_id": session_id,
            "status": session_data.get('status'),
            "start_time": session_data.get('start_time'),
            "end_time": session_data.get('end_time'),
            "summary": session_data.get('summary'),
            "topics": session_data.get('topics', []),
            "sentiment": session_data.get('sentiment'),
            "metrics": session_data.get('metrics', {}),
            "key_outcomes": session_data.get('key_outcomes', '')
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/session/{session_id}/rate")
async def rate_session(session_id: str, rating_data: dict):
    """
    Save user rating for a session.
    """
    try:
        rating = rating_data.get('rating', 0)
        
        if rating < 1 or rating > 5:
            return {"error": "Rating must be between 1 and 5"}
        
        # Update session with rating
        result = supabase.from_("sessions").update({
            "user_rating": rating,
            "rated_at": datetime.utcnow().isoformat()
        }).eq("session_id", session_id).execute()
        
        return {
            "success": True,
            "session_id": session_id,
            "rating": rating,
            "message": "Thank you for your feedback!"
        }
    except Exception as e:
        print(f"Error saving rating: {e}")
        return {"error": str(e), "success": False}

@app.get("/api/sessions")
async def list_sessions():
    """
    List all sessions with their summaries.
    """
    try:
        sessions = supabase.from_("sessions").select("*").order("start_time", desc=True).limit(50).execute()
        
        result = []
        for session in sessions.data:
            # Parse JSON fields
            topics = session.get('topics')
            if topics:
                try:
                    topics = json.loads(topics)
                except:
                    topics = []
            
            metrics = session.get('metrics')
            if metrics:
                try:
                    metrics = json.loads(metrics)
                except:
                    metrics = {}
            
            result.append({
                "session_id": session.get('session_id'),
                "status": session.get('status'),
                "start_time": session.get('start_time'),
                "end_time": session.get('end_time'),
                "summary": session.get('summary', '')[:100] + '...' if session.get('summary') else None,
                "topics": topics,
                "sentiment": session.get('sentiment'),
                "message_count": metrics.get('total_messages', 0) if metrics else 0
            })
        
        return {"sessions": result, "count": len(result)}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/session/{session_id}/regenerate-summary")
async def regenerate_summary(session_id: str):
    """
    Manually trigger summary regeneration for a session.
    Useful for testing and reprocessing sessions.
    """
    try:
        # Check if session exists
        session = supabase.from_("sessions").select("*").eq("session_id", session_id).execute()
        
        if not session.data:
            return {"error": "Session not found"}
        
        # Generate new summary
        summary_result = await generate_session_summary(session_id)
        
        # Update session
        update_data = {
            "summary": summary_result.get("summary", ""),
            "topics": json.dumps(summary_result.get("topics", [])),
            "sentiment": summary_result.get("sentiment", "neutral"),
            "metrics": json.dumps(summary_result.get("metrics", {})),
        }
        
        supabase.from_("sessions").update(update_data).eq("session_id", session_id).execute()
        
        return {
            "success": True,
            "session_id": session_id,
            "summary": summary_result
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
async def health_check():
    """
    Health check endpoint for deployment verification.
    """
    try:
        # Test database connection
        test_query = supabase.from_("sessions").select("session_id").limit(1).execute()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "running",
        "database": db_status,
        "model": "llama-3.1-8b-instant",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.websocket("/ws/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    # Check if session exists, if not create it - MUST succeed before proceeding
    session_ready = False
    try:
        existing_session = supabase.from_("sessions").select("*").eq("session_id", session_id).execute()
        if not existing_session.data:
            # Create new session
            result = supabase.from_("sessions").insert([{
                "session_id": session_id,
                "user_id": "placeholder_user",
                "status": "active",
                "start_time": datetime.utcnow().isoformat()
            }]).execute()
            print(f"New session created: {session_id}")
            session_ready = True
        else:
            # Update session to active if reconnecting
            supabase.from_("sessions").update({
                "status": "active"
            }).eq("session_id", session_id).execute()
            print(f"Session reconnected: {session_id}")
            session_ready = True
    except Exception as e:
        print(f"Error checking/creating session: {e}")
        await websocket.send_text(f"Error: Could not initialize session. {str(e)}")
        await websocket.close()
        return
    
    # Only proceed if session was successfully initialized
    if not session_ready:
        print(f"Session not ready, closing connection")
        return
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # Log user message
            try:
                supabase.from_("session_logs").insert([{
                    "session_id": session_id,
                    "event_type": "user",
                    "message": data
                }]).execute()
            except Exception as e:
                print(f"Error logging user message: {e}")
                print(f"Session ID: {session_id}, Message: {data[:50]}")
            
            # ============================================================
            # STEP 1: DETECT INTENT (Multi-Step Routing)
            # ============================================================
            intent = detect_intent(data)
            selected_prompt = get_system_prompt_for_intent(intent)
            print(f"[INTENT] Detected intent: {intent}")
            
            # Send intent notification to user (optional, for demo purposes)
            intent_names = {
                'technical_support': '🔧 Technical Support Mode',
                'code_assistant': '💻 Code Assistant Mode',
                'tutorial': '📚 Tutorial Mode',
                'casual_chat': '💬 Chat Mode'
            }
            await websocket.send_text(f"[{intent_names.get(intent, 'Chat')}]\n")
            
            # ============================================================
            # STEP 2: CHECK IF TOOL IS NEEDED (Function Calling)
            # ============================================================
            should_use, tool_name, tool_params = should_use_tool(data, session_id)
            
            tool_result = None
            if should_use:
                print(f"[TOOL] Tool needed: {tool_name}")
                await websocket.send_text(f"🔍 Fetching data using {tool_name}...\n")
                
                # Execute the tool
                tool_result = await execute_tool(tool_name, tool_params)
                print(f"[TOOL] Tool result: {tool_result}")
                
                # Send tool result to user (optional, for transparency)
                await websocket.send_text(f"✅ Data retrieved successfully!\n\n")
            
            # ============================================================
            # STEP 3: FETCH CONVERSATION HISTORY (Memory)
            # ============================================================
            print(f"[MEMORY] Fetching conversation history for session: {session_id}")
            try:
                # Get previous messages from this session
                # Limit to last 20 messages (10 exchanges) to prevent context overflow
                history = supabase.from_("session_logs").select("*").eq("session_id", session_id).order("id", desc=False).limit(20).execute()
                print(f"[MEMORY] Found {len(history.data) if history.data else 0} previous messages")
            except Exception as e:
                print(f"[MEMORY] Error fetching history: {e}")
                history = None
            
            # ============================================================
            # STEP 4: BUILD CONTEXT WITH TOOL RESULTS AND HISTORY
            # ============================================================
            # Start with system prompt
            messages = [("system", selected_prompt)]
            
            # Add conversation history (previous messages)
            if history and history.data:
                # Add all previous messages to maintain context
                for log in history.data:
                    if log['event_type'] == 'user':
                        messages.append(("human", log['message']))
                    elif log['event_type'] == 'ai':
                        messages.append(("assistant", log['message']))
                print(f"[MEMORY] Added {len(history.data)} messages to context")
            
            # Add current message (with tool results if any)
            if tool_result:
                # If we have tool results, add them to the current message
                current_message_with_context = f"""User query: {data}

I retrieved the following data using the {tool_name} function:
{json.dumps(tool_result, indent=2)}

Please use this data to answer the user's question in a natural, conversational way. 
Don't just repeat the raw data - interpret it and present it in a user-friendly format."""
                messages.append(("human", current_message_with_context))
            else:
                # Just add the current message
                messages.append(("human", data))
            
            print(f"[MEMORY] Total messages in context: {len(messages)}")
            
            # ============================================================
            # STEP 5: GENERATE AI RESPONSE WITH FULL CONVERSATION HISTORY
            # ============================================================
            full_response = ""
            try:
                
                for chunk in model.stream(messages):
                    if hasattr(chunk, 'content'):
                        token = chunk.content
                        full_response += token
                        await websocket.send_text(token)
                
                # Log the complete AI response
                if full_response:
                    # Try to log with metadata, fall back without it if column doesn't exist
                    try:
                        supabase.from_("session_logs").insert([{
                            "session_id": session_id,
                            "event_type": "ai",
                            "message": full_response,
                            "metadata": json.dumps({
                                "intent": intent,
                                "tool_used": tool_name if should_use else None
                            })
                        }]).execute()
                    except Exception as metadata_error:
                        # If metadata column doesn't exist, log without it
                        print(f"[LOG] Metadata column not found, logging without it: {metadata_error}")
                        supabase.from_("session_logs").insert([{
                            "session_id": session_id,
                            "event_type": "ai",
                            "message": full_response
                        }]).execute()
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                await websocket.send_text(error_msg)
                print(f"Error generating response: {e}")
    
    except WebSocketDisconnect:
        print(f"[WEBSOCKET] ============================================")
        print(f"[WEBSOCKET] Client disconnected for session: {session_id}")
        print(f"[WEBSOCKET] Triggering post-session processing...")
        print(f"[WEBSOCKET] ============================================")
        # Post-session processing
        await finalize_session(session_id)
        print(f"[WEBSOCKET] Post-session processing complete")
    except Exception as e:
        print(f"[WEBSOCKET] ❌ Unexpected error in WebSocket: {e}")
        import traceback
        print(f"[WEBSOCKET] Traceback: {traceback.format_exc()}")
        # Still try to finalize the session
        print(f"[WEBSOCKET] Attempting to finalize session despite error...")
        try:
            await finalize_session(session_id)
        except Exception as e2:
            print(f"[WEBSOCKET] Failed to finalize: {e2}")
    
        
        
