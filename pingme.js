const axios = require("axios");
const crypto = require("crypto");

/**
 * =========================
 * 代理池（自动切换）
 * =========================
 */
const PROXIES = [
  "https://proxy.showlo.gv.uy/?url=",
  "https://proxy2.showlo.gv.uy/?url="
];

function proxyUrl(url, index = 0) {
  return PROXIES[index] + encodeURIComponent(url);
}

/**
 * =========================
 * 配置
 * =========================
 */
const SECRET = "0fOiukQq7jXZV2GRi9LGlO";
const API_HOST = "api.pingmeapp.net";

const MAX_VIDEO = 5;
const ACCOUNT_GAP = 3000;

/**
 * =========================
 * 工具
 * =========================
 */
function md5(str) {
  return crypto.createHash("md5").update(str).digest("hex");
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// 随机延迟（反风控核心）
function randomSleep(min = 3000, max = 9000) {
  const t = Math.floor(Math.random() * (max - min) + min);
  return sleep(t);
}

/**
 * =========================
 * 风控判断（关键）
 * =========================
 */
function isBlocked(data) {
  const msg = (data?.retmsg || "").toLowerCase();
  return (
    msg.includes("验证码") ||
    msg.includes("captcha") ||
    msg.includes("verify") ||
    msg.includes("图形") ||
    msg.includes("challenge")
  );
}

// 👉 判断是否“被降权（0收益）”
function isZeroReward(data) {
  const bonus = data?.result?.bonus;

  // 明确 0 或 null 或 undefined
  return bonus === 0 || bonus === "0" || bonus == null;
}

/**
 * =========================
 * 签名
 * =========================
 */
function getUTCSignDate() {
  const now = new Date();
  const pad = n => String(n).padStart(2, "0");

  return `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())} ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())}`;
}

function buildSignedParamsRaw(account) {
  const params = {};

  Object.keys(account.paramsRaw || {}).forEach(k => {
    if (k !== "sign" && k !== "signDate") {
      params[k] = account.paramsRaw[k];
    }
  });

  params.signDate = getUTCSignDate();

  const signBase = Object.keys(params)
    .sort()
    .map(k => `${k}=${params[k]}`)
    .join("&");

  params.sign = md5(signBase + SECRET);

  return params;
}

function buildUrl(path, account) {
  const params = buildSignedParamsRaw(account);

  const qs = Object.keys(params)
    .map(k => `${k}=${encodeURIComponent(params[k])}`)
    .join("&");

  return `https://${API_HOST}/app/${path}?${qs}`;
}

function buildHeaders(account) {
  return {
    Host: API_HOST,
    Accept: "application/json",
    "User-Agent": account.headers?.["User-Agent"] || "PingMe/1.9.3"
  };
}

/**
 * =========================
 * 请求（双proxy）
 * =========================
 */
async function fetchApi(path, account) {
  const rawUrl = buildUrl(path, account);
  const headers = buildHeaders(account);

  for (let i = 0; i < PROXIES.length; i++) {
    const url = proxyUrl(rawUrl, i);

    try {
      const res = await axios.get(url, {
        headers,
        timeout: 20000
      });

      return res.data;
    } catch (e) {
      console.log(`⚠️ Proxy${i + 1} fail`);
    }
  }

  return {
    retcode: -1,
    retmsg: "all proxy failed"
  };
}

/**
 * =========================
 * 单账号执行
 * =========================
 */
async function runAccount(account, index, total) {
  const tag = `[账号${index + 1}/${total}]`;
  const msgs = [tag];

  console.log(`\n===== ${tag} START =====\n`);

  let data = await fetchApi("queryBalanceAndBonus", account);
  msgs.push(`💰 余额：${data?.result?.balance || 0}`);

  data = await fetchApi("checkIn", account);
  msgs.push(`签到：${data?.retmsg || "ok"}`);

  let blockedVideo = false;

  for (let i = 1; i <= MAX_VIDEO; i++) {
    await randomSleep();

    data = await fetchApi("videoBonus", account);

    // ❌ 风控直接停止
    if (isBlocked(data)) {
      msgs.push(`⛔ 视频${i}：触发风控，停止`);
      blockedVideo = true;
      break;
    }

    // ❌ 0收益判断（核心）
    if (isZeroReward(data)) {
      msgs.push(`⚠️ 视频${i}：0收益（疑似降权）`);
      blockedVideo = true;
      break;
    }

    msgs.push(`🎬 视频${i}：+${data?.result?.bonus}`);
  }

  if (blockedVideo) {
    msgs.push("⚠️ 当前账号处于低收益/风控状态");
  }

  data = await fetchApi("queryBalanceAndBonus", account);
  msgs.push(`💰 最新余额：${data?.result?.balance || 0}`);

  console.log(msgs.join("\n"));

  return msgs.join("\n");
}

/**
 * =========================
 * 主函数
 * =========================
 */
async function main() {
  const accounts = [
    process.env.PINGME_DATA_1
  ]
    .filter(Boolean)
    .map(x => {
      try {
        return JSON.parse(x);
      } catch {
        return null;
      }
    })
    .filter(Boolean);

  if (!accounts.length) {
    console.log("no account");
    return;
  }

  for (let i = 0; i < accounts.length; i++) {
    await runAccount(accounts[i], i, accounts.length);

    if (i < accounts.length - 1) {
      await sleep(ACCOUNT_GAP);
    }
  }

  console.log("\nDONE");
}

main();
