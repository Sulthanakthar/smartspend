# 🚀 SmartSpend - Deploy on Render (OPTION 1)

**Your Live Application URL (After Deployment):**
```
https://smartspend.onrender.com
```

---

## **Complete Step-by-Step Deployment Guide**

### **Step 1: Create Render Account**
1. Visit **[https://render.com](https://render.com)**
2. Click **"Sign Up"** → Select **"Continue with GitHub"**
3. Authorize Render to access your GitHub account

---

### **Step 2: Create PostgreSQL Database**

1. Go to **Render Dashboard** → Click **"New +"** button
2. Select **"PostgreSQL"**
3. Fill in the form:
   - **Name**: `smartspend-db`
   - **Database**: `smartspend`
   - **User**: `smartspend_user`
   - **Region**: Choose closest to you (e.g., `Ohio`)
   - **Version**: PostgreSQL 15
   - **Plan**: Free tier (optional: upgrade later)
4. Click **"Create Database"**
5. ⏳ Wait 2-3 minutes for database to be ready
6. **Copy the Internal Database URL** - You'll need this later
   - Example: `postgresql://smartspend_user:xxxxx@oregon-postgres.render.com:5432/smartspend`

---

### **Step 3: Create Redis Instance**

1. Go to **Render Dashboard** → Click **"New +"** button
2. Select **"Redis"**
3. Fill in the form:
   - **Name**: `smartspend-redis`
   - **Region**: Same as PostgreSQL (e.g., `Ohio`)
   - **Plan**: Free tier
4. Click **"Create Redis"**
5. ⏳ Wait 1-2 minutes for Redis to be ready
6. **Copy the Internal Redis URL** - You'll need this later
   - Example: `redis://:xxxxx@oregon-redis.render.com:6379`

---

### **Step 4: Deploy Web Service**

1. Go to **Render Dashboard** → Click **"New +"** button
2. Select **"Web Service"**
3. Select **"Deploy an existing repository"**
4. Paste: `https://github.com/Sulthanakthar/smartspend`
5. Click **"Connect"**

#### **Configure Web Service:**

Fill in the form with these details:

| Field | Value |
|-------|-------|
| **Name** | `smartspend` |
| **Environment** | `Docker` |
| **Region** | Same as PostgreSQL & Redis |
| **Branch** | `main` |
| **Build Command** | Leave empty (uses Dockerfile) |
| **Start Command** | Leave empty (uses Dockerfile) |
| **Plan** | Free tier |

---

### **Step 5: Add Environment Variables**

In the **Web Service Settings**, scroll to **"Environment"** section:

Click **"Add Environment Variable"** and add these variables:

| Key | Value | Notes |
|-----|-------|-------|
| `DEBUG` | `False` | Production mode |
| `ALLOWED_HOSTS` | `smartspend.onrender.com` | Your domain |
| `DATABASE_URL` | *Copy from PostgreSQL* | From Step 2 |
| `REDIS_URL` | *Copy from Redis* | From Step 3 |
| `PORT` | `8000` | Default port |
| `SECRET_KEY` | *(Render auto-generates)* | Secure Django key |

**How to paste DATABASE_URL & REDIS_URL:**
- Go back to **PostgreSQL** service → Copy **"Internal Database URL"**
- Go back to **Redis** service → Copy **"Internal Redis URL"**
- Paste into corresponding environment variables

---

### **Step 6: Deploy!**

1. Click **"Create Web Service"**
2. Render will start building (check logs in real-time)
3. ⏳ Build takes 3-5 minutes
4. Once complete, you'll see: **"Live"** ✅

---

### **Step 7: Verify Deployment**

Your app is now live at:
```
https://smartspend.onrender.com
```

**Test it:**
- Open https://smartspend.onrender.com in your browser
- You should see the SmartSpend login page

---

## **🔧 Post-Deployment Setup**

### **Create Superuser (Admin Account)**

1. Go to your **Web Service** on Render
2. Click **"Shell"** tab at the top
3. Run these commands:

```bash
python manage.py migrate
python manage.py createsuperuser
```

Follow the prompts to create your admin account:
- Username: `admin`
- Email: your@email.com
- Password: strong-password-123

---

### **Access Admin Panel**

- Go to: `https://smartspend.onrender.com/admin`
- Login with your superuser credentials
- Manage users, expenses, budgets, etc.

---

## **📊 Monitor Your Deployment**

1. **View Logs**: Click **"Logs"** tab in Web Service
2. **Check Database**: Click **PostgreSQL** service → **"Logs"**
3. **Check Redis**: Click **Redis** service → **"Logs"**
4. **Check Celery Worker**: Check startup logs for worker status

---

## **💾 Database & Backups**

### **Automatic Backups (PostgreSQL)**
- Render automatically backs up your database
- Retention: 7 days free tier

### **Manual Backup**
- From **PostgreSQL service** → **"Settings"** → **"Backup & Restore"**
- Click **"Create Manual Backup"**

---

## **🚀 Auto-Deploy from GitHub**

SmartSpend will automatically redeploy when you push to `main` branch:

1. Make code changes locally
2. Commit & push to GitHub:
   ```bash
   git add .
   git commit -m "Update smartspend"
   git push origin main
   ```
3. Render automatically rebuilds and deploys! ✅

---

## **🔐 Production Checklist**

- ✅ `DEBUG = False` in environment
- ✅ `SECRET_KEY` is secure (Render auto-generates)
- ✅ `ALLOWED_HOSTS` set to your domain
- ✅ Database migrations run
- ✅ Superuser created
- ✅ Static files collected
- ✅ Redis connected for Celery
- ✅ SSL/HTTPS enabled (automatic on Render)

---

## **📈 Cost Estimate**

| Service | Free Tier | Pro Tier | Notes |
|---------|-----------|----------|-------|
| Web Service | $0 (750 hrs/month) | $7/month | Scales automatically |
| PostgreSQL | $0 | $15/month | Free tier has limits |
| Redis | $0 | $15/month | Free tier has limits |
| **Total** | **$0** | **~$37/month** | Upgrade when ready |

---

## **🆘 Troubleshooting**

### **Build Failed**
- Check logs in **"Build"** tab
- Ensure `Dockerfile` exists in repo
- Verify `requirements.txt` is valid

### **Database Connection Error**
- Check `DATABASE_URL` format in environment
- Verify PostgreSQL service is "Live"
- Ensure URL is "Internal Database URL" (not external)

### **Static Files Not Loading**
- Run: `python manage.py collectstatic --noinput`
- Check `STATIC_ROOT` in Django settings
- Verify `STATIC_URL = '/static/'`

### **Celery Worker Not Running**
- Check Redis connection
- View worker logs in **"Logs"** tab
- Ensure `REDIS_URL` is set correctly

### **500 Server Error**
- Check logs in **"Logs"** tab
- Run migrations: `python manage.py migrate`
- Restart service: **"Settings"** → **"Restart"**

---

## **📞 Support**

- **Render Docs**: https://render.com/docs
- **Django Docs**: https://docs.djangoproject.com
- **GitHub Issues**: https://github.com/Sulthanakthar/smartspend/issues

---

## **🎉 Congratulations!**

Your SmartSpend application is now live and accessible worldwide! 🌍

**Your Production URL:**
```
https://smartspend.onrender.com
```

Share this with your team and start tracking expenses! 💰
