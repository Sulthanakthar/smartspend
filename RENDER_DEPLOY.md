# 🚀 SmartSpend - Deploy on Render

Your Live Application URL:
```
https://smartspend.onrender.com
```

## Quick Start Steps

### 1. Create Render Account
Visit https://render.com and sign up with GitHub

### 2. Create PostgreSQL Database
- Dashboard → New → PostgreSQL
- Name: smartspend-db
- Database: smartspend
- Copy the Internal Database URL

### 3. Create Redis
- Dashboard → New → Redis
- Name: smartspend-redis
- Copy the Internal Redis URL

### 4. Deploy Web Service
- Dashboard → New → Web Service
- Connect: https://github.com/Sulthanakthar/smartspend
- Environment: Docker
- Name: smartspend

### 5. Add Environment Variables
- DEBUG: False
- ALLOWED_HOSTS: smartspend.onrender.com
- DATABASE_URL: (from PostgreSQL)
- REDIS_URL: (from Redis)
- PORT: 8000

### 6. Deploy
Click "Create Web Service" and wait for build

### 7. Create Admin User
In Web Service Shell:
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 8. Access Your App
```
https://smartspend.onrender.com
```

Admin panel: https://smartspend.onrender.com/admin

🎉 Your app is live!
