#!/bin/bash
# EC2 Initial Setup Script for Ubuntu
# Run this once on your EC2 instance to set up the environment

set -e

echo "🚀 Setting up Quitemailingyourself on EC2..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv git nginx

# Install Node.js and PM2 for process management
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2

# Clone repository (you'll need to set up SSH key or use HTTPS with token)
cd /home/ubuntu
git clone https://github.com/marksher/quitemailingyourself.git
cd quitemailingyourself

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Create .env file (you'll need to fill this with your actual values)
cat > .env << EOF
# Database
DATABASE_URL=sqlite:///./app.db

# OpenAI (optional)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Google OAuth (required for auth)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# App settings
APP_TITLE=Pocketish
SECRET_KEY=$(openssl rand -hex 32)
BASE_URL=http://your-ec2-public-ip:8000

# Worker settings
WORKER_INTERVAL_SEC=2.0
EOF

echo "⚠️  IMPORTANT: Edit /home/ubuntu/quitemailingyourself/.env with your actual values!"

# Set up Nginx (optional - for production with SSL)
sudo tee /etc/nginx/sites-available/quitemailingyourself << EOF
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit /home/ubuntu/quitemailingyourself/.env with your actual values"
echo "2. Set up your GitHub secrets (see README)"
echo "3. Enable Nginx: sudo ln -s /etc/nginx/sites-available/quitemailingyourself /etc/nginx/sites-enabled/"
echo "4. Test Nginx: sudo nginx -t && sudo systemctl reload nginx"
echo "5. Start the app: pm2 start ecosystem.config.js"
echo "6. Save PM2 config: pm2 save && pm2 startup"
echo ""
echo "Your app will be available at http://your-ec2-public-ip:8000"