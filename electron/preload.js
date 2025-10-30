const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  runNetProbe: (options) => ipcRenderer.invoke('run-netprobe', options),
  stopNetProbe: () => ipcRenderer.invoke('stop-netprobe'),
  saveFile: (data) => ipcRenderer.invoke('save-file', data),
  getRecentResults: () => ipcRenderer.invoke('get-recent-results'),
  loadResultFile: (filePath) => ipcRenderer.invoke('load-result-file', filePath),

  // Event listeners
  onProgress: (callback) => {
    ipcRenderer.on('netprobe-progress', (event, data) => callback(data));
  },

  removeProgressListener: () => {
    ipcRenderer.removeAllListeners('netprobe-progress');
  }
});