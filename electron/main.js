const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let pythonProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '../assets/icon.png'),
    titleBarStyle: 'default',
    show: false
  });

  // Load the HTML file
  mainWindow.loadFile(path.join(__dirname, '../web/index.html'));

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

// Python script execution
function getPythonPath() {
  if (process.platform === 'win32') {
    return 'python';
  }
  return 'python3';
}

function getScriptPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'netprobe.py');
  }
  return path.join(__dirname, '../netprobe.py');
}

// IPC handlers
ipcMain.handle('run-netprobe', async (event, options) => {
  return new Promise((resolve, reject) => {
    const pythonPath = getPythonPath();
    const scriptPath = getScriptPath();

    let args = [scriptPath];

    // Build command line arguments
    if (options.duration) {
      args.push('--duration', options.duration.toString());
    }
    if (options.location) {
      args.push('--location', options.location);
    }
    if (options.detectLocation) {
      args.push('--detect-location');
    }
    if (options.compareVpn) {
      args.push('--compare-vpn');
    }
    if (options.debug) {
      args.push('--debug');
    }
    if (options.json) {
      args.push('--json', options.json);
    }

    console.log('Running:', pythonPath, args.join(' '));

    pythonProcess = spawn(pythonPath, args, {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      const output = data.toString();
      stdout += output;
      // Send progress updates to renderer
      event.sender.send('netprobe-progress', output);
    });

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    pythonProcess.on('close', (code) => {
      pythonProcess = null;
      if (code === 0) {
        resolve({ success: true, output: stdout });
      } else {
        reject({ success: false, error: stderr, code });
      }
    });

    pythonProcess.on('error', (error) => {
      pythonProcess = null;
      reject({ success: false, error: error.message });
    });
  });
});

ipcMain.handle('stop-netprobe', async () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
    return { success: true };
  }
  return { success: false, message: 'No running process' };
});

ipcMain.handle('save-file', async (event, data) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath: 'netprobe-results.json',
    filters: [
      { name: 'JSON Files', extensions: ['json'] },
      { name: 'CSV Files', extensions: ['csv'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });

  if (!result.canceled) {
    try {
      fs.writeFileSync(result.filePath, data);
      return { success: true, path: result.filePath };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }
  return { success: false, canceled: true };
});

ipcMain.handle('get-recent-results', async () => {
  console.log('🔍 Main: Getting recent results...');
  try {
    const resultsDir = path.join(__dirname, '../results');
    console.log('📁 Main: Looking in results directory:', resultsDir);

    if (!fs.existsSync(resultsDir)) {
      console.log('⚠️ Main: Results directory does not exist');
      return [];
    }

    const allFiles = fs.readdirSync(resultsDir);
    console.log('📂 Main: All files in results directory:', allFiles);

    const jsonFiles = allFiles.filter(file => file.endsWith('.json'));
    console.log('📋 Main: JSON files found:', jsonFiles);

    const files = jsonFiles
      .map(file => {
        const filePath = path.join(resultsDir, file);
        const stats = fs.statSync(filePath);
        const fileInfo = {
          name: file,
          path: filePath,
          modified: stats.mtime,
          size: stats.size
        };
        console.log('📄 Main: File info:', fileInfo);
        return fileInfo;
      })
      .sort((a, b) => b.modified - a.modified)
      .slice(0, 10); // Get 10 most recent

    console.log('✅ Main: Returning files:', files.length);
    return files;
  } catch (error) {
    console.error('❌ Main: Error getting recent results:', error);
    return [];
  }
});

ipcMain.handle('load-result-file', async (event, filePath) => {
  try {
    const data = fs.readFileSync(filePath, 'utf8');
    return { success: true, data: JSON.parse(data) };
  } catch (error) {
    return { success: false, error: error.message };
  }
});