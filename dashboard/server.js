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
import { spawn } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const ENV_FILE = path.join(PROJECT_ROOT, '.env');
const CONNECTORS_DIR = path.join(PROJECT_ROOT, 'connectors');
const FIREBASE_CONFIG = path.join(os.homedir(), '.config', 'configstore', 'firebase-tools.json');

const app = express();
app.use(cors());
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
        const value = trimmed.slice(eqIndex + 1).trim();
        env[key] = value;
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

        // Firebase uses Google login, not manual keys
        const usesGoogleLogin = folder.name === 'firebase';

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
    res.json({ config: masked, raw: env });
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
    // Use venv Python if available (has google-genai SDK)
    const venvPython = path.join(PROJECT_ROOT, 'venv', 'bin', 'python3');
    const pythonCmd = fs.existsSync(venvPython) ? venvPython : 'python3';
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
