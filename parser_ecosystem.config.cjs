module.exports = {
  apps: [
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
    }
  ]
}
