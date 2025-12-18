"""
Supabase Connection & Schema Checker
Run this to diagnose database issues
"""
from dotenv import load_dotenv
import os

load_dotenv()

# Check environment variables
print("=" * 60)
print("🔍 CHECKING ENVIRONMENT VARIABLES")
print("=" * 60)

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url:
    print("❌ SUPABASE_URL is not set in .env file")
    exit(1)
else:
    print(f"✅ SUPABASE_URL: {supabase_url}")

if not supabase_key:
    print("❌ SUPABASE_KEY is not set in .env file")
    exit(1)
else:
    # Show first 20 and last 10 characters for security
    masked_key = f"{supabase_key[:20]}...{supabase_key[-10:]}"
    print(f"✅ SUPABASE_KEY: {masked_key}")

# Check key type
if "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" in supabase_key:
    print("✅ Key format looks correct (JWT)")
else:
    print("⚠️  Key format doesn't look like a JWT token")

print()

# Try to connect
print("=" * 60)
print("🔌 TESTING SUPABASE CONNECTION")
print("=" * 60)

try:
    from supabase import create_client
    supabase = create_client(supabase_url, supabase_key)
    print("✅ Supabase client created successfully")
except Exception as e:
    print(f"❌ Failed to create Supabase client: {e}")
    exit(1)

print()

# Check if tables exist
print("=" * 60)
print("📊 CHECKING DATABASE TABLES")
print("=" * 60)

# Test sessions table
try:
    result = supabase.from_("sessions").select("*").limit(1).execute()
    print(f"✅ 'sessions' table exists")
    print(f"   Total records: {len(result.data)}")
    
    # Check if we can see the schema
    if result.data:
        print(f"   Sample columns: {list(result.data[0].keys())}")
except Exception as e:
    print(f"❌ 'sessions' table error: {e}")
    print("\n   💡 SOLUTION: Run the SQL schema in Supabase SQL Editor")
    print("   👉 File: supabase_schema.sql")
    print("   👉 Or see: DATABASE_SETUP.md")

print()

# Test session_logs table
try:
    result = supabase.from_("session_logs").select("*").limit(1).execute()
    print(f"✅ 'session_logs' table exists")
    print(f"   Total records: {len(result.data)}")
except Exception as e:
    print(f"❌ 'session_logs' table error: {e}")

print()

# Test creating a session
print("=" * 60)
print("🧪 TESTING SESSION CREATION")
print("=" * 60)

import uuid
from datetime import datetime

test_session_id = str(uuid.uuid4())
print(f"Test session ID: {test_session_id}")

try:
    result = supabase.from_("sessions").insert([{
        "session_id": test_session_id,
        "user_id": "test_user",
        "status": "active",
        "start_time": datetime.utcnow().isoformat()
    }]).execute()
    
    print("✅ Successfully created test session!")
    print(f"   Inserted record: {result.data}")
    
    # Clean up - delete test session
    supabase.from_("sessions").delete().eq("session_id", test_session_id).execute()
    print("✅ Test session cleaned up")
    
except Exception as e:
    print(f"❌ Failed to create session: {e}")
    
    # Check which column is missing
    error_msg = str(e)
    if "'status'" in error_msg:
        print("\n   💡 Missing column: 'status'")
    elif "'start_time'" in error_msg:
        print("\n   💡 Missing column: 'start_time'")
    elif "'user_id'" in error_msg:
        print("\n   💡 Missing column: 'user_id'")
    
    print("\n   🔧 FIX: Your table schema is incomplete.")
    print("   👉 Run the complete SQL from: supabase_schema.sql")
    print("   👉 See guide: DATABASE_SETUP.md")

print()
print("=" * 60)
print("🎉 DIAGNOSIS COMPLETE")
print("=" * 60)
print()
print("Next steps:")
print("1. If you see ❌ errors above, follow the fixes suggested")
print("2. Run supabase_schema.sql in Supabase SQL Editor")
print("3. Run this script again to verify")
print("4. Start your server: python -m uvicorn proj:app --port 8000")
print()
