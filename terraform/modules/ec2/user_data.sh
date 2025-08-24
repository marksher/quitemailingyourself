#!/bin/bash
# User data script for Quitemailingyourself EC2 instance

set -e

# Log all output
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "Starting user data script for ${project_name}-${environment}"

# Update system
apt-get update -y
apt-get upgrade -y

# Install required packages
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    nginx \
    curl \
    unzip \
    htop

# Install Node.js and PM2
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs
npm install -g pm2

# Create ubuntu user directories if they don't exist
mkdir -p /home/ubuntu
chown ubuntu:ubuntu /home/ubuntu

# Set up PM2 to start on boot
sudo -u ubuntu pm2 startup systemd -u ubuntu --hp /home/ubuntu
systemctl enable pm2-ubuntu

echo "User data script completed successfully"