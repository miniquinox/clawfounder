/**
 * ClawFounder Dashboard — Backend API
 * 
 * Reads/writes the .env file, discovers connectors,
 * and handles Firebase Google login flow.
 */

import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';
import { spawn, execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const ENV_FILE = path.join(PROJECT_ROOT, '.env');
const CONNECTORS_DIR = path.join(PROJECT_ROOT, 'connectors');
const FIREBASE_CONFIG = path.join(os.homedir(), '.config', 'configstore', 'firebase-tools.json');
const ADC_FILE = path.join(os.homedir(), '.config', 'gcloud', 'application_default_credentials.json');

// Separate credential files for personal Gmail vs Work Email
const GMAIL_PERSONAL_TOKEN = path.join(os.homedir(), '.clawfounder', 'gmail_personal.json');
const GMAIL_WORK_TOKEN = path.join(os.homedir(), '.clawfounder', 'gmail_work.json');

const app = express();
app.use(cors({ origin: /^https?:\/\/localhost(:\d+)?$/ }));
app.use(express.json());

// ── Parse .env file ─────────────────────────────────────────────
function readEnv() {
    if (!fs.existsSync(ENV_FILE)) return {};
    const content = fs.readFileSync(ENV_FILE, 'utf-8');
    const env = {};
    for (const line of content.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        const eqIndex = trimmed.indexOf('=');
        if (eqIndex === -1) continue;
        const key = trimmed.slice(0, eqIndex).trim();
        let value = trimmed.slice(eqIndex + 1).trim();
        // Strip inline comments (unquoted # preceded by whitespace)
        if (!value.startsWith('"') && !value.startsWith("'")) {
            const hashIdx = value.indexOf(' #');
            if (hashIdx !== -1) value = value.slice(0, hashIdx).trim();
            // Also handle value that IS just a comment (e.g., "= # comment")
            if (value.startsWith('#')) value = '';
        }
        if (value) env[key] = value;
    }
    return env;
}

function writeEnv(envObj) {
    let lines = [];
    if (fs.existsSync(ENV_FILE)) {
        lines = fs.readFileSync(ENV_FILE, 'utf-8').split('\n');
    }

    const updatedKeys = new Set();

    const newLines = lines.map(line => {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) return line;
        const eqIndex = trimmed.indexOf('=');
        if (eqIndex === -1) return line;
        const key = trimmed.slice(0, eqIndex).trim();
        if (key in envObj) {
            updatedKeys.add(key);
            return `${key}=${envObj[key]}`;
        }
        return line;
    });

    for (const [key, value] of Object.entries(envObj)) {
        if (!updatedKeys.has(key) && value) {
            newLines.push(`${key}=${value}`);
        }
    }

    fs.writeFileSync(ENV_FILE, newLines.join('\n'));
}

// ── Discover connectors ─────────────────────────────────────────
function discoverConnectors() {
    if (!fs.existsSync(CONNECTORS_DIR)) return [];
    const folders = fs.readdirSync(CONNECTORS_DIR, { withFileTypes: true });
    const connectors = [];

    for (const folder of folders) {
        if (!folder.isDirectory() || folder.name.startsWith('_') || folder.name.startsWith('.')) continue;

        const connectorPath = path.join(CONNECTORS_DIR, folder.name);
        const instructionsPath = path.join(connectorPath, 'instructions.md');

        let instructions = '';
        if (fs.existsSync(instructionsPath)) {
            instructions = fs.readFileSync(instructionsPath, 'utf-8');
        }

        // Parse required env vars from instructions.md table
        const envVars = [];
        const tableRegex = /\|\s*`([A-Z_]+)`\s*\|([^|]*)\|\s*(Yes|No)\s*\|/g;
        let match;
        while ((match = tableRegex.exec(instructions)) !== null) {
            envVars.push({
                key: match[1],
                description: match[2].trim(),
                required: match[3].trim() === 'Yes',
            });
        }

        // These connectors use Google login, not manual keys
        const usesGoogleLogin = ['firebase', 'gmail', 'work_email'].includes(folder.name);

        connectors.push({
            name: folder.name,
            envVars,
            usesGoogleLogin,
        });
    }

    return connectors;
}

// ── Firebase helpers ────────────────────────────────────────────
function getFirebaseAuth() {
    try {
        if (!fs.existsSync(FIREBASE_CONFIG)) return null;
        const config = JSON.parse(fs.readFileSync(FIREBASE_CONFIG, 'utf-8'));
        const tokens = config.tokens || {};
        const user = config.user || {};
        if (!tokens.refresh_token) return null;
        return {
            email: user.email || null,
            hasToken: true,
            expiresAt: tokens.expires_at || null,
        };
    } catch {
        return null;
    }
}

function getFirebaseRefreshToken() {
    try {
        if (!fs.existsSync(FIREBASE_CONFIG)) return null;
        const config = JSON.parse(fs.readFileSync(FIREBASE_CONFIG, 'utf-8'));
        return config.tokens?.refresh_token || null;
    } catch {
        return null;
    }
}

// Track active login process
let firebaseLoginProcess = null;

// ── API Routes ──────────────────────────────────────────────────

// Get current config (keys masked)
app.get('/api/config', (req, res) => {
    const env = readEnv();
    const masked = {};
    for (const [key, value] of Object.entries(env)) {
        if (value && value.length > 4) {
            masked[key] = value.slice(0, 4) + '•'.repeat(Math.min(value.length - 4, 20));
        } else {
            masked[key] = value ? '••••' : '';
        }
    }
    const isSet = {};
    for (const key of Object.keys(env)) {
        isSet[key] = true;
    }
    res.json({ config: masked, isSet });
});

// Save config
app.post('/api/config', (req, res) => {
    try {
        const { updates } = req.body;
        writeEnv(updates);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// List connectors
app.get('/api/connectors', (req, res) => {
    const connectors = discoverConnectors();
    const env = readEnv();
    const firebaseAuth = getFirebaseAuth();

    const enriched = connectors.map(c => {
        let connected;
        if (c.name === 'firebase') {
            // Firebase is connected if Google login exists + project ID is set
            connected = !!(firebaseAuth?.hasToken && env['FIREBASE_PROJECT_ID']);
        } else if (c.name === 'gmail') {
            connected = fs.existsSync(GMAIL_PERSONAL_TOKEN);
        } else if (c.name === 'work_email') {
            connected = fs.existsSync(GMAIL_WORK_TOKEN);
        } else {
            connected = c.envVars
                .filter(v => v.required)
                .every(v => env[v.key] && env[v.key].length > 0);
        }
        return { ...c, connected };
    });

    res.json({ connectors: enriched });
});

// ── Firebase-specific routes ────────────────────────────────────

// Check Firebase login status
app.get('/api/firebase/status', (req, res) => {
    const auth = getFirebaseAuth();
    const env = readEnv();
    res.json({
        loggedIn: !!auth?.hasToken,
        email: auth?.email || null,
        projectId: env['FIREBASE_PROJECT_ID'] || null,
        loginInProgress: !!firebaseLoginProcess,
    });
});

// Start Firebase Google login
app.post('/api/firebase/login', (req, res) => {
    if (firebaseLoginProcess) {
        return res.json({ status: 'already_running', message: 'Login already in progress. Complete it in your browser.' });
    }

    const proc = spawn('npx', ['-y', 'firebase-tools@latest', 'login', '--reauth'], {
        stdio: ['ignore', 'pipe', 'pipe'],
        shell: true,
    });

    firebaseLoginProcess = proc;
    let output = '';

    proc.stdout.on('data', (data) => { output += data.toString(); });
    proc.stderr.on('data', (data) => { output += data.toString(); });

    proc.on('close', (code) => {
        firebaseLoginProcess = null;
        console.log('Firebase login process exited with code:', code);
    });

    // Return immediately — the browser will open
    res.json({ status: 'started', message: 'Browser should open for Google login. Complete the login there.' });
});

// List Firebase projects (requires login)
app.get('/api/firebase/projects', async (req, res) => {
    const auth = getFirebaseAuth();
    if (!auth?.hasToken) {
        return res.status(401).json({ error: 'Not logged in. Run Firebase login first.' });
    }

    try {
        const result = await new Promise((resolve, reject) => {
            const proc = spawn('npx', ['-y', 'firebase-tools@latest', 'projects:list', '--json'], {
                stdio: ['ignore', 'pipe', 'pipe'],
                shell: true,
            });

            let stdout = '';
            let stderr = '';
            proc.stdout.on('data', d => { stdout += d.toString(); });
            proc.stderr.on('data', d => { stderr += d.toString(); });

            proc.on('close', (code) => {
                if (code === 0) {
                    try {
                        const data = JSON.parse(stdout);
                        resolve(data);
                    } catch {
                        reject(new Error('Failed to parse projects list'));
                    }
                } else {
                    reject(new Error(stderr || 'Failed to list projects'));
                }
            });
        });

        // result is { status: "success", result: [...] }
        const projects = (result.result || result || []).map(p => ({
            id: p.projectId || p.projectid,
            name: p.displayName || p.displayname || p.projectId,
        }));

        res.json({ projects });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Select Firebase project
app.post('/api/firebase/select-project', (req, res) => {
    const { projectId } = req.body;
    if (!projectId) {
        return res.status(400).json({ error: 'projectId is required' });
    }

    try {
        writeEnv({ FIREBASE_PROJECT_ID: projectId });

        // Also save the refresh token so the Python connector can use it
        const refreshToken = getFirebaseRefreshToken();
        if (refreshToken) {
            writeEnv({ FIREBASE_REFRESH_TOKEN: refreshToken });
        }

        res.json({ success: true, projectId });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});
// ── Email connector routes (Gmail + Work Email) ───────────────

let emailLoginProcess = null; // shared — only one login at a time

const GMAIL_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
].join(',');

// Map connector name → token file
const EMAIL_TOKEN_FILES = {
    gmail: GMAIL_PERSONAL_TOKEN,
    work_email: GMAIL_WORK_TOKEN,
};

const GMAIL_CLIENT_SECRET = path.join(os.homedir(), '.clawfounder', 'gmail_client_secret.json');

// Status endpoint for both Gmail and Work Email
for (const connName of ['gmail', 'work_email']) {
    app.get(`/api/${connName.replace('_', '-')}/status`, (req, res) => {
        const tokenFile = EMAIL_TOKEN_FILES[connName];
        try {
            if (fs.existsSync(tokenFile)) {
                const tokenData = JSON.parse(fs.readFileSync(tokenFile, 'utf-8'));
                if (tokenData.refresh_token || tokenData.token) {
                    const email = tokenData._email || null;
                    return res.json({ loggedIn: true, email, loginInProgress: !!emailLoginProcess });
                }
            }
            // For personal Gmail, also report if client_secret exists
            if (connName === 'gmail') {
                return res.json({
                    loggedIn: false,
                    email: null,
                    loginInProgress: !!emailLoginProcess,
                    hasClientSecret: fs.existsSync(GMAIL_CLIENT_SECRET),
                });
            }
            res.json({ loggedIn: false, email: null, loginInProgress: !!emailLoginProcess });
        } catch {
            res.json({ loggedIn: false, email: null, loginInProgress: !!emailLoginProcess });
        }
    });
}

// Gmail client secret upload endpoint
app.post('/api/gmail/client-secret', (req, res) => {
    try {
        const { client_id, client_secret } = req.body;
        if (!client_id || !client_secret) {
            return res.status(400).json({ error: 'client_id and client_secret are required.' });
        }

        const secretData = {
            installed: {
                client_id,
                client_secret,
                auth_uri: 'https://accounts.google.com/o/oauth2/auth',
                token_uri: 'https://oauth2.googleapis.com/token',
                redirect_uris: ['http://localhost'],
            },
        };

        fs.mkdirSync(path.dirname(GMAIL_CLIENT_SECRET), { recursive: true });
        fs.writeFileSync(GMAIL_CLIENT_SECRET, JSON.stringify(secretData, null, 2));
        res.json({ success: true, message: 'Client credentials saved.' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Delete Gmail client secret (reset OAuth credentials)
app.delete('/api/gmail/client-secret', (req, res) => {
    try {
        if (fs.existsSync(GMAIL_CLIENT_SECRET)) fs.unlinkSync(GMAIL_CLIENT_SECRET);
        if (fs.existsSync(GMAIL_PERSONAL_TOKEN)) fs.unlinkSync(GMAIL_PERSONAL_TOKEN);
        res.json({ success: true, message: 'Gmail credentials reset.' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ── Personal Gmail login (Python OAuth flow) ────────────────────
app.post('/api/gmail/login', (req, res) => {
    if (emailLoginProcess) {
        return res.json({ status: 'already_running', message: 'Login already in progress. Complete it in your browser.' });
    }

    if (!fs.existsSync(GMAIL_CLIENT_SECRET)) {
        return res.status(400).json({
            status: 'needs_client_secret',
            error: 'OAuth client credentials not configured. Please set up your client ID first.',
        });
    }

    // Run the Python OAuth script
    const oauthScript = path.join(CONNECTORS_DIR, 'gmail', 'oauth_login.py');
    const venvPython = path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
    const pythonCmd = fs.existsSync(venvPython) ? venvPython : 'python3';

    const proc = spawn(pythonCmd, [oauthScript], {
        stdio: ['ignore', 'pipe', 'pipe'],
        cwd: PROJECT_ROOT,
    });

    emailLoginProcess = proc;
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => { stdout += data.toString(); });
    proc.stderr.on('data', (data) => { stderr += data.toString(); });

    proc.on('close', (code) => {
        emailLoginProcess = null;
        console.log('[gmail] OAuth login exited with code:', code);
        if (stderr) console.log('[gmail] stderr:', stderr.slice(-300));

        if (code === 0) {
            try {
                const result = JSON.parse(stdout);
                console.log(`[gmail] ✅ Logged in as ${result.email || 'unknown'}`);
            } catch {
                console.log('[gmail] ✅ Login completed (could not parse output)');
            }
        } else {
            console.log('[gmail] ❌ Login failed:', stdout.slice(-300));
        }
    });

    res.json({ status: 'started', message: 'Browser should open for Google login. Complete the login there.' });
});

// ── Work Email login (gcloud ADC flow) ──────────────────────────
app.post('/api/work-email/login', (req, res) => {
    if (emailLoginProcess) {
        return res.json({ status: 'already_running', message: 'Login already in progress. Complete it in your browser.' });
    }

    const tokenFile = EMAIL_TOKEN_FILES.work_email;

    const proc = spawn('gcloud', [
        'auth', 'application-default', 'login',
        `--scopes=${GMAIL_SCOPES}`,
    ], {
        stdio: ['ignore', 'pipe', 'pipe'],
        shell: true,
    });

    emailLoginProcess = proc;
    let output = '';

    proc.stdout.on('data', (data) => { output += data.toString(); });
    proc.stderr.on('data', (data) => { output += data.toString(); });

    proc.on('close', (code) => {
        emailLoginProcess = null;
        console.log('[work_email] ADC login exited with code:', code);
        if (output) console.log('[work_email] output:', output.slice(-300));

        // gcloud sometimes exits with code 1 even on success (scope warnings).
        // Check if the ADC file was actually updated recently.
        let adcUpdated = false;
        try {
            const stat = fs.statSync(ADC_FILE);
            const ageMs = Date.now() - stat.mtimeMs;
            adcUpdated = ageMs < 60000; // updated within last 60 seconds
        } catch { /* file doesn't exist */ }

        if (code !== 0 && !adcUpdated) {
            console.log('[work_email] Login failed (no fresh ADC file).');
            return;
        }

        console.log('[work_email] Login succeeded. Running post-login setup...');

        const run = (cmd) => {
            try {
                return execSync(cmd, { encoding: 'utf-8', timeout: 30000 }).trim();
            } catch (e) {
                console.log(`[work_email] Command failed: ${cmd}`, e.message?.slice(0, 200));
                return null;
            }
        };

        // 1. Detect quota project (fast — just reads config/env)
        let quotaProject = null;
        const env = readEnv();
        if (env['FIREBASE_PROJECT_ID']) quotaProject = env['FIREBASE_PROJECT_ID'];
        if (!quotaProject) quotaProject = run('gcloud config get-value project 2>/dev/null');

        // 2. Read ADC file and save token IMMEDIATELY (so UI detects login)
        let adcData;
        try {
            adcData = JSON.parse(fs.readFileSync(ADC_FILE, 'utf-8'));
            if (quotaProject) adcData.quota_project_id = quotaProject;
            fs.mkdirSync(path.dirname(tokenFile), { recursive: true });
            fs.writeFileSync(tokenFile, JSON.stringify(adcData, null, 2));
            console.log(`[work_email] ✅ Saved initial credentials to ${tokenFile}`);
        } catch (e) {
            console.log(`[work_email] ⚠ Could not save token file:`, e.message);
            return;
        }

        // 3. Detect email from the ADC token (NOT gcloud auth list, which returns wrong account)
        //    Use the refresh token to get an access token, then call userinfo
        (async () => {
            try {
                const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({
                        client_id: adcData.client_id,
                        client_secret: adcData.client_secret,
                        refresh_token: adcData.refresh_token,
                        grant_type: 'refresh_token',
                    }),
                });
                const tokenData = await tokenRes.json();

                if (tokenData.access_token) {
                    const userRes = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
                        headers: { Authorization: `Bearer ${tokenData.access_token}` },
                    });
                    const userData = await userRes.json();
                    if (userData.email) {
                        adcData._email = userData.email;
                        fs.writeFileSync(tokenFile, JSON.stringify(adcData, null, 2));
                        console.log(`[work_email] ✅ Detected email: ${userData.email}`);
                    }
                }
            } catch (e) {
                console.log('[work_email] ⚠ Could not detect email:', e.message);
            }
        })();

        // 4. Slow setup (runs after token is saved — UI already shows connected)
        if (!quotaProject) {
            const first = run('gcloud projects list --format="value(projectId)" --limit=1 2>/dev/null');
            if (first) quotaProject = first;
        }
        if (quotaProject) {
            console.log(`[work_email] Enabling Gmail API on ${quotaProject}...`);
            run(`gcloud services enable gmail.googleapis.com --project=${quotaProject} 2>/dev/null`);
        }

        console.log('[work_email] ✅ Post-login setup complete!');
    });

    res.json({ status: 'started', message: 'Browser should open for Work Email login. Complete the login there.' });
});

// ── Disconnect endpoint ─────────────────────────────────────────

app.post('/api/connector/:name/disconnect', (req, res) => {
    const { name } = req.params;
    try {
        if (name === 'firebase') {
            // Clear project ID from .env (keep gcloud auth intact)
            const env = readEnv();
            if (env['FIREBASE_PROJECT_ID']) {
                writeEnv({ FIREBASE_PROJECT_ID: '' });
            }
            return res.json({ success: true, message: 'Firebase disconnected. Project ID cleared.' });
        }

        if (name === 'gmail' || name === 'work_email') {
            const tokenFile = EMAIL_TOKEN_FILES[name];
            if (tokenFile && fs.existsSync(tokenFile)) {
                fs.unlinkSync(tokenFile);
            }
            const label = name === 'gmail' ? 'Gmail' : 'Work Email';
            return res.json({ success: true, message: `${label} disconnected. Token removed.` });
        }

        // Generic connector: clear all env vars from .env
        const connectors = discoverConnectors();
        const connector = connectors.find(c => c.name === name);
        if (!connector) {
            return res.status(404).json({ error: `Connector "${name}" not found.` });
        }

        if (connector.envVars.length === 0) {
            return res.json({ success: true, message: `${name} has no config to clear.` });
        }

        const updates = {};
        for (const v of connector.envVars) {
            updates[v.key] = '';
        }
        writeEnv(updates);
        return res.json({ success: true, message: `${name} disconnected. ${Object.keys(updates).length} key(s) cleared.` });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ── Chat SSE endpoint ───────────────────────────────────────────

// List available providers (ones with API keys set)
app.get('/api/providers', (req, res) => {
    const env = readEnv();
    const providers = [];

    // Any GEMINI_API_KEY works — Vertex AI REST endpoint accepts all key formats
    if (env['GEMINI_API_KEY']) providers.push({ id: 'gemini', label: 'Gemini', emoji: '✨' });
    if (env['OPENAI_API_KEY']) providers.push({ id: 'openai', label: 'OpenAI', emoji: '🤖' });
    if (env['ANTHROPIC_API_KEY']) providers.push({ id: 'claude', label: 'Claude', emoji: '🧠' });

    res.json({ providers });
});

// SSE chat endpoint — streams agent events
app.post('/api/chat', (req, res) => {
    const { message, provider, history } = req.body;
    console.log(`[chat] Received: provider=${provider}, message="${message?.slice(0, 50)}..."`);

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    res.flushHeaders();

    // Merge the .env vars into the child process environment
    const envVars = { ...process.env, ...readEnv() };

    const pyScript = path.join(__dirname, 'chat_agent.py');
    // Use venv Python if available — check uv's .venv first, then venv
    const uvVenvPython = path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
    const venvPython = path.join(PROJECT_ROOT, 'venv', 'bin', 'python3');
    const pythonCmd = fs.existsSync(uvVenvPython) ? uvVenvPython : fs.existsSync(venvPython) ? venvPython : 'python3';
    console.log(`[chat] Spawning: ${pythonCmd} ${pyScript}`);

    const proc = spawn(pythonCmd, [pyScript], {
        cwd: PROJECT_ROOT,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: envVars,
    });

    let processExited = false;

    proc.on('error', (err) => {
        console.error('[chat] Spawn error:', err);
        res.write(`data: ${JSON.stringify({ type: 'error', error: `Spawn error: ${err.message}` })}\n\n`);
        res.end();
    });

    // Send input as JSON
    proc.stdin.write(JSON.stringify({ message, provider, history: history || [] }));
    proc.stdin.end();

    // Stream JSONL from stdout as SSE
    let buffer = '';
    proc.stdout.on('data', (data) => {
        const chunk = data.toString();
        console.log('[chat] stdout:', chunk.trim());
        buffer += chunk;
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
            if (line.trim()) {
                res.write(`data: ${line}\n\n`);
            }
        }
    });

    proc.stderr.on('data', (data) => {
        console.error('[chat_agent stderr]', data.toString().trim());
    });

    proc.on('close', (code) => {
        processExited = true;
        console.log(`[chat] Process exited with code ${code}`);
        if (buffer.trim()) {
            res.write(`data: ${buffer}\n\n`);
        }
        res.write(`data: ${JSON.stringify({ type: 'done' })}\n\n`);
        res.end();
    });

    // Only kill process if client truly disconnects while process is still running
    res.on('close', () => {
        if (!processExited) {
            console.log('[chat] Client disconnected, killing process');
            proc.kill();
        }
    });
});

// ── Start ───────────────────────────────────────────────────────
const PORT = 3001;
app.listen(PORT, () => {
    console.log(`🦀 ClawFounder API running on http://localhost:${PORT}`);
});
