/* e2e_check.js —— 端到端自检：真的调用大模型，把整条链路跑一遍
 *
 * 用的是「本机演示版」（已内嵌 Key）。
 * 检查项：6 个阶段是否跑完、是否出 SVG 图、结果表是否有内容、
 *         口径守卫是否生效、Excel 工作簿结构是否正确。
 *
 * 用法： node agent/eval/e2e_check.js
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const AGENT = path.resolve(__dirname, "..");
const PROJ = path.resolve(AGENT, "..");
const HTML = path.join(AGENT, "问数Agent_本机演示.html");
const OUTDIR = path.join(__dirname, "_out");

if (!fs.existsSync(HTML)) { console.error("找不到 " + HTML + "，请先运行 python agent/src/build_agent.py"); process.exit(1); }

/* ---------- DOM 桩 ---------- */
const els = {};
const tabsStub = [];
function el(id) {
  if (!els[id]) els[id] = { id, innerHTML: "", textContent: "", value: "", style: {}, className: "",
    dataset: {}, appendChild() {}, addEventListener() {}, onclick: null, disabled: false, click() {} };
  return els[id];
}
global.document = { getElementById: id => el(id), querySelectorAll: s => (s === "#tabs .tab" ? tabsStub : []),
                    createElement: () => el("t" + Math.random()) };
global.window = global;
global.navigator = { clipboard: { writeText() {} } };
global.Blob = class {};
global.URL.createObjectURL = () => "blob:x";     // 不要覆盖 URL 本身
global.addEventListener = function () {};
global.alert = m => console.log("  [页面 alert] " + m);

/* ---------- 取代码 ---------- */
const src = fs.readFileSync(HTML, "utf8");
const blocks = [...src.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const xlsxBlock = blocks.find(b => b.length > 300000 && !b.startsWith("window.DATA="));
const keyBlock = blocks.find(b => b.indexOf("DEFAULT_KEY") >= 0);
const dataBlock = blocks.find(b => b.startsWith("window.DATA=") && b.length < 2000000);
const appBlock = blocks.find(b => b.includes("planPrompt"));
if (!dataBlock || !appBlock) { console.error("无法提取代码块"); process.exit(1); }

// SheetJS 必须放进「没有 module / exports」的沙箱，否则它走 CommonJS 分支
const sandbox = { console }; sandbox.window = sandbox; sandbox.self = sandbox; sandbox.require = require;
vm.createContext(sandbox);
vm.runInContext(xlsxBlock, sandbox, { filename: "xlsx.full.min.js" });
global.XLSX = sandbox.XLSX;
if (keyBlock) eval(keyBlock);
eval(dataBlock);
eval(appBlock);

const KEY = (typeof DEFAULT_KEY === "string" && DEFAULT_KEY) ? DEFAULT_KEY : "";

const CASES = [
  "哪条产品线的内容互动率最高？",
  "小佩和竞品的官方内容效率差多少？",
  "哪个痛点播放量高但内容还不多？",
  "内容量这几年是怎么变的？"
];

(async function () {
  console.log("=== 问数 Agent · 端到端自检（真实调用大模型）===");
  console.log("文件：" + path.relative(PROJ, HTML) + "（" + (fs.statSync(HTML).size / 1048576).toFixed(2) + " MB）");
  console.log("SheetJS：" + (global.XLSX && global.XLSX.utils ? "OK" : "缺失") + " | Key：" + (KEY ? "已内嵌" : "缺失") + "\n");
  if (!KEY) { console.log("没有 Key，无法测试"); process.exit(1); }

  let pass = 0, fail = 0;
  for (const q of CASES) {
    el("q").value = q; el("key").value = KEY;
    el("err").style.display = "none"; el("jserr").style.display = "none";
    const t0 = Date.now();
    try {
      await run();
      const stages = (el("flow").innerHTML.match(/阶段 [1-6]/g) || []).length;
      const hasSvg = /<svg /.test(el("chart").innerHTML);
      const hasTable = /<table>/.test(el("tbl").innerHTML) || /insight/.test(el("tbl").innerHTML);
      const jsErr = el("jserr").style.display === "block";
      const errShown = el("err").style.display === "block";
      const rows = CURRENT && CURRENT.res ? CURRENT.res.rows.length : -1;
      const groups = CURRENT && CURRENT.res ? CURRENT.res.table.length : -1;
      const ok = stages === 6 && hasSvg && hasTable && !jsErr && !errShown && rows > 0 && groups > 0;
      if (ok) pass++; else fail++;
      console.log("  " + (ok ? "PASS" : "FAIL") + "  " + q.slice(0, 20).padEnd(22) +
        " 阶段=" + stages + " 命中=" + String(rows).padStart(4) + " 组=" + String(groups).padStart(3) +
        " SVG=" + (hasSvg ? "有" : "无") + " 表=" + (hasTable ? "有" : "无") +
        " (" + ((Date.now() - t0) / 1000).toFixed(1) + "s)" +
        (errShown ? "  [错误]" : "") + (jsErr ? " [脚本错误]" : ""));
      if (!ok) console.log("        错误框：" + el("err").textContent.slice(0, 160));
    } catch (e) { fail++; console.log("  FAIL  " + q + " -> " + e.message); }
  }

  /* ---------- Excel 工作簿 ---------- */
  console.log("\n=== Excel 导出验证 ===");
  fs.mkdirSync(OUTDIR, { recursive: true });
  try {
    const built = buildWorkbook(CURRENT);
    const buf = XLSX.write(built.wb, { type: "buffer", bookType: "xlsx" });
    fs.writeFileSync(path.join(OUTDIR, built.filename), buf);
    const wb = XLSX.read(buf, { type: "buffer" });
    console.log("  文件：" + built.filename + "（" + (buf.length / 1024).toFixed(1) + " KB）");
    console.log("  工作表：" + wb.SheetNames.join(" | "));
    const need = ["说明与数据性质", "AI 解读", "查询与口径", "结果表"];
    const missing = need.filter(n => wb.SheetNames.indexOf(n) < 0);
    if (missing.length) { console.log("  FAIL 缺少工作表：" + missing.join(",")); fail++; }
    else { console.log("  PASS 工作簿结构正确"); pass++; }
    const s1 = XLSX.utils.sheet_to_json(wb.Sheets["说明与数据性质"], { header: 1 });
    console.log("  第 1 张表前 8 行：");
    s1.slice(0, 8).forEach(r => console.log("     " + JSON.stringify(r)));
  } catch (e) { console.log("  FAIL 导出异常：" + e.message); fail++; }

  console.log("\n通过 " + pass + " / " + (pass + fail));
  process.exit(fail ? 1 : 0);
})();
