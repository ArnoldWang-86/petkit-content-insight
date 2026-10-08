/* e2e_check.js —— 端到端自检：把 Agent 真的跑一遍
 *
 * 与 eval_agent.js 的区别：
 *   eval_agent.js  只测「路由与参数抽取」的准确率（不执行操作）
 *   e2e_check.js   把整条链路跑通：DOM 渲染、6 个阶段、图表、CSV 导出、失败兜底
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
const WITH_LLM = process.argv.indexOf("--with-llm") >= 0;

/* ---------- DOM 桩 ---------- */
const els = {};
function el(id) {
  if (!els[id]) els[id] = { id, innerHTML: "", textContent: "", value: "", style: {}, className: "",
    dataset: {}, appendChild() {}, addEventListener() {}, onclick: null, disabled: false, click() {} };
  return els[id];
}
global.document = { getElementById: id => el(id), querySelectorAll: () => [], createElement: () => el("t" + Math.random()) };
global.window = global;
global.Plotly = { newPlot(e, d, l) { global.__CHART = l.title.text; } };
global.navigator = { clipboard: { writeText() {} } };
global.Blob = class {};
global.URL.createObjectURL = () => "blob:x";   // 不要覆盖 URL 本身，否则 fetch 解析不了地址
global.addEventListener = function () {};

/* ---------- 从 HTML 里取代码（每次都读最新构建产物） ---------- */
const src = fs.readFileSync(HTML, "utf8");
const blocks = [...src.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const dataBlock = blocks.find(b => b.startsWith("window.DATA=") && b.length < 2000000);
const appBlock = blocks.find(b => b.includes("matchByRules"));
if (!dataBlock || !appBlock) { console.error("无法从 HTML 提取代码块"); process.exit(1); }
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
];
if (WITH_LLM && key) {
  CASES.push(["我想知道哪个牌子的内容更受欢迎", key]);   // 规则命中不了 → 走大模型
  CASES.push(["我们公司上周的营收涨了多少", key]);         // 应该被明确拒绝（超出范围）
}

(async function () {
  console.log("=== 端到端自检（读取最新构建的 HTML）===");
  console.log("文件：" + path.relative(PROJ, HTML) + "（" + (fs.statSync(HTML).size / 1048576).toFixed(2) + " MB）");
  console.log("模式：" + (WITH_LLM && key ? "含大模型兜底" : "仅离线路径（加 --with-llm 可测大模型）") + "\n");
  let pass = 0, fail = 0;
  for (const [q, k] of CASES) {
    el("q").value = q; el("key").value = k;
    global.__CHART = null; el("err").style.display = "none"; el("jserr").style.display = "none";
    try {
      await run();
      const stages = (el("flow").innerHTML.match(/阶段 [1-6]/g) || []).length;
      const res = el("result").innerHTML;
      const errShown = el("err").style.display === "block";
      const jsErr = el("jserr").style.display === "block";
      // 判定：要么完整跑完 6 阶段并出图；要么明确给出"答不了"的解释（且不是脚本错误）
      const fullOk = stages === 6 && res.length > 400 && !!global.__CHART && !jsErr;
      const refusedOk = stages === 1 && errShown && !jsErr && res.length > 60;
      const ok = fullOk || refusedOk;
      if (ok) pass++; else fail++;
      console.log("  " + (ok ? "PASS" : "FAIL") + "  " + q.slice(0, 22).padEnd(24) +
        " 阶段=" + stages + " 结果=" + String(res.length).padStart(4) +
        " 图=" + (global.__CHART ? "有" : "无") +
        (refusedOk ? "  [已明确拒绝]" : "") + (jsErr ? "  [脚本错误!]" : ""));
    } catch (e) { fail++; console.log("  FAIL  " + q + " -> 抛出异常：" + e.message); }
  }
  console.log("\n通过 " + pass + "/" + (pass + fail));
  process.exit(fail ? 1 : 0);
})();
