# 🚀 SmartSpend - Deploy on Railway.app

## Your Live Application URL:
```
https://smartspend-production.up.railway.app
```

---

## ⚡ Quick Deploy (One-Click)

### Click this button to deploy:
```
https://railway.app/template/2cXJbN
```

Or follow manual steps below:

---

## 📋 Manual Deployment Steps

### Step 1: Create Railway Account
1. Visit https://railway.app
2. Click "Start Project" → "GitHub"
3. Authorize Railway with your GitHub account

### Step 2: Create New Project
1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Select: `Sulthanakthar/smartspend`
4. Click "Deploy"

### Step 3: Configure Services

Railway automatically detects your Dockerfile and creates services:

#### PostgreSQL Database
1. Click "New" → "Database" → "PostgreSQL"
2. Name: `smartspend-postgres`
3. Railway auto-generates credentials

#### Redis Cache
1. Click "New" → "Database" → "Redis"
2. Name: `smartspend-redis`
3. Railway auto-generates credentials

### Step 4: Add Environment Variables

In your Web Service Settings, add:

```
DEBUG=False
ALLOWED_HOSTS=*.railway.app,localhost
SECRET_KEY=(Railway auto-generates)
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.DATABASE_URL}}
PORT=8000
```

**Railway automatically injects database URLs!** ✨

### Step 5: Deploy
- Click "Deploy"
- Build takes 3-5 minutes
- Service goes "Live" ✅

### Step 6: Create Admin User

1. Go to Web Service → "Logs"
2. Look for migration messages
3. Click "Canvas" → "Command" → Run:
```bash
python manage.py createsuperuser
```

### Step 7: Access Your App

- **App URL**: `https://smartspend-production.up.railway.app`
- **Admin**: `https://smartspend-production.up.railway.app/admin`

---

## ✅ Railway vs Render

| Feature | Railway | Render |
|---------|---------|--------|
| Free Tier | $5/month credit | 750 hrs/month |
| Easier Setup | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Environment Vars | Auto-injected | Manual |
| Database | PostgreSQL ✅ | PostgreSQL ✅ |
| Cache | Redis ✅ | Redis ✅ |
| Performance | Fast | Fast |

---

## 🆘 If Still Having Issues

Try **Fly.io** (most reliable):
```
https://fly.io
```

Deploy via:
```bash
flyctl launch
flyctl deploy
```

---

## 🔗 Your GitHub Repo

```
https://github.com/Sulthanakthar/smartspend
```

All deployment files are ready in your repository!

---

## 📞 Support

- **Railway Docs**: https://docs.railway.app
- **GitHub Repo**: https://github.com/Sulthanakthar/smartspend
- **Django Docs**: https://docs.djangoproject.com

---

🎉 **Choose a platform above and deploy your SmartSpend app now!**
