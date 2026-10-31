# Brightloop Subscription Management System — Backend

## Setup

### 1. Create virtual environment
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment (optional)
Copy `.env.example` to `.env` and edit:
```bash
cp .env.example .env
```

### 4. Run the server
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Seed demo data
```bash
# Standard seed (~20 customers, sample data)
python seed.py

# Large seed for performance testing (5000+ subs)
python seed.py --large
```

API docs: http://localhost:8000/docs

## Demo Credentials
- **Admin**: admin@brightloop.com / Admin@12345
- **Staff**: staff@brightloop.com / Staff@12345
- **Customer**: customer@brightloop.com / Customer@12345
