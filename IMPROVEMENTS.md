# CourseCompass Improvements

This document summarizes all optimizations and improvements implemented in the CourseCompass chatbot codebase.

---

## 1. Security & Configuration

### 1.1 Environment-Based Settings
**Files:** `CourseCompass/settings/base.py`, `dev.py`, `prod.py`, `__init__.py`

- Split monolithic `settings.py` into modular structure:
  - `base.py` - Common settings shared across environments
  - `dev.py` - Development-specific settings (DEBUG=True, verbose logging)
  - `prod.py` - Production settings (security headers, HTTPS settings)
- Settings auto-load based on `DJANGO_ENV` environment variable

### 1.2 Secrets Management
**Before:** Hardcoded secret key in settings.py
```python
SECRET_KEY = 'django-insecure-nq&ndx&2x0s(1^7(u$2@&sw)!#suqejkdv6@6399^(y93ip0p7'
```

**After:** Loaded from environment
```python
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production')
```

### 1.3 Neo4j SSL Configuration
**File:** `CourseCompass/neo4j_driver.py`

**Before:** SSL verification always disabled (insecure)
```python
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
```

**After:** Configurable via environment variable, secure by default
```python
SKIP_SSL_VERIFY = os.getenv("NEO4J_SKIP_SSL_VERIFY", "false").lower() == "true"
```

### 1.4 Added `.env.example` Template
Created example environment file with all required variables documented.

---

## 2. Code Refactoring

### 2.1 Split `agent.py` (626 lines → 6 modules)

**Before:** Single monolithic file with all chatbot logic

**After:** Modular structure:

| Module | Purpose | Lines |
|--------|---------|-------|
| `bot/config.py` | Configuration, constants, course aliases | ~45 |
| `bot/queries.py` | Neo4j Cypher query helpers | ~115 |
| `bot/prompts.py` | LLM prompt templates | ~145 |
| `bot/agent.py` | Main orchestrator only | ~115 |
| `bot/intents/__init__.py` | Intent handler exports | ~20 |
| `bot/intents/prereqs.py` | Prerequisites queries | ~115 |
| `bot/intents/advising.py` | Advising & general queries | ~45 |
| `bot/intents/course_info.py` | Course information handler | ~65 |
| `bot/intents/smalltalk.py` | Greetings handler | ~25 |
| `bot/intents/next_course.py` | Next course queries | ~60 |

### 2.2 Deduplicated Course Views
**File:** `courses/views.py`, `courses/services.py`

**Before:** Duplicate code in `add_course()` and `edit_course()`:
- Prerequisite parsing logic duplicated
- Validation logic duplicated  
- Database operations duplicated
- Bug: Missing courses appended twice due to duplicate loop

**After:** Extracted to `courses/services.py`:
```python
def parse_prereq_groups_from_post(request_post) -> Tuple[List, List, List]
def validate_prereq_courses(session, codes) -> List[str]
def create_prereq_groups(session, course_code, required, recommended, custom)
def delete_course_prereq_groups(session, course_code)
def get_all_prereq_codes(required, recommended, custom) -> set
def create_or_update_course(session, code, title, credits, level, description)
def get_course_prereq_groups(session, code) -> Tuple[List, List, List]
```

### 2.3 Fixed Duplicate Imports
**Before:**
```python
import re
import uuid
import re      # duplicate
import uuid    # duplicate
```

**After:** Single import of each module

---

## 3. Debug Code Removal

### 3.1 Removed Print Statements
**Files:** `bot/groqllm.py`, `bot/agent.py` (old)

**Before:**
```python
print("Payload sent to Groq API:", {...})
print("Response JSON keys:", list(data.keys()))
print("[DEBUG] Intent:", intent)
```

**After:** All debug prints removed or replaced with proper logging

### 3.2 Added Proper Logging
**All modules now use:**
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Intent: {intent} | Codes: {course_codes}")
logger.error(f"LLM error: {e}")
logger.debug(f"Query result: {res}")
```

---

## 4. Error Handling

### 4.1 View-Level Error Handling
**File:** `bot/views.py`

**Before:** No try/catch, errors would crash the request
```python
bot_result = advisor_response(user_message)
```

**After:** Graceful error handling with user-friendly messages
```python
try:
    bot_result = advisor_response(user_message, session_history=history)
except Exception as e:
    logger.exception(f"Error processing message: {e}")
    bot_result = {
        "type": "text",
        "content": "I apologize, but I encountered an error. Please try again."
    }
```

### 4.2 Intent Handler Error Handling
All intent handlers now have try/except blocks with fallback responses.

---

## 5. Per-User Conversation State

### 5.1 Session-Based Chat History
**File:** `bot/views.py`

**Before:** Global mutable state (broken for multiple users)
```python
conversation_history: List[Dict[str, str]] = []
last_course_code: Optional[str] = None
```

**After:** Django session-based storage
```python
def get_chat_history(request) -> list:
    if 'chat_history' not in request.session:
        request.session['chat_history'] = []
    return request.session['chat_history']

def add_to_chat_history(request, user_message, bot_response):
    history = get_chat_history(request)
    history.append({'user': user_message, 'bot': bot_response, 'timestamp': time.time()})
    # Keep only last 50 messages
    request.session['chat_history'] = history[-50:]
```

### 5.2 Rate Limiting
**File:** `bot/views.py`

Added per-session rate limiting to prevent API abuse:
```python
def is_rate_limited(session_key: str, limit: int = None) -> bool:
    # 1-minute sliding window rate limiter
    # Configurable via CHAT_RATE_LIMIT setting (default: 30 req/min)
```

### 5.3 Clear History Endpoint
**File:** `bot/urls.py`

Added new endpoint to clear chat history:
```python
path('clear-history/', views.clear_history, name='clear_history'),
```

---

## 6. Docker Improvements

### 6.1 Multi-Stage Build
**File:** `docker/Dockerfile`

**Before:** Single stage, larger image
```dockerfile
FROM python:3.12-slim
WORKDIR /CourseCompass
```

**After:** Multi-stage build for smaller production image
```dockerfile
FROM python:3.12-slim as builder
# Install dependencies

FROM python:3.12-slim as runtime
COPY --from=builder /usr/local/lib/python3.12/site-packages ...
```

### 6.2 Security Improvements
- Added non-root user: `useradd -m -u 1000 appuser`
- Set `USER appuser` before running application

### 6.3 Health Checks
**Dockerfile:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/chat/')"
```

**docker-compose.yml:**
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "..."]
  interval: 30s
  timeout: 10s
  retries: 3
```

### 6.4 Production-Ready Gunicorn Config
**Before:**
```yaml
command: gunicorn CourseCompass.wsgi:application --bind 0.0.0.0:8000
```

**After:**
```yaml
command: gunicorn CourseCompass.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 120
```

### 6.5 Proper Volume Mounts
**Before:** Entire source mounted (includes .env, .git, etc.)
```yaml
volumes:
  - ../:/app
```

**After:** Only necessary files
```yaml
volumes:
  - ../staticfiles:/app/staticfiles
  - ../db.sqlite3:/app/db.sqlite3
```

---

## 7. Test Fixes

### 7.1 Fixed Import Path
**File:** `bot/tests.py`

**Before:** Incorrect double-nested import
```python
from CourseCompass.CourseCompass.neo4j_driver import driver
```

**After:** Correct import path
```python
from CourseCompass.neo4j_driver import driver
```

### 7.2 Updated to Use New Module Structure
```python
from . import queries  # instead of from . import agent as advisor
```

### 7.3 Replaced Prints with Logging
All `print()` statements in tests replaced with `logger.info()`.

---

## 8. Documentation

### 8.1 Updated README.md
- Added architecture diagram
- Documented all environment variables
- Added setup instructions
- Added Docker deployment guide
- Added development section

---

## File Changes Summary

| Category | Files Added | Files Modified |
|----------|-------------|----------------|
| Settings | 4 | 1 |
| Bot Module | 8 | 4 |
| Courses | 1 | 1 |
| Docker | 0 | 3 |
| Docs | 2 | 0 |
| **Total** | **15** | **9** |

### New Files Created
- `CourseCompass/settings/__init__.py`
- `CourseCompass/settings/base.py`
- `CourseCompass/settings/dev.py`
- `CourseCompass/settings/prod.py`
- `bot/config.py`
- `bot/queries.py`
- `bot/prompts.py`
- `bot/intents/__init__.py`
- `bot/intents/prereqs.py`
- `bot/intents/advising.py`
- `bot/intents/course_info.py`
- `bot/intents/smalltalk.py`
- `bot/intents/next_course.py`
- `courses/services.py`
- `IMPROVEMENTS.md`

### Files Modified
- `CourseCompass/settings.py` (deprecated, forwards to new structure)
- `CourseCompass/neo4j_driver.py`
- `bot/agent.py` (replaced with new orchestrator)
- `bot/groqllm.py`
- `bot/views.py`
- `bot/urls.py`
- `bot/tests.py`
- `courses/views.py` (replaced with refactored version)
- `docker/Dockerfile`
- `docker/docker-compose.yml`
- `docker/entrypoint.sh`
- `README.md`

---

## Migration Notes

### For Existing Deployments

1. **Create `.env` file** from `.env.example` with your secrets
2. **Set `DJANGO_ENV`** to `production` for production deployments
3. **Generate new SECRET_KEY**:
   ```python
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   ```
4. **Review SSL settings** - ensure `NEO4J_SKIP_SSL_VERIFY=false` in production
5. **Run migrations** - session table needed for chat history:
   ```bash
   python manage.py migrate
   ```

### Backward Compatibility

- Old `settings.py` still works (imports from new structure)
- Old `agent_old.py` preserved for reference
- Old `views_old.py` preserved in courses app
