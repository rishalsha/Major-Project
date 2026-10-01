"""
SQLite Database System for Recruitment App
Handles users, sessions, and candidates data
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
import bcrypt
import os
import csv
from io import StringIO

DB_PATH = "recruitment.db"

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with tables and default admin user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            company_name TEXT,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Recruitment sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recruitment_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_name TEXT NOT NULL,
            job_description TEXT,
            job_title TEXT,
            resume_count INTEGER DEFAULT 0,
            workflow_config TEXT,
            results_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # Candidates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            candidate_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            score REAL,
            rank INTEGER,
            interview_date TEXT,
            interview_time TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (session_id) REFERENCES recruitment_sessions(id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes for better performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON recruitment_sessions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON candidates(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON users(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON users(email)")
    
    conn.commit()
    
    # Create default admin user if it doesn't exist
    admin_username = "admin"
    cursor.execute("SELECT id FROM users WHERE username = ?", (admin_username,))
    if not cursor.fetchone():
        password_hash = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("""
            INSERT INTO users (username, email, company_name, password_hash, role)
            VALUES (?, ?, ?, ?, ?)
        """, (admin_username, "admin@example.com", "Admin Company", password_hash, "admin"))
        conn.commit()
    
    conn.close()

def create_user(username: str, email: str, company_name: str, password: str) -> Tuple[bool, str]:
    """
    Create a new user with bcrypt password hashing
    Returns: (success: bool, message: str)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return False, "Username already exists"
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            return False, "Email already exists"
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Insert user
        cursor.execute("""
            INSERT INTO users (username, email, company_name, password_hash, role)
            VALUES (?, ?, ?, ?, ?)
        """, (username, email, company_name, password_hash, 'user'))
        
        conn.commit()
        conn.close()
        return True, "User created successfully"
    
    except sqlite3.Error as e:
        conn.close()
        return False, f"Database error: {str(e)}"

def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[Dict]]:
    """
    Authenticate user with username and password
    Returns: (success: bool, user_data: dict or None)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, username, email, company_name, password_hash, role, created_at
            FROM users WHERE username = ?
        """, (username,))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return False, None
        
        # Verify password
        stored_hash = user['password_hash']
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            user_data = {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'company_name': user['company_name'],
                'role': user['role'],
                'created_at': user['created_at']
            }
            return True, user_data
        else:
            return False, None
    
    except sqlite3.Error as e:
        conn.close()
        return False, None

def update_user_profile(user_id: int, update_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Update user profile information
    Returns: (success: bool, message: str)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Build update query based on provided data
        updates = []
        values = []
        
        if 'email' in update_data:
            # Check if email already exists for another user
            cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", 
                          (update_data['email'], user_id))
            if cursor.fetchone():
                conn.close()
                return False, "Email already in use by another account"
            updates.append("email = ?")
            values.append(update_data['email'])
        
        if 'company_name' in update_data:
            updates.append("company_name = ?")
            values.append(update_data['company_name'])
        
        if 'password' in update_data:
            # Hash the new password
            password_hash = bcrypt.hashpw(update_data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            updates.append("password_hash = ?")
            values.append(password_hash)
        
        if not updates:
            conn.close()
            return False, "No changes to update"
        
        # Add user_id to values
        values.append(user_id)
        
        # Execute update
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        
        conn.commit()
        conn.close()
        return True, "Profile updated successfully"
    
    except sqlite3.Error as e:
        conn.close()
        return False, f"Database error: {str(e)}"

def save_session_to_db(user_id: int, session_name: str, job_description: str, 
                       job_title: str, resume_count: int, workflow_config: Dict, 
                       results_data: Dict) -> Optional[int]:
    """
    Save complete recruitment session to database
    Returns: session_id or None if error
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Convert dicts to JSON strings
        workflow_json = json.dumps(workflow_config) if workflow_config else None
        results_json = json.dumps(results_data) if results_data else None
        
        cursor.execute("""
            INSERT INTO recruitment_sessions 
            (user_id, session_name, job_description, job_title, resume_count, workflow_config, results_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, session_name, job_description, job_title, resume_count, workflow_json, results_json))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id
    
    except sqlite3.Error as e:
        conn.close()
        return None

def save_candidates_to_db(session_id: int, candidates: List[Dict]) -> bool:
    """
    Save candidates for a recruitment session - UPDATED WITH DEBUG
    """
    print(f"⏳ DEBUG: Starting save_candidates_to_db for session {session_id}")
    print(f"📊 DEBUG: Received {len(candidates)} candidates")
    
    if not candidates:
        print("❌ DEBUG: No candidates provided")
        return True
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Show first few candidates for debugging
        print("👤 DEBUG Sample candidates:")
        for i, candidate in enumerate(candidates[:3]):
            if isinstance(candidate, dict):
                print(f"  {i+1}. Name: {candidate.get('name', 'No name')}, "
                      f"Email: {candidate.get('email', 'No email')}, "
                      f"Rank: {candidate.get('rank', 'No rank')}")
        
        # Delete existing candidates for this session
        cursor.execute("DELETE FROM candidates WHERE session_id = ?", (session_id,))
        print(f"🗑️ DEBUG: Deleted existing candidates for session {session_id}")
        
        inserted_count = 0
        
        # Insert each candidate
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            
            # Extract data with fallbacks
            name = candidate.get('name') or candidate.get('Name') or 'Unknown'
            email = candidate.get('email') or candidate.get('Email') or ''
            phone = candidate.get('phone') or candidate.get('Phone') or ''
            
            # Handle score (convert to float)
            score = 0.0
            score_val = candidate.get('score') or candidate.get('Score')
            if score_val is not None:
                try:
                    score = float(score_val)
                except (ValueError, TypeError):
                    score = 0.0
            
            # Handle rank (convert to int)
            rank = 0
            rank_val = candidate.get('rank') or candidate.get('Rank')
            if rank_val is not None:
                try:
                    rank = int(rank_val)
                except (ValueError, TypeError):
                    rank = 0
            
            # Interview info
            interview_date = candidate.get('interview_date') or candidate.get('Interview Date') or ''
            interview_time = candidate.get('interview_time') or candidate.get('Interview Time') or ''
            
            # Status
            status = candidate.get('status') or candidate.get('Status') or 'eligible'
            
            # Only save if we have at least a name
            if name and name != 'Unknown':
                cursor.execute("""
                    INSERT INTO candidates 
                    (session_id, candidate_name, email, phone, score, rank, 
                     interview_date, interview_time, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    name[:100] if name else 'Unknown',
                    email[:100] if email else '',
                    phone[:20] if phone else '',
                    score,
                    rank,
                    interview_date[:20] if interview_date else '',
                    interview_time[:20] if interview_time else '',
                    status[:20] if status else 'eligible'
                ))
                inserted_count += 1
        
        conn.commit()
        print(f"✅ DEBUG: Successfully saved {inserted_count} candidates to database")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ DEBUG: Error saving candidates: {e}")
        import traceback
        print(traceback.format_exc())
        conn.rollback()
        conn.close()
        return False
def get_user_sessions(user_id: int) -> List[Dict]:
    """Get all recruitment sessions for a user - SIMPLIFIED"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, session_name, job_title, resume_count, created_at
            FROM recruitment_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'id': row['id'],
                'session_name': row['session_name'],
                'job_title': row['job_title'],
                'resume_count': row['resume_count'],
                'created_at': row['created_at']
            })
        
        conn.close()
        print(f"DEBUG: Found {len(sessions)} sessions for user {user_id}")
        return sessions
    
    except sqlite3.Error as e:
        conn.close()
        print(f"Error getting user sessions: {e}")
        return []

def get_session_details(session_id: int) -> Optional[Dict]:
    """Get session with candidates - SIMPLIFIED"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get basic session info
        cursor.execute("""
            SELECT id, session_name, job_description, job_title, resume_count, created_at
            FROM recruitment_sessions
            WHERE id = ?
        """, (session_id,))
        
        session_row = cursor.fetchone()
        if not session_row:
            conn.close()
            print(f"❌ DEBUG: No session found with ID {session_id}")
            return None
        
        # Get candidates for this session
        cursor.execute("""
            SELECT candidate_name, email, phone, score, rank, 
                   interview_date, interview_time, status
            FROM candidates
            WHERE session_id = ?
            ORDER BY rank ASC, score DESC
        """, (session_id,))
        
        candidates = []
        for row in cursor.fetchall():
            candidates.append({
                'name': row['candidate_name'],
                'email': row['email'],
                'phone': row['phone'],
                'score': row['score'],
                'rank': row['rank'],
                'interview_date': row['interview_date'],
                'interview_time': row['interview_time'],
                'status': row['status']
            })
        
        print(f"✅ DEBUG: Retrieved {len(candidates)} candidates for session {session_id}")
        
        # Create session data
        session_data = {
            'id': session_row['id'],
            'session_name': session_row['session_name'],
            'job_description': session_row['job_description'],
            'job_title': session_row['job_title'],
            'resume_count': session_row['resume_count'],
            'created_at': session_row['created_at'],
            'candidates': candidates
        }
        
        conn.close()
        return session_data
        
    except Exception as e:
        print(f"❌ DEBUG: Error in get_session_details: {e}")
        conn.close()
        return None
    
def delete_session(session_id: int, user_id: int) -> bool:
    """
    Delete a recruitment session (only if user owns it)
    Returns: True if deleted, False otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check ownership
        cursor.execute("SELECT user_id FROM recruitment_sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        
        if not session or session['user_id'] != user_id:
            conn.close()
            return False
        
        # Delete session (candidates will be deleted via CASCADE)
        cursor.execute("DELETE FROM recruitment_sessions WHERE id = ?", (session_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        
        return deleted
    
    except sqlite3.Error as e:
        print(f"Error deleting session: {e}")
        conn.close()
        return False

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user data by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, username, email, company_name, role, created_at
            FROM users WHERE id = ?
        """, (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'company_name': user['company_name'],
                'role': user['role'],
                'created_at': user['created_at']
            }
        return None
    
    except sqlite3.Error as e:
        conn.close()
        return None

def get_user_statistics(user_id: int) -> Dict[str, Any]:
    """
    Get statistics for a user
    Returns: Dictionary with user statistics
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Total sessions
        cursor.execute("SELECT COUNT(*) as total FROM recruitment_sessions WHERE user_id = ?", (user_id,))
        total_sessions_result = cursor.fetchone()
        total_sessions = total_sessions_result['total'] if total_sessions_result else 0
        
        # Total candidates processed
        cursor.execute("""
            SELECT SUM(resume_count) as total_candidates 
            FROM recruitment_sessions 
            WHERE user_id = ?
        """, (user_id,))
        
        total_candidates_result = cursor.fetchone()
        total_candidates = total_candidates_result['total_candidates'] if total_candidates_result and total_candidates_result['total_candidates'] else 0
        
        # Recent sessions (last 5)
        cursor.execute("""
            SELECT session_name, created_at, resume_count 
            FROM recruitment_sessions 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 5
        """, (user_id,))
        
        recent_sessions = []
        for row in cursor.fetchall():
            recent_sessions.append({
                'name': row['session_name'],
                'date': row['created_at'],
                'resumes': row['resume_count']
            })
        
        conn.close()
        
        return {
            'total_sessions': total_sessions,
            'total_candidates': total_candidates,
            'recent_sessions': recent_sessions
        }
    
    except Exception as e:
        conn.close()
        return {
            'total_sessions': 0,
            'total_candidates': 0,
            'recent_sessions': []
        }

def get_session_candidates_csv(session_id: int) -> str:
    """
    Get candidates for a session as CSV string
    Returns: CSV formatted string
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get session info
        cursor.execute("SELECT session_name, created_at FROM recruitment_sessions WHERE id = ?", (session_id,))
        session_info = cursor.fetchone()
        
        if not session_info:
            conn.close()
            return ""
        
        # Get candidates
        cursor.execute("""
            SELECT candidate_name, email, phone, score, rank, interview_date, interview_time, status
            FROM candidates
            WHERE session_id = ?
            ORDER BY rank ASC, score DESC
        """, (session_id,))
        
        candidates = cursor.fetchall()
        
        # Build CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header with session info
        writer.writerow(['Session Name', session_info['session_name']])
        writer.writerow(['Generated On', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Session Created', session_info['created_at']])
        writer.writerow([])  # Empty line
        
        # Write candidate headers
        writer.writerow(['Name', 'Email', 'Phone', 'Score', 'Rank', 
                        'Interview Date', 'Interview Time', 'Status'])
        
        # Write candidate data
        for candidate in candidates:
            writer.writerow([
                candidate['candidate_name'],
                candidate['email'],
                candidate['phone'],
                candidate['score'],
                candidate['rank'],
                candidate['interview_date'],
                candidate['interview_time'],
                candidate['status']
            ])
        
        conn.close()
        return output.getvalue()
    
    except Exception as e:
        conn.close()
        return ""

def check_username_exists(username: str) -> bool:
    """Check if username already exists"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    except:
        conn.close()
        return False

def check_email_exists(email: str) -> bool:
    """Check if email already exists"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    except:
        conn.close()
        return False

def get_total_candidates_processed(user_id: int) -> int:
    """Get total number of candidates processed by user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT SUM(resume_count) as total 
            FROM recruitment_sessions 
            WHERE user_id = ?
        """, (user_id,))
        
        result = cursor.fetchone()
        total = result['total'] if result and result['total'] else 0
        conn.close()
        return total
    except:
        conn.close()
        return 0

def get_candidates_by_session(session_id: int) -> List[Dict]:
    """Get candidates for a specific session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT candidate_name, email, phone, score, rank, interview_date, interview_time, status
            FROM candidates
            WHERE session_id = ?
            ORDER BY rank ASC, score DESC
        """, (session_id,))
        
        candidates = []
        for row in cursor.fetchall():
            candidates.append({
                'name': row['candidate_name'],
                'email': row['email'],
                'phone': row['phone'],
                'score': row['score'],
                'rank': row['rank'],
                'interview_date': row['interview_date'],
                'interview_time': row['interview_time'],
                'status': row['status']
            })
        
        conn.close()
        return candidates
    except:
        conn.close()
        return []

def get_recent_sessions(user_id: int, limit: int = 5) -> List[Dict]:
    """Get recent sessions for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, session_name, job_title, resume_count, created_at
            FROM recruitment_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'id': row['id'],
                'session_name': row['session_name'],
                'job_title': row['job_title'],
                'resume_count': row['resume_count'],
                'created_at': row['created_at']
            })
        
        conn.close()
        return sessions
    except:
        conn.close()
        return []

def get_session_count(user_id: int) -> int:
    """Get total number of sessions for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) as count FROM recruitment_sessions WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        count = result['count'] if result else 0
        conn.close()
        return count
    except:
        conn.close()
        return 0

def search_sessions(user_id: int, search_term: str) -> List[Dict]:
    """Search sessions by session name or job title"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        search_pattern = f"%{search_term}%"
        cursor.execute("""
            SELECT id, session_name, job_title, resume_count, created_at
            FROM recruitment_sessions
            WHERE user_id = ? AND (session_name LIKE ? OR job_title LIKE ?)
            ORDER BY created_at DESC
        """, (user_id, search_pattern, search_pattern))
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'id': row['id'],
                'session_name': row['session_name'],
                'job_title': row['job_title'],
                'resume_count': row['resume_count'],
                'created_at': row['created_at']
            })
        
        conn.close()
        return sessions
    except:
        conn.close()
        return []

def create_candidate_download_data(session_id: int) -> Tuple[str, str]:
    """
    Create downloadable CSV data for session candidates
    Returns: (filename, csv_data)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get session info for filename
        cursor.execute("SELECT session_name, created_at FROM recruitment_sessions WHERE id = ?", (session_id,))
        session_info = cursor.fetchone()
        
        if not session_info:
            conn.close()
            return "", ""
        
        # Get candidates
        cursor.execute("""
            SELECT candidate_name, email, phone, score, rank, interview_date, interview_time, status
            FROM candidates
            WHERE session_id = ?
            ORDER BY rank ASC, score DESC
        """, (session_id,))
        
        candidates = cursor.fetchall()
        
        # Create filename
        session_name_clean = session_info['session_name'].replace(" ", "_").replace("/", "_").replace("\\", "_")
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"candidates_{session_name_clean}_{date_str}.csv"
        
        # Build CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Session Name', session_info['session_name']])
        writer.writerow(['Generated On', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Session Date', session_info['created_at']])
        writer.writerow([])
        
        # Write candidate headers
        writer.writerow(['Name', 'Email', 'Phone', 'Score', 'Rank', 
                        'Interview Date', 'Interview Time', 'Status'])
        
        # Write candidate data
        for candidate in candidates:
            writer.writerow([
                candidate['candidate_name'],
                candidate['email'],
                candidate['phone'],
                candidate['score'],
                candidate['rank'],
                candidate['interview_date'],
                candidate['interview_time'],
                candidate['status']
            ])
        
        conn.close()
        return filename, output.getvalue()
    
    except Exception as e:
        conn.close()
        return "", ""

# Test function
def test_database_functions():
    """Test all database functions"""
    print("🧪 Testing database functions...")
    
    # Initialize database
    init_database()
    print("✅ Database initialized")
    
    # Test user creation
    success, message = create_user("testuser", "test@example.com", "Test Company", "testpass123")
    print(f"📝 Create user test: {success} - {message}")
    
    # Test authentication
    success, user = authenticate_user("testuser", "testpass123")
    print(f"🔐 Authentication test: {success}")
    
    if success and user:
        user_id = user['id']
        print(f"👤 User ID: {user_id}")
        
        # Test session creation
        session_id = save_session_to_db(
            user_id,
            "Test Recruitment Session",
            "Job description for software engineer position",
            "Software Engineer",
            25,
            {"mode": "auto", "scheduling": True},
            {"status": "completed", "processed": 25}
        )
        print(f"💾 Save session test: {session_id}")
        
        if session_id:
            # Test saving candidates
            candidates_data = [
                {
                    'name': 'John Doe',
                    'email': 'john@example.com',
                    'phone': '123-456-7890',
                    'score': 8.5,
                    'rank': 1,
                    'interview_date': '2024-12-15',
                    'interview_time': '10:00',
                    'status': 'scheduled'
                },
                {
                    'name': 'Jane Smith',
                    'email': 'jane@example.com',
                    'phone': '987-654-3210',
                    'score': 7.8,
                    'rank': 2,
                    'interview_date': '2024-12-16',
                    'interview_time': '11:00',
                    'status': 'scheduled'
                }
            ]
            
            candidates_saved = save_candidates_to_db(session_id, candidates_data)
            print(f"👥 Save candidates test: {candidates_saved}")
            
            # Test getting sessions
            sessions = get_user_sessions(user_id)
            print(f"📋 Get user sessions test: {len(sessions)} sessions found")
            
            # Test session details
            session_details = get_session_details(session_id)
            print(f"🔍 Get session details test: {session_details is not None}")
            
            # Test statistics
            stats = get_user_statistics(user_id)
            print(f"📊 User statistics test: {stats}")
            
            # Test CSV generation
            csv_data = get_session_candidates_csv(session_id)
            print(f"📄 CSV generation test: {len(csv_data) > 0}")
            
            # Test update profile
            update_success, update_msg = update_user_profile(user_id, {
                'email': 'updated@example.com',
                'company_name': 'Updated Company'
            })
            print(f"🔄 Update profile test: {update_success} - {update_msg}")
            
            # Test session count
            session_count = get_session_count(user_id)
            print(f"🔢 Session count test: {session_count}")
            
            # Test recent sessions
            recent = get_recent_sessions(user_id, 3)
            print(f"🕒 Recent sessions test: {len(recent)} sessions")
            
            # Test search
            search_results = search_sessions(user_id, "test")
            print(f"🔎 Search sessions test: {len(search_results)} results")
            
            # Test candidate download data
            filename, csv_content = create_candidate_download_data(session_id)
            print(f"💾 Candidate download test: {filename} - {len(csv_content) > 0}")
    
    print("✅ Database testing completed!")

if __name__ == "__main__":
    test_database_functions()