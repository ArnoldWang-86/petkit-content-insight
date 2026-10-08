// probe.js —— 环境自检：确认能连上 B站公开接口（带重试，避免网络偶发抖动误报）
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function tryOnce() {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 15000);
  try {
    const r = await fetch('https://api.bilibili.com/x/web-interface/nav', { signal: ctrl.signal, headers: { 'User-Agent': UA } });
    const j = await r.json();
    return !!(j && j.data);
  } catch (e) {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

(async () => {
  const MAX = 4;
  for (let i = 1; i <= MAX; i++) {
    if (await tryOnce()) {
      console.log('B站接口连通（第 ' + i + ' 次尝试），wbi 签名素材可用');
      process.exit(0);
    }
    if (i < MAX) { console.log('第 ' + i + ' 次连接失败，' + (i * 2) + ' 秒后重试 ...'); await sleep(i * 2000); }
  }
  console.log('连续 ' + MAX + ' 次连接失败');
  process.exit(1);
})();
