module.exports = {
  apps: [
    {
      name: 'quitemailingyourself',
      script: 'uvicorn',
      args: 'backend.app:app --host 0.0.0.0 --port 8000',
      interpreter: 'python',
      cwd: '/home/ubuntu/quitemailingyourself',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/ubuntu/quitemailingyourself'
      },
      error_file: './logs/app-error.log',
      out_file: './logs/app-out.log',
      log_file: './logs/app-combined.log',
      time: true
    },
    {
      name: 'quitemailingyourself-worker',
      script: 'worker/worker.py',
      interpreter: 'python',
      cwd: '/home/ubuntu/quitemailingyourself',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/ubuntu/quitemailingyourself'
      },
      error_file: './logs/worker-error.log',
      out_file: './logs/worker-out.log',
      log_file: './logs/worker-combined.log',
      time: true
    }
  ]
};