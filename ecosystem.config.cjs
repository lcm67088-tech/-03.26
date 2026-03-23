module.exports = {
  apps: [
    {
      name: 'nplace-demo',
      script: 'python3',
      args: '-m http.server 3000',
      cwd: '/home/user/nplace-project/frontend_html',
      env: {
        NODE_ENV: 'production'
      },
      watch: false,
      instances: 1,
      exec_mode: 'fork'
    }
  ]
}
