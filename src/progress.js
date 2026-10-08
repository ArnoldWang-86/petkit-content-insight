// progress.js —— 采集进度查看（只读，不修改任何数据）
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");
const RAW = path.join(ROOT, "data", "raw");
const OUT = path.join(RAW, "search_raw.jsonl");
const STATE = path.join(RAW, "_collect_state.json");

// 与 collect.js 保持一致的关键词表
const KEYWORDS = [
  "智能猫砂盆","自动猫砂盆","宠物饮水机","猫咪饮水机","自动喂食器","宠物喂食器",
  "宠物摄像头","宠物烘干箱","宠物烘干机","智能猫窝","宠物加热垫","自动铲屎机",
  "宠物智能","猫砂盆推荐","宠物自动厕所",
  "小佩宠物","PETKIT","霍曼宠物","CATLINK","catlink猫砂盆","小佩猫砂盆",
  "小米宠物","宠物智能品牌",
  "猫砂盆异味","猫咪不喝水","猫泌尿","猫毛满天飞","上班族养猫","出差喂猫",
  "猫砂盆怎么选","猫砂盆测评","宠物饮水机测评","养猫神器","养狗神器","宠物拆家",
];

const bar = (n, total, width) => {
  const w = Math.max(0, Math.min(width, Math.round(n / total * width)));
  return "[" + "#".repeat(w) + ".".repeat(width - w) + "]";
};

let done = [];
if (fs.existsSync(STATE)) { try { done = JSON.parse(fs.readFileSync(STATE, "utf8")).done || []; } catch (e) {} }
const doneSet = new Set(done);

let rows = 0, uniq = 0;
const perKw = {};
if (fs.existsSync(OUT)) {
  const seen = new Set();
  for (const line of fs.readFileSync(OUT, "utf8").split("\n")) {
    if (!line.trim()) continue;
    rows++;
    try {
      const r = JSON.parse(line);
      if (r.bvid) seen.add(r.bvid);
      perKw[r._keyword] = (perKw[r._keyword] || 0) + 1;
    } catch (e) {}
  }
  uniq = seen.size;
}

const pct = (done.length / KEYWORDS.length * 100);
console.log("关键词进度  " + bar(done.length, KEYWORDS.length, 34) + " " + done.length + "/" + KEYWORDS.length +
  "  (" + pct.toFixed(0) + "%)");
console.log("");
console.log("已采集行数  : " + rows);
console.log("唯一视频数  : " + uniq + "   <- 有效样本量");
if (rows > 0) console.log("去重比例    : " + ((1 - uniq / rows) * 100).toFixed(1) + "% （搜索接口跨词重复，属正常）");
console.log("");

console.log("--- 各关键词采集量 ---");
for (const kw of KEYWORDS) {
  const n = perKw[kw] || 0;
  const mark = doneSet.has(kw) ? "[完成]" : (n > 0 ? "[中断]" : "[待采]");
  console.log("  " + mark + " " + kw.padEnd(12, " ") + String(n).padStart(6) + " 行");
}
console.log("");

if (done.length < KEYWORDS.length) {
  const rest = KEYWORDS.filter(k => !doneSet.has(k));
  console.log("下一步：双击「一键采完剩余数据.bat」，一次采完剩余 " + rest.length + " 个关键词。");
  console.log("        预计耗时约 " + Math.ceil(rest.length * 4) + " 分钟，可随时关掉，下次接着采。");
} else {
  console.log("采集已全部完成！下一步：双击「3_清洗数据.bat」");
}
