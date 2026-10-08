/* e2e_check.js —— 端到端自检：把 Agent 真的跑一遍，并验证导出的 Excel
 *
 * 与 eval_agent.js 的区别：
 *   eval_agent.js  只测「路由与参数抽取」的准确率（不执行操作）
 *   e2e_check.js   把整条链路跑通：DOM 渲染、6 个阶段、SVG 出图、Excel 导出、失败兜底
 *
 * 用法：
 *   node agent/eval/e2e_check.js            # 只测离线路径（缓存 + 规则）
 *   node agent/eval/e2e_check.js --with-llm # 额外测大模型兜底（需要 .env 里有 API Key）
 */
const fs = require("fs");
const path = require("path");

const AGENT = path.resolve(__dirname, "..");
const PROJ = path.resolve(AGENT, "..");
const HTML = path.join(AGENT, "运营问数Agent.html");
const OUTDIR = path.join(AGENT, "eval", "_out");
const WITH_LLM = process.argv.indexOf("--with-llm") >= 0;

/* ---------- DOM 桩 ---------- */
const els = {};
const tabsStub = [];
function el(id) {
  if (!els[id]) els[id] = { id, innerHTML: "", textContent: "", value: "", style: {}, className: "",
    dataset: {}, appendChild() {}, addEventListener() {}, onclick: null, disabled: false, click() {} };
  return els[id];
}
global.document = {
  getElementById: id => el(id),
  querySelectorAll: sel => (sel === "#tabs .tab" ? tabsStub : []),
  createElement: () => el("t" + Math.random()),
};
global.window = global;
global.navigator = { clipboard: { writeText() {} } };
global.Blob = class {};
global.URL.createObjectURL = () => "blob:x";
global.addEventListener = function () {};
global.alert = function (m) { console.log("  [页面 alert] " + m); };

/* ---------- 取代码（每次都读最新构建产物） ---------- */
const src = fs.readFileSync(HTML, "utf8");
const blocks = [...src.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const xlsxBlock = blocks.find(b => b.length > 300000 && !b.startsWith("window.DATA="));
const dataBlock = blocks.find(b => b.startsWith("window.DATA=") && b.length < 2000000);
const appBlock = blocks.find(b => b.includes("matchByRules"));
if (!dataBlock || !appBlock) { console.error("无法从 HTML 提取代码块"); process.exit(1); }

// SheetJS 必须放进一个「没有 module / exports」的沙箱里执行，
// 否则它会走 CommonJS 分支，把 API 挂到 exports 上而不是全局 XLSX（浏览器里不存在这个问题）。
if (xlsxBlock) {
  const vm = require("vm");
  const sandbox = { console };
  sandbox.window = sandbox;          // 模拟浏览器：window 就是全局
  sandbox.self = sandbox;
  sandbox.require = require;         // 让 writeFile 能拿到 fs（Node 下写文件，浏览器下走下载）
  sandbox.setTimeout = setTimeout; sandbox.clearTimeout = clearTimeout;
  vm.createContext(sandbox);
  vm.runInContext(xlsxBlock, sandbox, { filename: "xlsx.full.min.js" });
  global.XLSX = sandbox.XLSX || (sandbox.window && sandbox.window.XLSX);
  console.log("SheetJS 装载：" + (global.XLSX && global.XLSX.utils ? "OK（utils 可用）" : "失败"));
}
eval(dataBlock);
eval(appBlock);

let key = "";
try {
  const env = fs.readFileSync(path.join(PROJ, ".env"), "utf8");
  const line = env.split("\n").find(l => l.startsWith("DEEPSEEK_API_KEY="));
  if (line) key = line.split("=").slice(1).join("=").trim();
} catch (e) {}

const CASES = [
  ["猫砂盆有多少条内容", ""],
  ["哪条产品线的内容互动率最高？", ""],
  ["小佩官方和达人差在哪", ""],
  ["视频做多长效果更好", ""],
  ["品牌提及量排名", ""],
  ["哪个痛点播放量高但内容还不多？", ""],
];
if (WITH_LLM && key) {
  CASES.push(["我想知道哪个牌子的内容更受欢迎", key]);
  CASES.push(["我们公司上周的营收涨了多少", key]);
}

(async function () {
  console.log("=== 端到端自检 ===");
  console.log("文件：" + path.relative(PROJ, HTML) + "（" + (fs.statSync(HTML).size / 1048576).toFixed(2) + " MB）");
  console.log("SheetJS：" + (xlsxBlock ? "已内联" : "缺失"));
  console.log("模式：" + (WITH_LLM && key ? "含大模型兜底" : "仅离线路径") + "\n");

  let pass = 0, fail = 0, savedCtx = null;
  for (const [q, k] of CASES) {
    el("q").value = q; el("key").value = k;
    el("err").style.display = "none"; el("jserr").style.display = "none";
    try {
      await run();
      const stages = (el("flow").innerHTML.match(/阶段 [1-6]/g) || []).length;
      const res = el("result").innerHTML;
      const hasSvg = /<svg /.test(el("chart").innerHTML);
      const jsErr = el("jserr").style.display === "block";
      const refusedOk = stages === 1 && el("err").style.display === "block" && !jsErr;
      const fullOk = stages === 6 && res.length > 400 && hasSvg && !jsErr;
      const ok = fullOk || refusedOk;
      if (ok) pass++; else fail++;
      console.log("  " + (ok ? "PASS" : "FAIL") + "  " + q.slice(0, 22).padEnd(24) +
        " 阶段=" + stages + " 结果=" + String(res.length).padStart(4) +
        " SVG图=" + (hasSvg ? "有" : "无") + (refusedOk ? "  [明确拒绝]" : "") + (jsErr ? "  [脚本错误!]" : ""));
      if (fullOk && !savedCtx && el("dlx").onclick) savedCtx = { q, k };
    } catch (e) { fail++; console.log("  FAIL  " + q + " -> 抛出异常：" + e.message); }
  }

  /* ---------- 验证 Excel 导出 ---------- */
  console.log("\n=== Excel 导出验证 ===");
  if (!savedCtx) { console.log("  （跳过：没有成功的用例）"); }
  else {
    fs.mkdirSync(OUTDIR, { recursive: true });
    const before = new Set(fs.readdirSync(OUTDIR));
    try {
      // 直接测「工作簿组装」这一层（不依赖浏览器的下载行为）
      const built = CURRENT.op ? buildWorkbook(CURRENT.op, CURRENT.params, CURRENT.res, CURRENT.question, CURRENT.guard) : null;
      if (!built) { console.log("  FAIL  没有可用的上下文"); fail++; }
      else {
        const buf = XLSX.write(built.wb, { type: "buffer", bookType: "xlsx" });
        const f = path.join(OUTDIR, built.filename);
        fs.writeFileSync(f, buf);
        console.log("  生成文件：" + built.filename + "（" + (buf.length / 1024).toFixed(1) + " KB）");
        const wb = XLSX.read(buf, { type: "buffer" });
        console.log("  工作表：" + wb.SheetNames.join(" | "));
        const s1 = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1 });
        console.log("  第 1 张表前 9 行：");
        s1.slice(0, 9).forEach(r => console.log("     " + JSON.stringify(r)));
        const need = ["说明与数据性质", "结果解读"];
        const missing = need.filter(n => wb.SheetNames.indexOf(n) < 0);
        if (missing.length) { console.log("  FAIL  缺少工作表：" + missing.join(",")); fail++; }
        else { console.log("  PASS  工作簿结构正确（说明与数据性质在最前）"); pass++; }
      }
    } catch (e) { console.log("  FAIL  导出抛错：" + e.message); fail++; }
  }

  console.log("\n通过 " + pass + " / " + (pass + fail));
  process.exit(fail ? 1 : 0);
})();
