module.exports = {
  apps: [
    {
      name: 'nplace-demo',
      script: 'python3',
      args: '-m http.server 3000',
      cwd: '/home/user/nplace-project/frontend',
      env: {
        NODE_ENV: 'production'
      },
      watch: false,
      instances: 1,
      exec_mode: 'fork'
    },
    {
      name: 'nplace-parser-api',
      script: 'python3',
      args: '-m uvicorn parser_api:app --host 0.0.0.0 --port 8000',
      cwd: '/home/user/nplace-project/parser',
      env: {
        NODE_ENV: 'production',
      },
      watch: false,
      instances: 1,
      exec_mode: 'fork'
    },
    {
      name: 'nplace-backend',
      script: 'python3',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload',
      cwd: '/home/user/nplace-project/backend',
      env: {
        NODE_ENV: 'production',
      },
      watch: false,
      instances: 1,
      exec_mode: 'fork'
    }
  ]
}
