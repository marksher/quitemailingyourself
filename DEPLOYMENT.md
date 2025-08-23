# EC2 Deployment Guide

This guide will help you set up automated deployment to AWS EC2 using GitHub Actions.

## 🚀 Quick Setup

### 1. Launch EC2 Instance
- Launch an Ubuntu 22.04 EC2 instance (t2.micro works for testing)
- Configure security group to allow:
  - SSH (port 22) from your IP
  - HTTP (port 80) from anywhere (0.0.0.0/0)
  - Custom TCP (port 8000) from anywhere (for testing)
- Create or use an existing SSH key pair

### 2. Initial Server Setup
SSH into your EC2 instance and run:

```bash
# Make setup script executable and run it
wget https://raw.githubusercontent.com/marksher/quitemailingyourself/main/scripts/setup-ec2.sh
chmod +x setup-ec2.sh
./setup-ec2.sh
```

### 3. Configure Environment Variables
Edit the `.env` file on your server:

```bash
nano /home/ubuntu/quitemailingyourself/.env
```

Fill in your actual values:
```env
DATABASE_URL=sqlite:///./app.db
OPENAI_API_KEY=sk-your-actual-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
APP_TITLE=Pocketish
BASE_URL=http://your-ec2-public-ip:8000
```

### 4. Set up GitHub Secrets
In your GitHub repository, go to Settings → Secrets and variables → Actions, and add:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `EC2_HOST` | `your-ec2-public-ip` | EC2 instance public IP |
| `EC2_USER` | `ubuntu` | SSH username (ubuntu for Ubuntu instances) |
| `EC2_SSH_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----...` | Your SSH private key content |

To get your SSH private key:
```bash
cat ~/.ssh/your-key-name.pem
```

### 5. Test Manual Deployment
Start the application manually first:

```bash
cd /home/ubuntu/quitemailingyourself
source venv/bin/activate
pm2 start ecosystem.config.js
pm2 save
pm2 startup  # Follow the instructions this command gives you
```

Visit `http://your-ec2-public-ip:8000` to verify it works.

## 🔄 Automated Deployment

Once setup is complete, every push to `main` will automatically:

1. ✅ Connect to your EC2 instance via SSH
2. ✅ Pull the latest code from GitHub
3. ✅ Install/update Python dependencies
4. ✅ Restart the web app and worker processes
5. ✅ Verify deployment success

### Manual Deployment Trigger
You can also trigger deployment manually:
- Go to Actions tab in GitHub
- Click "Deploy to EC2"
- Click "Run workflow"

## 📊 Monitoring

Check application status on EC2:
```bash
pm2 status                    # See all processes
pm2 logs quitemailingyourself # View app logs
pm2 logs quitemailingyourself-worker # View worker logs
pm2 restart all               # Restart all processes
```

## 🔒 Production Considerations

### SSL/HTTPS Setup
For production, set up SSL with Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Environment Security
- Use AWS Systems Manager Parameter Store for secrets
- Set up IAM roles instead of storing keys
- Use RDS instead of SQLite for production
- Set up CloudWatch for monitoring

### Scaling
- Use Application Load Balancer
- Auto Scaling Groups
- RDS with read replicas
- ElastiCache for caching

## 🐛 Troubleshooting

**Deployment fails with SSH errors:**
- Check that EC2_SSH_KEY secret contains the entire private key
- Verify EC2_HOST is the correct public IP
- Ensure security group allows SSH from GitHub Actions IPs

**App won't start:**
- Check logs: `pm2 logs quitemailingyourself`
- Verify .env file has correct values
- Check Python dependencies: `pip install -r requirements.txt`

**Database issues:**
- Make sure app.db file has correct permissions
- Check if SQLite is installed: `sqlite3 --version`

## 📝 Files Created

- `.github/workflows/deploy.yml` - GitHub Actions workflow
- `ecosystem.config.js` - PM2 process configuration
- `scripts/setup-ec2.sh` - Initial server setup script
- `DEPLOYMENT.md` - This documentation