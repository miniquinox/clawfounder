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
import { WebSocketServer } from 'ws';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const ENV_FILE = path.join(PROJECT_ROOT, '.env');
const CONNECTORS_DIR = path.join(PROJECT_ROOT, 'connectors');
const FIREBASE_CONFIG = path.join(os.homedir(), '.config', 'configstore', 'firebase-tools.json');
const ADC_FILE = path.join(os.homedir(), '.config', 'gcloud', 'application_default_credentials.json');

// Separate credential files for personal Gmail vs Work Email
const GMAIL_PERSONAL_TOKEN = path.join(os.homedir(), '.clawfounder', 'gmail_personal.json');
const GMAIL_WORK_TOKEN = path.join(os.homedir(), '.clawfounder', 'gmail_work.json');

const CLAWFOUNDER_DIR = path.join(os.homedir(), '.clawfounder');
const ACCOUNTS_FILE = path.join(CLAWFOUNDER_DIR, 'accounts.json');
const BRIEFING_CONFIG_FILE = path.join(CLAWFOUNDER_DIR, 'briefing_config.json');

const app = express();
const IS_PRODUCTION = process.env.NODE_ENV === 'production';
app.use(cors(IS_PRODUCTION ? {} : { origin: /^https?:\/\/localhost(:\d+)?$/ }));
app.use(express.json());

// ── Serve built frontend in production ──────────────────────────
const DIST_DIR = path.join(__dirname, 'dist');
if (fs.existsSync(DIST_DIR)) {
    app.use(express.static(DIST_DIR));
}

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

// ── Accounts registry ───────────────────────────────────────────

function readAccountsRegistry() {
    if (!fs.existsSync(ACCOUNTS_FILE)) return { version: 1, accounts: {} };
    try {
        return JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf-8'));
    } catch {
        return { version: 1, accounts: {} };
    }
}

function writeAccountsRegistry(registry) {
    fs.mkdirSync(CLAWFOUNDER_DIR, { recursive: true });
    fs.writeFileSync(ACCOUNTS_FILE, JSON.stringify(registry, null, 2));
}

/**
 * Auto-generate accounts.json from existing credentials if it doesn't exist.
 * Called at startup. No files are moved — just records what exists.
 */
function ensureAccountsRegistry() {
    if (fs.existsSync(ACCOUNTS_FILE)) return;

    const env = readEnv();
    const registry = { version: 1, accounts: {} };

    // Gmail personal
    if (fs.existsSync(GMAIL_PERSONAL_TOKEN)) {
        let email = 'Personal Gmail';
        try {
            const data = JSON.parse(fs.readFileSync(GMAIL_PERSONAL_TOKEN, 'utf-8'));
            if (data._email) email = data._email;
        } catch { /* ignore */ }
        registry.accounts.gmail = [{
            id: 'default',
            label: email,
            enabled: true,
            credential_file: 'gmail_personal.json',
        }];
    }

    // Work email
    if (fs.existsSync(GMAIL_WORK_TOKEN)) {
        let email = 'Work Email';
        try {
            const data = JSON.parse(fs.readFileSync(GMAIL_WORK_TOKEN, 'utf-8'));
            if (data._email) email = data._email;
        } catch { /* ignore */ }
        registry.accounts.work_email = [{
            id: 'default',
            label: email,
            enabled: true,
            credential_file: 'gmail_work.json',
        }];
    }

    // GitHub
    if (env['GITHUB_TOKEN']) {
        registry.accounts.github = [{
            id: 'default',
            label: 'personal',
            enabled: true,
            env_key: 'GITHUB_TOKEN',
        }];
    }

    // Telegram
    if (env['TELEGRAM_BOT_TOKEN'] && env['TELEGRAM_CHAT_ID']) {
        registry.accounts.telegram = [{
            id: 'default',
            label: 'default bot',
            enabled: true,
            env_keys: { TELEGRAM_BOT_TOKEN: 'TELEGRAM_BOT_TOKEN', TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID' },
        }];
    }

    // Supabase
    if (env['SUPABASE_URL'] && env['SUPABASE_SERVICE_KEY']) {
        registry.accounts.supabase = [{
            id: 'default',
            label: 'default',
            enabled: true,
            env_keys: { SUPABASE_URL: 'SUPABASE_URL', SUPABASE_SERVICE_KEY: 'SUPABASE_SERVICE_KEY' },
        }];
    }

    writeAccountsRegistry(registry);
    console.log('[accounts] Auto-generated accounts.json from existing credentials');
}

/**
 * Get the credential file path for an email account.
 */
function getAccountCredentialFile(connectorName, accountId) {
    if (accountId === 'default' || !accountId) {
        return connectorName === 'gmail' ? GMAIL_PERSONAL_TOKEN : GMAIL_WORK_TOKEN;
    }
    return path.join(CLAWFOUNDER_DIR, `${connectorName}_account_${accountId}.json`);
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
    const registry = readAccountsRegistry();

    const enriched = connectors.map(c => {
        let connected;
        if (c.name === 'firebase') {
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

        // Attach accounts from the registry
        const accounts = (registry.accounts[c.name] || []).map(acct => {
            let acctConnected = false;
            if (c.name === 'gmail' || c.name === 'work_email') {
                const credFile = getAccountCredentialFile(c.name, acct.id);
                acctConnected = fs.existsSync(credFile);
            } else if (acct.env_key) {
                acctConnected = !!(env[acct.env_key]);
            } else if (acct.env_keys) {
                acctConnected = Object.values(acct.env_keys).every(k => env[k] && env[k].length > 0);
            }
            return { ...acct, connected: acctConnected };
        });

        // Also consider connected if any registry account is connected
        if (!connected && accounts.some(a => a.connected)) {
            connected = true;
        }

        const supportsMultiAccount = !['firebase', 'yahoo_finance'].includes(c.name);

        return { ...c, connected, accounts, supportsMultiAccount };
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

const emailLoginProcesses = {}; // keyed by "connector:accountId" for concurrent logins

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
        const anyLoginInProgress = Object.keys(emailLoginProcesses).some(k => k.startsWith(connName + ':'));
        try {
            // Build per-account status from registry
            const registry = readAccountsRegistry();
            const acctList = registry.accounts[connName] || [];
            const accounts = acctList.map(acct => {
                const credFile = getAccountCredentialFile(connName, acct.id);
                let acctLoggedIn = false;
                let acctEmail = null;
                try {
                    if (fs.existsSync(credFile)) {
                        const data = JSON.parse(fs.readFileSync(credFile, 'utf-8'));
                        if (data.refresh_token || data.token) {
                            acctLoggedIn = true;
                            acctEmail = data._email || null;
                        }
                    }
                } catch { /* ignore */ }
                return {
                    ...acct,
                    connected: acctLoggedIn,
                    email: acctEmail,
                    loginInProgress: !!emailLoginProcesses[`${connName}:${acct.id}`],
                };
            });

            // Backward-compat: top-level loggedIn/email from default account
            if (fs.existsSync(tokenFile)) {
                const tokenData = JSON.parse(fs.readFileSync(tokenFile, 'utf-8'));
                if (tokenData.refresh_token || tokenData.token) {
                    const email = tokenData._email || null;
                    const resp = { loggedIn: true, email, loginInProgress: anyLoginInProgress, accounts };
                    if (connName === 'gmail') resp.hasClientSecret = fs.existsSync(GMAIL_CLIENT_SECRET);
                    return res.json(resp);
                }
            }
            const resp = { loggedIn: false, email: null, loginInProgress: anyLoginInProgress, accounts };
            if (connName === 'gmail') resp.hasClientSecret = fs.existsSync(GMAIL_CLIENT_SECRET);
            res.json(resp);
        } catch {
            const resp = { loggedIn: false, email: null, loginInProgress: anyLoginInProgress, accounts: [] };
            if (connName === 'gmail') resp.hasClientSecret = fs.existsSync(GMAIL_CLIENT_SECRET);
            res.json(resp);
        }
    });
}

// Gmail client secret upload endpoint
// Accepts either {client_id, client_secret} or {json: "..."} (the downloaded JSON from Google Cloud Console)
app.post('/api/gmail/client-secret', (req, res) => {
    try {
        let secretData;

        if ('json' in req.body) {
            // User pasted/uploaded the full JSON from Google Cloud Console
            const parsed = typeof req.body.json === 'string' ? JSON.parse(req.body.json) : req.body.json;
            // Google exports as {"installed": {...}} or {"web": {...}}
            const creds = parsed.installed || parsed.web;
            if (!creds || !creds.client_id || !creds.client_secret) {
                return res.status(400).json({ error: 'Invalid JSON — must contain "installed" or "web" with client_id and client_secret.' });
            }
            secretData = { installed: creds };
        } else {
            const { client_id, client_secret } = req.body;
            if (!client_id || !client_secret) {
                return res.status(400).json({ error: 'client_id and client_secret are required (or provide json).' });
            }
            secretData = {
                installed: {
                    client_id,
                    client_secret,
                    auth_uri: 'https://accounts.google.com/o/oauth2/auth',
                    token_uri: 'https://oauth2.googleapis.com/token',
                    redirect_uris: ['http://localhost'],
                },
            };
        }

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
    const accountId = req.body?.accountId || 'default';
    const processKey = `gmail:${accountId}`;

    if (emailLoginProcesses[processKey]) {
        // Kill the existing process so user can retry
        const existing = emailLoginProcesses[processKey];
        console.log(`[${processKey}] Killing previous login process (pid ${existing.pid}) for retry.`);
        try { existing.kill(); } catch { /* already dead */ }
        delete emailLoginProcesses[processKey];
    }

    if (!fs.existsSync(GMAIL_CLIENT_SECRET)) {
        return res.status(400).json({
            status: 'needs_client_secret',
            error: 'OAuth client credentials not configured. Please set up your client ID first.',
        });
    }

    // Determine target token file for this account
    const targetTokenFile = getAccountCredentialFile('gmail', accountId);

    // Run the Python OAuth script with optional --token-file argument
    const oauthScript = path.join(CONNECTORS_DIR, 'gmail', 'oauth_login.py');
    const venvPython = path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
    const pythonCmd = fs.existsSync(venvPython) ? venvPython : 'python3';

    const args = [oauthScript];
    if (accountId !== 'default') {
        args.push('--token-file', targetTokenFile);
    }

    const proc = spawn(pythonCmd, args, {
        stdio: ['ignore', 'pipe', 'pipe'],
        cwd: PROJECT_ROOT,
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });

    emailLoginProcesses[processKey] = proc;
    let stdout = '';
    let stderr = '';
    let responded = false;

    // Auto-kill after 3 minutes if user never completes the login
    const killTimer = setTimeout(() => {
        if (emailLoginProcesses[processKey]) {
            console.log(`[${processKey}] Login timed out after 3 minutes, killing process.`);
            proc.kill();
        }
    }, 180000);

    proc.stdout.on('data', (data) => {
        stdout += data.toString();

        // Try to parse the first JSON line (auth URL) before responding
        if (!responded) {
            const lines = stdout.split('\n');
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const parsed = JSON.parse(line.trim());
                    if (parsed.auth_url) {
                        responded = true;
                        res.json({ status: 'started', authUrl: parsed.auth_url });
                        return;
                    }
                    if (parsed.error) {
                        responded = true;
                        res.status(400).json({ status: 'error', ...parsed });
                        return;
                    }
                } catch { /* not complete JSON yet */ }
            }
        }
    });
    proc.stderr.on('data', (data) => { stderr += data.toString(); });

    proc.on('close', (code) => {
        clearTimeout(killTimer);
        delete emailLoginProcesses[processKey];
        console.log(`[gmail:${accountId}] OAuth login exited with code:`, code);
        if (stderr) console.log(`[gmail:${accountId}] stderr:`, stderr.slice(-300));

        if (code === 0) {
            try {
                // Parse the LAST JSON line (success result — the first was auth_url)
                const lines = stdout.split('\n').filter(l => l.trim());
                const lastLine = lines[lines.length - 1];
                const result = JSON.parse(lastLine);
                console.log(`[gmail:${accountId}] ✅ Logged in as ${result.email || 'unknown'}`);
                // Update or create the account entry in the registry
                const registry = readAccountsRegistry();
                if (!registry.accounts.gmail) registry.accounts.gmail = [];
                const accts = registry.accounts.gmail;
                let acct = accts.find(a => a.id === accountId);
                if (!acct) {
                    // First login — create the registry entry
                    acct = {
                        id: accountId,
                        label: result.email || (accountId === 'default' ? 'Personal Gmail' : accountId),
                        enabled: true,
                        credential_file: accountId === 'default' ? 'gmail_personal.json'
                            : `gmail_account_${accountId}.json`,
                    };
                    accts.push(acct);
                } else if (result.email) {
                    acct.label = result.email;
                }
                writeAccountsRegistry(registry);
            } catch {
                console.log(`[gmail:${accountId}] ✅ Login completed (could not parse output)`);
            }
        } else {
            console.log(`[gmail:${accountId}] ❌ Login failed:`, stdout.slice(-300));
        }

        // If we never responded (e.g. process crashed before emitting auth URL)
        if (!responded) {
            responded = true;
            res.status(500).json({ status: 'error', message: 'Login process exited unexpectedly.' });
        }
    });

    // Timeout: if no auth URL within 15 seconds, respond with fallback
    setTimeout(() => {
        if (!responded) {
            responded = true;
            res.json({ status: 'started', message: 'Login process started. Complete in browser.' });
        }
    }, 15000);
});

// ── Cancel login (kill running OAuth/gcloud process) ─────────────
for (const connName of ['gmail', 'work-email']) {
    app.post(`/api/${connName}/login/cancel`, (req, res) => {
        const accountId = req.body?.accountId || 'default';
        const normalized = connName.replace('-', '_');
        const processKey = `${normalized}:${accountId}`;
        const proc = emailLoginProcesses[processKey];
        if (proc) {
            proc.kill();
            delete emailLoginProcesses[processKey];
            console.log(`[${processKey}] Login cancelled by user.`);
            res.json({ status: 'cancelled' });
        } else {
            res.json({ status: 'not_running' });
        }
    });
}

// ── Work Email login (gcloud ADC flow) ──────────────────────────
app.post('/api/work-email/login', (req, res) => {
    const accountId = req.body?.accountId || 'default';
    const processKey = `work_email:${accountId}`;

    if (emailLoginProcesses[processKey]) {
        const existing = emailLoginProcesses[processKey];
        console.log(`[${processKey}] Killing previous login process (pid ${existing.pid}) for retry.`);
        try { existing.kill(); } catch { /* already dead */ }
        delete emailLoginProcesses[processKey];
    }

    const tokenFile = getAccountCredentialFile('work_email', accountId);

    const proc = spawn('gcloud', [
        'auth', 'application-default', 'login',
        `--scopes=${GMAIL_SCOPES}`,
    ], {
        stdio: ['ignore', 'pipe', 'pipe'],
        shell: true,
    });

    emailLoginProcesses[processKey] = proc;
    let output = '';

    proc.stdout.on('data', (data) => { output += data.toString(); });
    proc.stderr.on('data', (data) => { output += data.toString(); });

    proc.on('close', (code) => {
        delete emailLoginProcesses[processKey];
        console.log(`[work_email:${accountId}] ADC login exited with code:`, code);
        if (output) console.log(`[work_email:${accountId}] output:`, output.slice(-300));

        // gcloud sometimes exits with code 1 even on success (scope warnings).
        // Check if the ADC file was actually updated recently.
        let adcUpdated = false;
        try {
            const stat = fs.statSync(ADC_FILE);
            const ageMs = Date.now() - stat.mtimeMs;
            adcUpdated = ageMs < 60000; // updated within last 60 seconds
        } catch { /* file doesn't exist */ }

        if (code !== 0 && !adcUpdated) {
            console.log(`[work_email:${accountId}] Login failed (no fresh ADC file).`);
            return;
        }

        console.log(`[work_email:${accountId}] Login succeeded. Running post-login setup...`);

        const run = (cmd) => {
            try {
                return execSync(cmd, { encoding: 'utf-8', timeout: 30000 }).trim();
            } catch (e) {
                console.log(`[work_email] Command failed: ${cmd}`, e.message?.slice(0, 200));
                return null;
            }
        };

        // 1. Read ADC file and save immediately (so UI detects login fast)
        let adcData;
        try {
            adcData = JSON.parse(fs.readFileSync(ADC_FILE, 'utf-8'));
            fs.mkdirSync(path.dirname(tokenFile), { recursive: true });
            fs.writeFileSync(tokenFile, JSON.stringify(adcData, null, 2));
            console.log(`[work_email:${accountId}] ✅ Saved initial credentials (UI should detect login now)`);

            // Ensure account entry exists in registry so UI sees it immediately
            const registry = readAccountsRegistry();
            if (!registry.accounts.work_email) registry.accounts.work_email = [];
            if (!registry.accounts.work_email.find(a => a.id === accountId)) {
                registry.accounts.work_email.push({
                    id: accountId,
                    label: accountId === 'default' ? 'Work Email' : accountId,
                    enabled: true,
                    credential_file: accountId === 'default' ? 'gmail_work.json'
                        : `work_email_account_${accountId}.json`,
                });
                writeAccountsRegistry(registry);
            }
        } catch (e) {
            console.log(`[work_email:${accountId}] ⚠ Could not save token file:`, e.message);
            return;
        }

        // 2. Async: detect email + setup project (UI already shows "Connected")
        (async () => {
            // 2a. Detect email from the actual ADC token via userinfo API
            let userEmail = null;
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
                        userEmail = userData.email;
                        console.log(`[work_email:${accountId}] ✅ Detected email: ${userEmail}`);
                    }
                }
            } catch (e) {
                console.log(`[work_email:${accountId}] ⚠ Could not detect email:`, e.message);
            }

            // 2b. Find the right quota project
            let quotaProject = run('gcloud config get-value project 2>/dev/null');
            if (!quotaProject) {
                const env = readEnv();
                if (env['FIREBASE_PROJECT_ID']) quotaProject = env['FIREBASE_PROJECT_ID'];
            }
            if (!quotaProject) {
                quotaProject = run('gcloud projects list --format="value(projectId)" --limit=1 2>/dev/null');
            }

            // 2c. Enable Gmail API on the project
            if (quotaProject) {
                console.log(`[work_email:${accountId}] Enabling Gmail API on ${quotaProject}...`);
                run(`gcloud services enable gmail.googleapis.com --project=${quotaProject} 2>/dev/null`);
            }

            // 2d. Grant serviceUsageConsumer to the authenticated user
            if (userEmail && quotaProject) {
                console.log(`[work_email:${accountId}] Granting serviceUsageConsumer to ${userEmail} on ${quotaProject}...`);
                run(`gcloud projects add-iam-policy-binding ${quotaProject} --member="user:${userEmail}" --role="roles/serviceusage.serviceUsageConsumer" --condition=None --quiet 2>/dev/null`);
            }

            // 2e. Re-save token with email + quota project
            try {
                if (userEmail) adcData._email = userEmail;
                if (quotaProject) adcData.quota_project_id = quotaProject;
                fs.writeFileSync(tokenFile, JSON.stringify(adcData, null, 2));
                console.log(`[work_email:${accountId}] ✅ Updated token: email=${userEmail}, quota=${quotaProject}`);
                // Update or create the account entry in the registry
                {
                    const registry = readAccountsRegistry();
                    if (!registry.accounts.work_email) registry.accounts.work_email = [];
                    const accts = registry.accounts.work_email;
                    let acct = accts.find(a => a.id === accountId);
                    if (!acct) {
                        acct = {
                            id: accountId,
                            label: userEmail || (accountId === 'default' ? 'Work Email' : accountId),
                            enabled: true,
                            credential_file: accountId === 'default' ? 'gmail_work.json'
                                : `work_email_account_${accountId}.json`,
                        };
                        accts.push(acct);
                    } else if (userEmail) {
                        acct.label = userEmail;
                    }
                    writeAccountsRegistry(registry);
                }
            } catch (e) {
                console.log(`[work_email:${accountId}] ⚠ Could not update token file:`, e.message);
            }

            console.log(`[work_email:${accountId}] ✅ Post-login setup complete!`);
        })();
    });

    res.json({ status: 'started', message: 'Browser should open for Work Email login. Complete the login there.' });
});

// ── Disconnect endpoint ─────────────────────────────────────────

app.post('/api/connector/:name/disconnect', (req, res) => {
    const { name } = req.params;
    const accountId = req.body?.accountId;
    try {
        if (name === 'firebase') {
            const env = readEnv();
            if (env['FIREBASE_PROJECT_ID']) {
                writeEnv({ FIREBASE_PROJECT_ID: '' });
            }
            return res.json({ success: true, message: 'Firebase disconnected. Project ID cleared.' });
        }

        if (name === 'gmail' || name === 'work_email') {
            if (accountId) {
                // Disconnect a specific account
                const credFile = getAccountCredentialFile(name, accountId);
                if (fs.existsSync(credFile)) fs.unlinkSync(credFile);
                return res.json({ success: true, message: `Account "${accountId}" disconnected.` });
            }
            // Legacy: disconnect default account
            const tokenFile = EMAIL_TOKEN_FILES[name];
            if (tokenFile && fs.existsSync(tokenFile)) {
                fs.unlinkSync(tokenFile);
            }
            const label = name === 'gmail' ? 'Gmail' : 'Work Email';
            return res.json({ success: true, message: `${label} disconnected. Token removed.` });
        }

        if (accountId) {
            // Disconnect a specific env-var account
            const registry = readAccountsRegistry();
            const accts = registry.accounts[name] || [];
            const acct = accts.find(a => a.id === accountId);
            if (acct) {
                const envKeys = acct.env_key ? [acct.env_key] : Object.values(acct.env_keys || {});
                const updates = {};
                for (const k of envKeys) updates[k] = '';
                writeEnv(updates);
                return res.json({ success: true, message: `Account "${accountId}" disconnected.` });
            }
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

// ── Accounts API ────────────────────────────────────────────────

// Get full accounts registry
app.get('/api/accounts', (req, res) => {
    res.json(readAccountsRegistry());
});

// Add account to a connector
app.post('/api/accounts/:connector/add', (req, res) => {
    const { connector } = req.params;
    const { id, label, envValues } = req.body;
    if (!id || !label) {
        return res.status(400).json({ error: 'id and label are required' });
    }
    if (!/^[a-z0-9_-]+$/.test(id)) {
        return res.status(400).json({ error: 'id must be lowercase alphanumeric with hyphens/underscores' });
    }
    try {
        const registry = readAccountsRegistry();
        if (!registry.accounts[connector]) registry.accounts[connector] = [];
        if (registry.accounts[connector].find(a => a.id === id)) {
            return res.status(409).json({ error: `Account "${id}" already exists for ${connector}` });
        }

        const entry = { id, label, enabled: true };

        // Determine credential storage based on connector type
        if (connector === 'gmail' || connector === 'work_email') {
            entry.credential_file = `${connector}_account_${id}.json`;
        } else {
            // For env-var connectors, derive env key names from the connector's existing pattern
            const connectors = discoverConnectors();
            const connDef = connectors.find(c => c.name === connector);
            if (connDef && connDef.envVars.length === 1) {
                const derivedKey = `${connDef.envVars[0].key}_${id.toUpperCase().replace(/-/g, '_')}`;
                entry.env_key = derivedKey;
                // Save the actual credential value to .env if provided
                if (envValues && envValues[connDef.envVars[0].key]) {
                    writeEnv({ [derivedKey]: envValues[connDef.envVars[0].key] });
                }
            } else if (connDef && connDef.envVars.length > 1) {
                const keys = {};
                const envUpdates = {};
                for (const v of connDef.envVars) {
                    const derivedKey = `${v.key}_${id.toUpperCase().replace(/-/g, '_')}`;
                    keys[v.key] = derivedKey;
                    // Save the actual credential value to .env if provided
                    if (envValues && envValues[v.key]) {
                        envUpdates[derivedKey] = envValues[v.key];
                    }
                }
                entry.env_keys = keys;
                if (Object.keys(envUpdates).length > 0) {
                    writeEnv(envUpdates);
                }
            }
        }

        registry.accounts[connector].push(entry);
        writeAccountsRegistry(registry);
        res.json({ success: true, account: entry });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Toggle account enable/disable
app.post('/api/accounts/:connector/:id/toggle', (req, res) => {
    const { connector, id } = req.params;
    const { enabled } = req.body;
    try {
        const registry = readAccountsRegistry();
        const accts = registry.accounts[connector] || [];
        const acct = accts.find(a => a.id === id);
        if (!acct) return res.status(404).json({ error: 'Account not found' });
        acct.enabled = !!enabled;
        writeAccountsRegistry(registry);
        res.json({ success: true, account: acct });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Remove account entirely
app.post('/api/accounts/:connector/:id/remove', (req, res) => {
    const { connector, id } = req.params;
    if (id === 'default') {
        return res.status(400).json({ error: 'Cannot remove the default account. Use disconnect instead.' });
    }
    try {
        const registry = readAccountsRegistry();
        const accts = registry.accounts[connector] || [];
        const idx = accts.findIndex(a => a.id === id);
        if (idx === -1) return res.status(404).json({ error: 'Account not found' });

        const acct = accts[idx];
        // Delete credential file if it exists
        if (acct.credential_file) {
            const credFile = path.join(CLAWFOUNDER_DIR, acct.credential_file);
            if (fs.existsSync(credFile)) fs.unlinkSync(credFile);
        }
        // Clear env vars if applicable
        if (acct.env_key) {
            writeEnv({ [acct.env_key]: '' });
        } else if (acct.env_keys) {
            const updates = {};
            for (const k of Object.values(acct.env_keys)) updates[k] = '';
            writeEnv(updates);
        }

        accts.splice(idx, 1);
        writeAccountsRegistry(registry);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Rename account
app.post('/api/accounts/:connector/:id/rename', (req, res) => {
    const { connector, id } = req.params;
    const { label } = req.body;
    if (!label) return res.status(400).json({ error: 'label is required' });
    try {
        const registry = readAccountsRegistry();
        const accts = registry.accounts[connector] || [];
        const acct = accts.find(a => a.id === id);
        if (!acct) return res.status(404).json({ error: 'Account not found' });
        acct.label = label;
        writeAccountsRegistry(registry);
        res.json({ success: true, account: acct });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Disconnect one account (clear creds, keep entry)
app.post('/api/accounts/:connector/:id/disconnect', (req, res) => {
    const { connector, id } = req.params;
    try {
        const registry = readAccountsRegistry();
        const accts = registry.accounts[connector] || [];
        const acct = accts.find(a => a.id === id);
        if (!acct) return res.status(404).json({ error: 'Account not found' });

        if (acct.credential_file) {
            const credFile = path.join(CLAWFOUNDER_DIR, acct.credential_file);
            if (fs.existsSync(credFile)) fs.unlinkSync(credFile);
        } else if (connector === 'gmail' || connector === 'work_email') {
            const credFile = getAccountCredentialFile(connector, id);
            if (fs.existsSync(credFile)) fs.unlinkSync(credFile);
        } else if (acct.env_key) {
            writeEnv({ [acct.env_key]: '' });
        } else if (acct.env_keys) {
            const updates = {};
            for (const k of Object.values(acct.env_keys)) updates[k] = '';
            writeEnv(updates);
        }
        res.json({ success: true, message: `Account "${id}" disconnected.` });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Disconnect ALL accounts for a connector
app.post('/api/accounts/:connector/disconnect-all', (req, res) => {
    const { connector } = req.params;
    try {
        const registry = readAccountsRegistry();
        const accts = registry.accounts[connector] || [];
        for (const acct of accts) {
            if (acct.credential_file) {
                const credFile = path.join(CLAWFOUNDER_DIR, acct.credential_file);
                if (fs.existsSync(credFile)) fs.unlinkSync(credFile);
            } else if (connector === 'gmail' || connector === 'work_email') {
                const credFile = getAccountCredentialFile(connector, acct.id);
                if (fs.existsSync(credFile)) fs.unlinkSync(credFile);
            } else if (acct.env_key) {
                writeEnv({ [acct.env_key]: '' });
            } else if (acct.env_keys) {
                const updates = {};
                for (const k of Object.values(acct.env_keys)) updates[k] = '';
                writeEnv(updates);
            }
        }
        res.json({ success: true, message: `All ${connector} accounts disconnected.` });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Toggle all accounts for a connector
app.post('/api/accounts/:connector/toggle-all', (req, res) => {
    const { connector } = req.params;
    const { enabled } = req.body;
    try {
        const registry = readAccountsRegistry();
        const accts = registry.accounts[connector] || [];
        for (const acct of accts) acct.enabled = !!enabled;
        writeAccountsRegistry(registry);
        res.json({ success: true });
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

// ── Briefing config endpoints ──────────────────────────────────

app.get('/api/briefing/config', (req, res) => {
    try {
        if (fs.existsSync(BRIEFING_CONFIG_FILE)) {
            const data = JSON.parse(fs.readFileSync(BRIEFING_CONFIG_FILE, 'utf-8'));
            return res.json(data);
        }
    } catch (err) {
        console.error('[briefing/config] Read error:', err.message);
    }
    res.json({ version: 1, connectors: {} });
});

app.post('/api/briefing/config', (req, res) => {
    try {
        if (!fs.existsSync(CLAWFOUNDER_DIR)) {
            fs.mkdirSync(CLAWFOUNDER_DIR, { recursive: true });
        }
        const config = { version: 1, ...req.body };
        fs.writeFileSync(BRIEFING_CONFIG_FILE, JSON.stringify(config, null, 2));
        res.json({ ok: true });
    } catch (err) {
        console.error('[briefing/config] Write error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── Yahoo Finance ticker search ─────────────────────────────────

app.get('/api/yahoo/search', (req, res) => {
    const q = (req.query.q || '').trim();
    if (!q) return res.json({ results: [] });

    const uvVenvPython = path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
    const venvPython = path.join(PROJECT_ROOT, 'venv', 'bin', 'python3');
    const pythonCmd = fs.existsSync(uvVenvPython) ? uvVenvPython : fs.existsSync(venvPython) ? venvPython : 'python3';

    const script = `
import sys, json
sys.path.insert(0, "${PROJECT_ROOT.replace(/\\/g, '\\\\')}")
from connectors.yahoo_finance.connector import handle
result = handle("yahoo_finance_search", {"query": ${JSON.stringify(q)}, "max_results": 8})
print(result)
`;
    const proc = spawn(pythonCmd, ['-c', script], { cwd: PROJECT_ROOT });

    let out = '';
    let err = '';
    proc.stdout.on('data', d => out += d.toString());
    proc.stderr.on('data', d => err += d.toString());
    proc.on('close', (code) => {
        if (code !== 0) {
            console.error('[yahoo/search] Error:', err);
            return res.status(500).json({ error: err || 'Search failed' });
        }
        try {
            res.json({ results: JSON.parse(out) });
        } catch {
            res.status(500).json({ error: 'Failed to parse search results' });
        }
    });
});

// ── GitHub repos helper (for briefing settings) ────────────────

app.get('/api/github/repos', (req, res) => {
    const envVars = { ...process.env, ...readEnv() };
    const uvVenvPython = path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
    const venvPython = path.join(PROJECT_ROOT, 'venv', 'bin', 'python3');
    const pythonCmd = fs.existsSync(uvVenvPython) ? uvVenvPython : fs.existsSync(venvPython) ? venvPython : 'python3';

    // Pass account_id if provided — connector will resolve the right token
    const accountId = req.query.account_id || '';
    const acctArg = accountId ? `, account_id="${accountId}"` : '';
    const script = `
import sys, json
sys.path.insert(0, "${PROJECT_ROOT.replace(/\\/g, '\\\\')}")
from connectors.github.connector import handle
result = handle("github_list_repos", {"max_results": 100}${acctArg})
print(result)
`;
    const proc = spawn(pythonCmd, ['-c', script], {
        cwd: PROJECT_ROOT,
        env: envVars,
    });

    let out = '';
    let err = '';
    proc.stdout.on('data', d => out += d.toString());
    proc.stderr.on('data', d => err += d.toString());
    proc.on('close', (code) => {
        if (code !== 0) {
            console.error('[github/repos] Error:', err);
            return res.status(500).json({ error: err || 'Failed to fetch repos' });
        }
        try {
            res.json({ repos: JSON.parse(out) });
        } catch {
            res.status(500).json({ error: 'Failed to parse repo list' });
        }
    });
});

// ── Briefing SSE endpoint ───────────────────────────────────────

app.post('/api/briefing', (req, res) => {
    const { provider, briefing_config } = req.body;
    console.log(`[briefing] Generating briefing with provider=${provider}`);

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    res.flushHeaders();

    const envVars = { ...process.env, ...readEnv() };
    const pyScript = path.join(__dirname, 'briefing_agent.py');
    const uvVenvPython = path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
    const venvPython = path.join(PROJECT_ROOT, 'venv', 'bin', 'python3');
    const pythonCmd = fs.existsSync(uvVenvPython) ? uvVenvPython : fs.existsSync(venvPython) ? venvPython : 'python3';

    const proc = spawn(pythonCmd, [pyScript], {
        cwd: PROJECT_ROOT,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: envVars,
    });

    let processExited = false;

    proc.on('error', (err) => {
        console.error('[briefing] Spawn error:', err);
        res.write(`data: ${JSON.stringify({ type: 'error', error: `Spawn error: ${err.message}` })}\n\n`);
        res.end();
    });

    proc.stdin.write(JSON.stringify({
        provider: provider || 'gemini',
        briefing_config: briefing_config || {},
    }));
    proc.stdin.end();

    let buffer = '';
    proc.stdout.on('data', (data) => {
        const chunk = data.toString();
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
        console.error('[briefing stderr]', data.toString().trim());
    });

    proc.on('close', (code) => {
        processExited = true;
        console.log(`[briefing] Process exited with code ${code}`);
        if (buffer.trim()) {
            res.write(`data: ${buffer}\n\n`);
        }
        res.write(`data: ${JSON.stringify({ type: 'done' })}\n\n`);
        res.end();
    });

    res.on('close', () => {
        if (!processExited) {
            console.log('[briefing] Client disconnected, killing process');
            proc.kill();
        }
    });
});

// ── SPA fallback — serve index.html for non-API routes ──────────
if (fs.existsSync(DIST_DIR)) {
    app.get('/{*path}', (req, res, next) => {
        if (req.path.startsWith('/api') || req.path.startsWith('/ws')) return next();
        res.sendFile(path.join(DIST_DIR, 'index.html'));
    });
}

// ── Start ───────────────────────────────────────────────────────
const PORT = process.env.PORT || 3001;
const server = app.listen(PORT, () => {
    ensureAccountsRegistry();
    console.log(`🦀 ClawFounder API running on http://localhost:${PORT}`);
});

// ── Voice WebSocket (Gemini Live API bridge) ────────────────────

const wss = new WebSocketServer({ server, path: '/ws/voice' });

wss.on('connection', (ws) => {
    console.log('[voice] WebSocket client connected');

    const envVars = { ...process.env, ...readEnv() };
    const voiceScript = path.join(__dirname, 'voice_agent.py');
    const uvVenvPython = path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
    const venvPython = path.join(PROJECT_ROOT, 'venv', 'bin', 'python3');
    const pythonCmd = fs.existsSync(uvVenvPython) ? uvVenvPython
        : fs.existsSync(venvPython) ? venvPython : 'python3';

    const proc = spawn(pythonCmd, [voiceScript], {
        cwd: PROJECT_ROOT,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: envVars,
    });

    let procAlive = true;

    // Prevent EPIPE from crashing the server
    proc.stdin.on('error', (err) => {
        if (err.code === 'EPIPE' || err.code === 'ERR_STREAM_DESTROYED') {
            console.log('[voice] Python stdin closed (process exited)');
        } else {
            console.error('[voice] stdin error:', err.message);
        }
        procAlive = false;
    });

    // Send setup message with API key
    proc.stdin.write(JSON.stringify({
        type: 'setup',
        api_key: envVars['GEMINI_API_KEY'] || '',
    }) + '\n');

    // Browser → Python: forward audio/control messages
    ws.on('message', (data) => {
        if (!procAlive) return;
        try {
            const msg = JSON.parse(data.toString());
            proc.stdin.write(JSON.stringify(msg) + '\n');
        } catch (e) {
            console.error('[voice] Bad message from client:', e.message);
        }
    });

    // Python → Browser: forward JSONL events
    let buffer = '';
    proc.stdout.on('data', (chunk) => {
        buffer += chunk.toString();
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line in buffer
        for (const line of lines) {
            if (line.trim() && ws.readyState === ws.OPEN) {
                ws.send(line);
            }
        }
    });

    proc.stderr.on('data', (d) => {
        const msg = d.toString().trim();
        if (msg) console.error('[voice stderr]', msg);
    });

    // Cleanup on disconnect
    ws.on('close', () => {
        console.log('[voice] WebSocket client disconnected');
        if (procAlive) {
            try { proc.stdin.write(JSON.stringify({ type: 'end' }) + '\n'); } catch {}
        }
        setTimeout(() => { try { proc.kill(); } catch {} }, 1000);
    });

    proc.on('close', (code) => {
        console.log(`[voice] Python process exited: ${code}`);
        procAlive = false;
        if (ws.readyState === ws.OPEN) ws.close();
    });
});
