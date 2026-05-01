# CourseCompass

An AI-powered academic advising chatbot built using LLMs (Groq/Llama) and Neo4j graph database to help students with course selection, degree planning, and academic queries.

## Features

- Natural language understanding for academic-related questions
- Course recommendation based on interests and academic goals
- Prerequisite visualization with interactive Cytoscape.js graphs
- Degree progress tracking
- Session-based conversation history
- Rate limiting for API protection

## Architecture

```
CourseCompass/
├── bot/                           # Chatbot application
│   ├── intents/                   # Intent-specific handlers
│   │   ├── advising.py           # Advising & general queries
│   │   ├── course_info.py        # Course information
│   │   ├── next_course.py        # What comes after a course
│   │   ├── prereqs.py            # Prerequisites queries
│   │   └── smalltalk.py          # Greetings & casual chat
│   ├── agent.py                   # Main orchestrator
│   ├── config.py                  # Configuration & constants
│   ├── groqllm.py                 # Groq LLM wrapper
│   ├── prompts.py                 # LLM prompt templates
│   ├── queries.py                 # Neo4j query helpers
│   └── views.py                   # Chat views with rate limiting
├── courses/                       # Course management
│   ├── services.py               # Shared business logic
│   ├── views.py                  # Course CRUD views
│   └── forms.py                  # Course forms
├── CourseCompass/                 # Django project settings
│   ├── settings/                  # Split settings
│   │   ├── base.py               # Common settings
│   │   ├── dev.py                # Development settings
│   │   └── prod.py               # Production settings
│   └── neo4j_driver.py           # Neo4j connection
├── templates/                     # HTML templates
└── docker/                        # Docker configuration
```

## Setup

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# Django
SECRET_KEY=your-secret-key-here
DJANGO_ENV=development  # or 'production'
ALLOWED_HOSTS=localhost,127.0.0.1,34.123.45.67
CSRF_TRUSTED_ORIGINS=http://34.123.45.67
USE_HTTPS=false

# Neo4j
NEO4J_URI=neo4j+s://your-neo4j-uri
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_SKIP_SSL_VERIFY=false  # Set to 'true' only for local dev

# LLM
GROQ_API_KEY=your-groq-api-key

# Rate limiting
CHAT_RATE_LIMIT=30  # requests per minute
```

## Deployment Troubleshooting (GCP VM)

If you see `400 Bad Request` right after deploying, Django is usually rejecting the `Host` header.

Check these first:

```bash
DJANGO_ENV=production
ALLOWED_HOSTS=your-domain.com,<YOUR_VM_EXTERNAL_IP>
CSRF_TRUSTED_ORIGINS=http://your-domain.com,http://<YOUR_VM_EXTERNAL_IP>
```

Notes:

- `ALLOWED_HOSTS` must include the exact host users access.
- `CSRF_TRUSTED_ORIGINS` must include scheme (`http://` or `https://`).
- If you run behind HTTPS with a reverse proxy/load balancer, set `USE_HTTPS=true` only when Django is correctly receiving HTTPS/proxy headers.

### 2. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Start the Server

```bash
python manage.py runserver
```

## Docker Deployment

```bash
cd docker
docker-compose up --build
```

## GitHub Actions Deployment Secrets

For VM deployments, store production settings as separate GitHub Secrets (not a bundled blob):

```text
SECRET_KEY
DJANGO_ENV                # production
ALLOWED_HOSTS             # e.g. your-domain.com,34.123.45.67
CSRF_TRUSTED_ORIGINS      # e.g. https://your-domain.com,http://34.123.45.67
USE_HTTPS                 # true or false
CHAT_RATE_LIMIT           # e.g. 30

GROQ_API_KEY
NEO4J_URI
NEO4J_USERNAME
NEO4J_PASSWORD
```

Infra secrets remain separate from app settings:

```text
# GCP workflow
GCE_KEY
GCE_HOST
GCE_USER

# EC2 workflow
EC2_KEY
EC2_HOST
EC2_USER
```

## Development

### Running Tests

```bash
python manage.py test bot
python manage.py test courses
```

### Code Structure

- **Intent Detection**: The chatbot uses LLM to detect user intent and route to appropriate handlers
- **Graph Queries**: Neo4j Cypher queries for course relationships
- **Response Generation**: LLM-powered natural language responses with factual data
- **Session Management**: Per-user conversation history stored in Django sessions

## Graph Schema

See [docs/schema.md](docs/schema.md) for the Neo4j graph schema documentation.

## License

MIT
