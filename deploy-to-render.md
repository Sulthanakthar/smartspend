# SmartSpend - Render Deployment Guide

## Quick Deployment Steps

### 1. Create Required Services on Render

#### PostgreSQL Database
1. Go to [render.com](https://render.com)
2. Click **"New +"** → **"PostgreSQL"**
3. Fill in:
   - **Name**: `smartspend-db`
   - **Database**: `smartspend`
   - **User**: `smartspend_user`
   - **Plan**: Free tier
4. Note the **Internal Database URL** (you'll need this)

#### Redis Cache
1. Click **"New +"** → **"Redis"**
2. Fill in:
   - **Name**: `smartspend-redis`
   - **Plan**: Free tier
3. Note the **Internal Redis URL**

### 2. Deploy the Web Service

1. Click **"New +"** → **"Web Service"**
2. **Connect GitHub**:
   - Click "Connect account"
   - Select `Sulthanakthar/smartspend`
3. **Configure**:
   - **Name**: `smartspend`
   - **Environment**: Docker
   - **Plan**: Free tier
4. **Add Environment Variables**:
   ```
   DEBUG=False
   ALLOWED_HOSTS=smartspend.onrender.com,localhost
   SECRET_KEY=(Render auto-generates this)
   DATABASE_URL=postgresql://<user>:<password>@<db-host>:5432/smartspend
   REDIS_URL=redis://<redis-host>:6379/0
   PORT=8000
   ```
   - Copy the PostgreSQL Internal URL to `DATABASE_URL`
   - Copy the Redis Internal URL to `REDIS_URL`
5. Click **"Create Web Service"**

### 3. Run Migrations

Once deployed, SSH into the service and run:
```bash
render exec smartspend -- python manage.py migrate
render exec smartspend -- python manage.py createsuperuser
```

### 4. Access Your App

Your application will be live at:
```
https://smartspend.onrender.com
```

## Troubleshooting

### Build Fails
- Check that `requirements.txt` has all dependencies
- Ensure `Dockerfile` references correct Python version

### Database Connection Errors
- Verify `DATABASE_URL` format: `postgresql://user:pass@host:5432/dbname`
- Check internal URLs match between services

### Static Files Not Loading
- Run: `python manage.py collectstatic --noinput`
- Verify `STATIC_ROOT` and `STATIC_URL` in settings

## Cost Estimates
- **Free Tier**: $0/month (limited to 750 hours)
- **Pro Tier**: Database ($7/month) + Redis ($7/month) + Web Service ($7/month) = ~$21/month

---

For support, visit [render.com/docs](https://render.com/docs)
