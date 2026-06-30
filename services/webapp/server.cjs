#!/usr/bin/env node
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const https = require('https');
const path = require('path');

const HOST = process.env.BETMAN_DATA_WEBAPP_HOST || '127.0.0.1';
const PORT = Number(process.env.BETMAN_DATA_WEBAPP_PORT || 18088);
const PUBLIC_HOST = process.env.BETMAN_DATA_PUBLIC_HOST || '';
const PUBLIC_PORT = Number(process.env.BETMAN_DATA_PUBLIC_PORT || 0);
const ROOT = process.env.BETMAN_DATA_WEBAPP_ROOT || '/opt/betman/betman_data/services/webapp/dist';
const API_HOST = process.env.BETMAN_DATA_API_HOST || '127.0.0.1';
const API_PORT = Number(process.env.BETMAN_DATA_API_PORT || 18086);
const API_AUTHORIZATION = process.env.API_PROXY_AUTHORIZATION || '';
const TLS_CERT = process.env.BETMAN_DATA_TLS_CERT || '';
const TLS_KEY = process.env.BETMAN_DATA_TLS_KEY || '';
const PASSWORD_SETUP_ORIGIN = process.env.BETMAN_PASSWORD_SETUP_ORIGIN || 'https://170.64.201.182';

const AUTH_USER = process.env.BETMAN_DATA_AUTH_USER || '';
const AUTH_PASSWORD = process.env.BETMAN_DATA_AUTH_PASSWORD || '';
const AUTH_SECRET = process.env.BETMAN_DATA_AUTH_SECRET || AUTH_PASSWORD || API_AUTHORIZATION || 'betman-data-dev-secret';
const AUTH_TOKEN_TTL_MS = Number(process.env.BETMAN_DATA_AUTH_TOKEN_TTL_MS || 8 * 60 * 60 * 1000);
const MAX_LOGIN_BODY_BYTES = 32 * 1024;

const TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

function sendJson(res, status, body) {
  res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
  res.end(JSON.stringify(body));
}

function proxyPasswordSetup(req, res) {
  if (req.method !== 'POST') {
    res.writeHead(405, { allow: 'POST', 'cache-control': 'no-store' });
    res.end();
    return;
  }

  const target = new URL('/api/password-setup-link', PASSWORD_SETUP_ORIGIN);
  const upstream = (target.protocol === 'https:' ? https : http).request({
    hostname: target.hostname,
    port: target.port || (target.protocol === 'https:' ? 443 : 80),
    method: 'POST',
    path: target.pathname,
    rejectUnauthorized: false,
    headers: {
      'content-type': req.headers['content-type'] || 'application/json',
      'x-forwarded-host': req.headers.host || '',
      'x-forwarded-proto': req.socket.encrypted ? 'https' : 'http',
    },
  }, (upstreamRes) => {
    res.writeHead(upstreamRes.statusCode || 502, {
      'content-type': upstreamRes.headers['content-type'] || 'application/json',
      'cache-control': 'no-store',
    });
    upstreamRes.pipe(res);
  });

  upstream.on('error', (error) => {
    sendJson(res, 502, {
      ok: false,
      error: 'password_setup_unavailable',
      message: error.message,
    });
  });

  req.pipe(upstream);
}

function safeEqual(left, right) {
  const leftBuffer = Buffer.from(String(left));
  const rightBuffer = Buffer.from(String(right));
  if (leftBuffer.length !== rightBuffer.length) return false;
  return crypto.timingSafeEqual(leftBuffer, rightBuffer);
}

function credentialsAreValid(username, password) {
  if (!AUTH_USER || !AUTH_PASSWORD) return false;
  return safeEqual(username, AUTH_USER) && safeEqual(password, AUTH_PASSWORD);
}

function signTokenPart(subject, expiresAt) {
  return crypto
    .createHmac('sha256', AUTH_SECRET)
    .update(`${subject}.${expiresAt}`)
    .digest('base64url');
}

function createDataToken(username) {
  const subject = Buffer.from(username).toString('base64url');
  const expiresAt = String(Date.now() + AUTH_TOKEN_TTL_MS);
  const signature = signTokenPart(subject, expiresAt);
  return `${subject}.${expiresAt}.${signature}`;
}

function validateDataToken(token) {
  const parts = String(token || '').split('.');
  if (parts.length !== 3) return false;
  const [subject, expiresAt, signature] = parts;
  const expiresAtMs = Number(expiresAt);
  if (!subject || !Number.isFinite(expiresAtMs) || expiresAtMs <= Date.now()) return false;
  return safeEqual(signature, signTokenPart(subject, expiresAt));
}

function extractDataToken(req, url) {
  const auth = String(req.headers.authorization || '');
  if (auth.startsWith('Bearer ')) return auth.slice(7);
  return url.searchParams.get('data_token') || '';
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      body += chunk;
      if (Buffer.byteLength(body, 'utf8') > MAX_LOGIN_BODY_BYTES) {
        reject(new Error('request_too_large'));
        req.destroy();
      }
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        reject(new Error('invalid_json'));
      }
    });
    req.on('error', reject);
  });
}

async function handleLogin(req, res) {
  if (req.method !== 'POST') {
    res.writeHead(405, { allow: 'POST', 'cache-control': 'no-store' });
    res.end();
    return;
  }

  let body;
  try {
    body = await readJsonBody(req);
  } catch {
    sendJson(res, 400, { ok: false, error: 'invalid_login_request' });
    return;
  }

  if (!credentialsAreValid(body.username, body.password)) {
    sendJson(res, 401, { ok: false, error: 'invalid_username_or_password' });
    return;
  }

  sendJson(res, 200, {
    access_token: createDataToken(body.username),
    token_type: 'bearer',
    expires_in: Math.floor(AUTH_TOKEN_TTL_MS / 1000),
  });
}

function requireDataToken(req, res, url) {
  if (validateDataToken(extractDataToken(req, url))) return true;
  sendJson(res, 401, { ok: false, error: 'betman_data_login_required' });
  return false;
}

function proxyApi(req, res, upstreamPath) {
  const headers = {
    ...req.headers,
    host: `${API_HOST}:${API_PORT}`,
    'x-forwarded-host': req.headers.host || '',
    'x-forwarded-proto': req.socket.encrypted ? 'https' : 'http',
  };
  if (API_AUTHORIZATION) headers.authorization = API_AUTHORIZATION;
  delete headers.connection;
  delete headers['proxy-connection'];

  const upstream = http.request({
    hostname: API_HOST,
    port: API_PORT,
    method: req.method,
    path: upstreamPath,
    headers,
  }, (upstreamRes) => {
    res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);
    upstreamRes.pipe(res);
  });

  upstream.on('error', (error) => {
    sendJson(res, 502, {
      ok: false,
      error: 'betman_data_api_unavailable',
      message: error.message,
    });
  });

  req.pipe(upstream);
}

function writeUpgradeResponse(socket, statusCode, statusMessage, headers) {
  const lines = [`HTTP/1.1 ${statusCode} ${statusMessage || ''}`.trim()];
  for (const [key, value] of Object.entries(headers || {})) {
    if (Array.isArray(value)) {
      for (const item of value) lines.push(`${key}: ${item}`);
    } else if (value !== undefined) {
      lines.push(`${key}: ${value}`);
    }
  }
  socket.write(`${lines.join('\r\n')}\r\n\r\n`);
}

function proxyApiUpgrade(req, socket, head, upstreamPath) {
  const headers = {
    ...req.headers,
    host: `${API_HOST}:${API_PORT}`,
    'x-forwarded-host': req.headers.host || '',
    'x-forwarded-proto': 'https',
  };
  if (API_AUTHORIZATION) headers.authorization = API_AUTHORIZATION;

  const upstream = http.request({
    hostname: API_HOST,
    port: API_PORT,
    method: req.method,
    path: upstreamPath,
    headers,
  });

  upstream.on('upgrade', (upstreamRes, upstreamSocket, upstreamHead) => {
    writeUpgradeResponse(socket, upstreamRes.statusCode || 101, upstreamRes.statusMessage || 'Switching Protocols', upstreamRes.headers);
    if (upstreamHead?.length) socket.write(upstreamHead);
    if (head?.length) upstreamSocket.write(head);
    upstreamSocket.pipe(socket);
    socket.pipe(upstreamSocket);
  });

  upstream.on('response', (upstreamRes) => {
    writeUpgradeResponse(socket, upstreamRes.statusCode || 502, upstreamRes.statusMessage || 'Bad Gateway', upstreamRes.headers);
    upstreamRes.on('data', (chunk) => socket.write(chunk));
    upstreamRes.on('end', () => socket.end());
  });

  upstream.on('error', () => {
    writeUpgradeResponse(socket, 502, 'Bad Gateway', { 'content-type': 'text/plain' });
    socket.end('betman_data_api_unavailable');
  });

  upstream.end();
}

function serveStatic(req, res, pathname) {
  let cleanPath;
  try {
    cleanPath = decodeURIComponent(pathname).replace(/^\/+/, '');
  } catch {
    sendJson(res, 400, { ok: false, error: 'invalid_path' });
    return;
  }
  const candidate = path.resolve(ROOT, cleanPath || 'index.html');
  const rootPath = path.resolve(ROOT);
  let filePath = path.join(rootPath, 'index.html');
  try {
    if (candidate.startsWith(rootPath) && fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      filePath = candidate;
    }
  } catch {
    sendJson(res, 404, { ok: false, error: 'static_asset_not_found' });
    return;
  }
  const ext = path.extname(filePath).toLowerCase();
  const immutable = filePath.includes(`${path.sep}assets${path.sep}`);
  const stream = fs.createReadStream(filePath);
  stream.on('open', () => {
    res.writeHead(200, {
      'content-type': TYPES[ext] || 'application/octet-stream',
      'cache-control': immutable ? 'public, max-age=31536000, immutable' : 'no-store',
      'x-content-type-options': 'nosniff',
    });
  });
  stream.on('error', () => {
    if (!res.headersSent) sendJson(res, 500, { ok: false, error: 'static_asset_unavailable' });
    else res.destroy();
  });
  stream.pipe(res);
}

function handleRequest(req, res) {
  let url;
  try {
    url = new URL(req.url || '/', 'http://betman-data-webapp.local');
  } catch {
    sendJson(res, 400, { ok: false, error: 'invalid_url' });
    return;
  }

  if (url.pathname === '/health') {
    sendJson(res, 200, { ok: true });
    return;
  }

  if (url.pathname === '/auth/login') {
    handleLogin(req, res);
    return;
  }

  if (url.pathname === '/password-setup-link') {
    proxyPasswordSetup(req, res);
    return;
  }

  if (url.pathname === '/api' || url.pathname.startsWith('/api/')) {
    const upstreamPath = url.pathname.replace(/^\/api(?=\/|$)/, '') + url.search || '/';
    if (requireDataToken(req, res, url)) proxyApi(req, res, upstreamPath);
    return;
  }

  serveStatic(req, res, url.pathname);
}

function handleUpgrade(req, socket, head) {
  let url;
  try {
    url = new URL(req.url || '/', 'http://betman-data-webapp.local');
  } catch {
    writeUpgradeResponse(socket, 400, 'Bad Request', { 'content-type': 'text/plain' });
    socket.end('invalid_url');
    return;
  }
  if (url.pathname === '/api' || url.pathname.startsWith('/api/')) {
    const upstreamPath = url.pathname.replace(/^\/api(?=\/|$)/, '') + url.search || '/';
    if (validateDataToken(extractDataToken(req, url))) {
      proxyApiUpgrade(req, socket, head, upstreamPath);
      return;
    }
    writeUpgradeResponse(socket, 401, 'Unauthorized', { 'content-type': 'text/plain' });
    socket.end('betman_data_login_required');
    return;
  }
  writeUpgradeResponse(socket, 404, 'Not Found', { 'content-type': 'text/plain' });
  socket.end('not_found');
}

function createHttpServer() {
  const server = http.createServer(handleRequest);
  server.on('upgrade', handleUpgrade);
  server.on('connection', (socket) => {
    socket.on('error', () => {});
  });
  server.on('clientError', (_error, socket) => {
    socket.destroy();
  });
  return server;
}

createHttpServer().listen(PORT, HOST, () => {
  console.log(`BETMAN Data Viewer listening on http://${HOST}:${PORT}`);
});

if (PUBLIC_PORT) {
  if (!TLS_CERT || !TLS_KEY) {
    console.error('BETMAN_DATA_PUBLIC_PORT is set but BETMAN_DATA_TLS_CERT/BETMAN_DATA_TLS_KEY are missing');
    process.exitCode = 1;
  } else {
    const tlsOptions = {
      cert: fs.readFileSync(TLS_CERT),
      key: fs.readFileSync(TLS_KEY),
    };
    const publicServer = https.createServer(tlsOptions, handleRequest);
    publicServer.on('upgrade', handleUpgrade);
    publicServer.on('connection', (socket) => {
      socket.on('error', () => {});
    });
    publicServer.on('secureConnection', (socket) => {
      socket.on('error', () => {});
    });
    publicServer.on('tlsClientError', () => {});
    publicServer.on('clientError', (_error, socket) => {
      socket.destroy();
    });
    publicServer.listen(PUBLIC_PORT, PUBLIC_HOST || undefined, () => {
      console.log(`BETMAN Data Viewer public listener on https://${PUBLIC_HOST || '0.0.0.0'}:${PUBLIC_PORT}`);
    });
  }
}
