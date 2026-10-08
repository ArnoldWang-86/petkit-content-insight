/* eval_agent.js —— 评测「问数 Agent」的路由与参数抽取准确率
 *
 * 为什么这个评测重要
 * ------------------
 * 不做评测的 demo 只能"看起来能跑"。这里用一组业务问题当测试集，
 * 量出「规则路径」的意图识别准确率与参数准确率，剩下的才交给大模型兜底。
 *
 * 用法： node agent/eval/eval_agent.js
 */
const fs = require("fs");
const path = require("path");

const AGENT = path.resolve(__dirname, "..");
const HTML = path.join(AGENT, "运营问数Agent.html");
const QS = JSON.parse(fs.readFileSync(path.join(__dirname, "questions.json"), "utf8"));

const src = fs.readFileSync(HTML, "utf8");
const blocks = [...src.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const dataBlock = blocks.find(b => b.startsWith("window.DATA=") && b.length < 2000000);
const appBlock = blocks.find(b => b.includes("matchByRules"));
if (!dataBlock || !appBlock) { console.error("无法从 HTML 中提取数据/逻辑块"); process.exit(1); }

function el() { return { innerHTML: "", textContent: "", style: {}, dataset: {},
  appendChild() {}, addEventListener() {}, onclick: null }; }
global.document = { getElementById: () => el(), querySelectorAll: () => [], createElement: () => el() };
global.window = global; global.Plotly = { newPlot() {} };
global.navigator = { clipboard: { writeText() {} } };
global.Blob = class {}; global.URL = { createObjectURL: () => "b" };

eval(dataBlock);
eval(appBlock);

let intentOk = 0, paramOk = 0, both = 0, fromCache = 0;
const rows = [];
QS.forEach(item => {
  const cached = findCached(item.q);
  const route = cached ? { op: findOp(cached.op), params: cached.params || {}, score: "-" } : matchByRules(item.q);
  let got = "-", okI = false, okP = false;
  if (route && route.op) {
    got = route.op.id;
    okI = (got === item.op);
    const ex = cached ? { params: Object.assign({}, route.params) } : extractParams(route.op, item.q);
    const params = Object.assign({}, ex.params);
    okP = true;
    for (const k in (item.params || {})) if (params[k] !== item.params[k]) okP = false;
    if (okI && (!item.params || !Object.keys(item.params).length)) okP = true;
  }
  if (cached) fromCache++;
  if (okI) intentOk++;
  if (okP) paramOk++;
  if (okI && okP) both++;
  rows.push({ q: item.q, want: item.op, got: got, ok: okI && okP, via: cached ? "缓存" : "规则" });
});

console.log("=== 问数 Agent · 路由评测（离线规则路径）===");
console.log("测试集：" + QS.length + " 条业务问题\n");
const w = Math.max(...rows.map(r => r.q.length)) + 2;
rows.forEach(r => {
  console.log("  " + (r.ok ? "PASS" : "FAIL") + "  " + r.q.padEnd(w) +
              " 期望=" + r.want.padEnd(16) + " 实际=" + r.got + "  [" + r.via + "]");
});
console.log("");
console.log("  意图识别准确率  : " + intentOk + "/" + QS.length + " = " + (intentOk / QS.length * 100).toFixed(1) + "%");
console.log("  参数抽取准确率  : " + paramOk + "/" + QS.length + " = " + (paramOk / QS.length * 100).toFixed(1) + "%");
console.log("  端到端正确率    : " + both + "/" + QS.length + " = " + (both / QS.length * 100).toFixed(1) + "%");
console.log("  其中命中预置缓存: " + fromCache + "/" + QS.length);
console.log("");
console.log("  说明：这是**离线规则路径**的准确率（不调大模型）。");
console.log("        规则未命中的问题会交给大模型做意图识别，因此线上覆盖面高于此数。");
