// 文件路径：pingme.js

/**
 * PingMe GitHub Actions版自动签到 + 视频奖励 + TG通知
 *
 * Secrets：
 * PINGME_DATA_1
 * PINGME_DATA_2
 * PINGME_DATA_3
 * PINGME_DATA_4
 * PINGME_DATA_5
 *
 * TG_BOT_TOKEN
 * TG_USER_ID
 */

const axios = require("axios");
const crypto = require("crypto");

const SECRET = "0fOiukQq7jXZV2GRi9LGlO";
const API_HOST = "api.pingmeapp.net";

// 👉 代理入口（新增：仅这一处变化）
const PROXY = "http://proxy.showlo.gv.uy/?url=";

const MAX_VIDEO = 5;
const VIDEO_DELAY = 8000;
const ACCOUNT_GAP = 3500;

const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN || "";
const TG_USER_ID = process.env.TG_USER_ID || "";

function md5(str) {
  return crypto.createHash("md5").update(str).digest("hex");
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

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

// 👉 只动这里：走 CF Worker
function proxyUrl(url) {
  return PROXY + encodeURIComponent(url);
}

function buildHeaders(account) {
  return {
    Host: API_HOST,
    Accept: "application/json",
    "Accept-Language": "zh-Hans-CN;q=1.0",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent":
      account.headers?.["User-Agent"] || "PingMe/1.9.3"
  };
}

async function fetchApi(path, account) {
  const rawUrl = buildUrl(path, account);

  // 👉 关键修改点：全部走 Cloudflare Worker
  const url = proxyUrl(rawUrl);

  const headers = buildHeaders(account);

  try {
    const resp = await axios.get(url, {
      headers,
      timeout: 20000
    });

    return resp.data;
  } catch (e) {
    return {
      retcode: -1,
      retmsg: e.message || "请求失败"
    };
  }
}

async function sendTG(title, content) {
  if (!TG_BOT_TOKEN || !TG_USER_ID) {
    console.log("未配置 TG 推送");
    return;
  }

  const url = `https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`;

  try {
    await axios.post(
      url,
      {
        chat_id: TG_USER_ID,
        text: `${title}\n\n${content}`,
        parse_mode: "HTML",
        disable_web_page_preview: true
      },
      {
        timeout: 20000
      }
    );

    console.log("✅ TG推送成功");
  } catch (e) {
    console.log("❌ TG推送失败：" + (e.message || e));
  }
}

async function runAccount(account, index, total) {
  const tag = `[账号${index + 1}/${total} ${account.alias || "未命名"}]`;
  const msgs = [tag];

  console.log(`\n========== ${tag} 开始 ==========\n`);

  let data = await fetchApi("queryBalanceAndBonus", account);

  if (data.retcode === 0) {
    msgs.push(`💰 当前余额：${data.result?.balance || 0} Coins`);
  } else {
    msgs.push(`⚠️ 查询失败：${data.retmsg}`);
  }

  data = await fetchApi("checkIn", account);

  if (data.retcode === 0) {
    msgs.push(
      `✅ 签到成功：${
        (data.result?.bonusHint || data.retmsg || "").replace(/\n/g, " ")
      }`
    );
  } else {
    msgs.push(`⚠️ 签到状态：${data.retmsg}`);
  }

  for (let i = 1; i <= MAX_VIDEO; i++) {
    if (i > 1) {
      await sleep(VIDEO_DELAY);
    }

    data = await fetchApi("videoBonus", account);

    if (data.retcode === 0) {
      msgs.push(`🎬 视频${i}：+${data.result?.bonus || "?"} Coins`);
    } else {
      msgs.push(`⏸ 视频${i}：${data.retmsg}`);
      break;
    }
  }

  data = await fetchApi("queryBalanceAndBonus", account);

  if (data.retcode === 0) {
    msgs.push(`💰 最新余额：${data.result?.balance || 0} Coins`);
  }

  console.log(msgs.join("\n"));
  console.log(`\n========== ${tag} 结束 ==========\n`);

  return msgs.join("\n");
}

async function main() {
  const accounts = [
    process.env.PINGME_DATA_1,
    process.env.PINGME_DATA_2,
    process.env.PINGME_DATA_3,
    process.env.PINGME_DATA_4,
    process.env.PINGME_DATA_5
  ]
    .filter(Boolean)
    .map(item => {
      try {
        return JSON.parse(item);
      } catch {
        return null;
      }
    })
    .filter(Boolean);

  if (!accounts.length) {
    console.log("❌ 没有可执行账号");
    return;
  }

  const results = [];

  for (let i = 0; i < accounts.length; i++) {
    const result = await runAccount(accounts[i], i, accounts.length);
    results.push(result);

    if (i < accounts.length - 1) {
      await sleep(ACCOUNT_GAP);
    }
  }

  const finalMsg = results.join("\n————————————\n");

  console.log("\n==============================");
  console.log("🎉 全部任务执行完成");
  console.log("==============================\n");

  console.log(finalMsg);

  await sendTG("🎉 PingMe 签到完成", finalMsg);
}

main();
