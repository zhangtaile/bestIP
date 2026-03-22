export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // 1. 专门用于端到端延迟测速的轻量级响应
    // 我们的 python 脚本将会向这个路径发送 GET 请求来测试延迟
    if (url.pathname === '/ping') {
      return new Response('pong', { 
        status: 200,
        headers: { 'Content-Type': 'text/plain' }
      });
    }

    // 2. 这里是你原有的 VLESS/WS 代理逻辑
    // 例如：
    // const upgradeHeader = request.headers.get('Upgrade');
    // if (upgradeHeader === 'websocket') { 
    //   ... vless 逻辑 ... 
    // }

    // 如果既不是 ping 也不是 websocket 升级请求，返回一个默认页面
    return new Response('VLESS Worker is running.', { status: 200 });
  }
};
