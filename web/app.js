class NetProbeApp {
    constructor() {
        this.isRunning = false;
        this.currentResults = null;
        this.progressInterval = null;

        this.initializeElements();
        this.bindEvents();
        this.loadRecentResults();
    }

    initializeElements() {
        // Form elements
        this.durationInput = document.getElementById('duration');
        this.locationInput = document.getElementById('location');
        this.detectLocationCheckbox = document.getElementById('detect-location');
        this.compareVpnCheckbox = document.getElementById('compare-vpn');
        this.debugCheckbox = document.getElementById('debug');
        this.exportFileInput = document.getElementById('export-file');

        // Button elements
        this.startButton = document.getElementById('start-test');
        this.stopButton = document.getElementById('stop-test');
        this.exportButton = document.getElementById('export-results');
        this.newTestButton = document.getElementById('new-test');
        this.toggleAdvancedButton = document.getElementById('toggle-advanced');
        this.toggleOutputButton = document.getElementById('toggle-output');

        // Advanced options
        this.advancedOptions = document.getElementById('advanced-options');
        this.toggleIcon = document.getElementById('toggle-icon');
        this.outputToggleIcon = document.getElementById('output-toggle-icon');

        // Status and results elements
        this.testStatus = document.getElementById('test-status');
        this.progressContainer = document.getElementById('progress-container');
        this.progressFill = document.getElementById('progress-fill');
        this.progressText = document.getElementById('progress-text');
        this.liveOutput = document.getElementById('live-output');
        this.resultsSummary = document.getElementById('results-summary');
        this.resultsActions = document.getElementById('results-actions');

        // Metric elements
        this.latencyValue = document.getElementById('latency-value');
        this.packetLossValue = document.getElementById('packet-loss-value');
        this.jitterValue = document.getElementById('jitter-value');
        this.downloadValue = document.getElementById('download-value');
        this.uploadValue = document.getElementById('upload-value');
        this.qualityScore = document.getElementById('quality-score');

        // History elements
        this.historyList = document.getElementById('history-list');
    }

    bindEvents() {
        this.startButton.addEventListener('click', () => this.startTest());
        this.stopButton.addEventListener('click', () => this.stopTest());
        this.exportButton.addEventListener('click', () => this.exportResults());
        this.newTestButton.addEventListener('click', () => this.resetInterface());
        this.toggleAdvancedButton.addEventListener('click', () => this.toggleAdvanced());
        this.toggleOutputButton.addEventListener('click', () => this.toggleOutput());

        // Listen for progress updates from main process
        window.electronAPI.onProgress((data) => {
            this.updateLiveOutput(data);
        });

        // Auto-detect location checkbox handler
        this.detectLocationCheckbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                this.locationInput.disabled = true;
                this.locationInput.placeholder = 'Auto-detecting...';
            } else {
                this.locationInput.disabled = false;
                this.locationInput.placeholder = 'e.g., Home Office, Starbucks NYC';
            }
        });
    }

    async loadRecentResults() {
        console.log('🔄 Loading recent results...');
        try {
            const results = await window.electronAPI.getRecentResults();
            console.log('📁 Recent results loaded:', results);
            console.log('📊 Results count:', results.length);
            this.displayHistoryResults(results);
        } catch (error) {
            console.error('❌ Failed to load recent results:', error);
        }
    }

    displayHistoryResults(results) {
        console.log('🎨 Displaying history results, count:', results.length);

        if (results.length === 0) {
            console.log('📭 No results to display');
            this.historyList.innerHTML = '<p class="no-results">No previous test results found.</p>';
            return;
        }

        console.log('📋 Rendering results list...');
        this.historyList.innerHTML = results.map((result, index) => {
            console.log(`📄 Processing result ${index}:`, result);
            const date = new Date(result.modified).toLocaleString();
            const size = (result.size / 1024).toFixed(1) + ' KB';

            return `
                <div class="history-item" data-path="${result.path}">
                    <div class="history-item-header">
                        <span class="history-item-name">${result.name}</span>
                        <span class="history-item-date">${date}</span>
                    </div>
                    <div class="history-item-summary">${size}</div>
                </div>
            `;
        }).join('');

        console.log('🖱️ Adding click handlers...');
        // Add click handlers for history items
        this.historyList.querySelectorAll('.history-item').forEach((item, index) => {
            console.log(`🔗 Adding click handler for item ${index}`);
            item.addEventListener('click', () => {
                console.log('🖱️ History item clicked:', item.dataset.path);
                this.loadHistoryResult(item.dataset.path);
            });
        });
        console.log('✅ History display complete');
    }

    async loadHistoryResult(filePath) {
        try {
            const result = await window.electronAPI.loadResultFile(filePath);
            if (result.success) {
                this.currentResults = result.data;
                this.displayResults(result.data);
                this.updateStatus('complete', '✅', 'Results loaded from history');
            } else {
                this.updateStatus('error', '❌', `Failed to load results: ${result.error}`);
            }
        } catch (error) {
            this.updateStatus('error', '❌', `Failed to load results: ${error.message}`);
        }
    }

    getTestOptions() {
        return {
            duration: parseInt(this.durationInput.value) || 30,
            location: this.locationInput.value.trim() || null,
            detectLocation: this.detectLocationCheckbox.checked,
            compareVpn: this.compareVpnCheckbox.checked,
            debug: this.debugCheckbox.checked,
            json: this.exportFileInput.value.trim() || null
        };
    }

    async startTest() {
        if (this.isRunning) return;

        this.isRunning = true;
        this.updateButtonStates();
        this.resetResults();
        this.updateStatus('running', '🔄', 'Starting test...');
        this.showProgress();

        const options = this.getTestOptions();

        try {
            this.startProgressSimulation(options.duration);
            const result = await window.electronAPI.runNetProbe(options);

            if (result.success) {
                this.parseAndDisplayResults(result.output);
                this.updateStatus('complete', '✅', 'Test completed successfully');
                this.loadRecentResults(); // Refresh history
            } else {
                this.updateStatus('error', '❌', 'Test failed');
                this.updateLiveOutput(`Error: ${result.error}`);
            }
        } catch (error) {
            this.updateStatus('error', '❌', 'Test failed');
            this.updateLiveOutput(`Error: ${error.error || error.message}`);
        } finally {
            this.isRunning = false;
            this.stopProgressSimulation();
            this.updateButtonStates();
            this.hideProgress();
        }
    }

    async stopTest() {
        if (!this.isRunning) return;

        try {
            await window.electronAPI.stopNetProbe();
            this.updateStatus('idle', '⏹️', 'Test stopped');
        } catch (error) {
            this.updateStatus('error', '❌', 'Failed to stop test');
        }
    }

    startProgressSimulation(estimatedDuration) {
        this.testStartTime = Date.now();
        this.estimatedDuration = estimatedDuration;
        let elapsed = 0;

        this.progressInterval = setInterval(() => {
            elapsed = Math.floor((Date.now() - this.testStartTime) / 1000);

            // Use actual elapsed time, but show estimated until we exceed it
            if (elapsed <= this.estimatedDuration) {
                const progress = Math.min((elapsed / this.estimatedDuration) * 100, 95);
                this.progressFill.style.width = `${progress}%`;
                this.progressText.textContent = `Testing... ${elapsed}/${this.estimatedDuration}s`;
            } else {
                // Test is running longer than expected
                const progress = 95; // Keep at 95% but update time
                this.progressFill.style.width = `${progress}%`;
                this.progressText.textContent = `Testing... ${elapsed}s (${elapsed - this.estimatedDuration}s over estimate)`;
            }
        }, 1000);
    }

    stopProgressSimulation() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
        this.progressFill.style.width = '100%';
        this.progressText.textContent = 'Processing results...';
    }

    parseAndDisplayResults(output) {
        console.log('🔍 Parsing results from output...');
        try {
            // Try to parse JSON from the output (if --json flag was used)
            const jsonMatch = output.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                console.log('📋 Found JSON in output, parsing...');
                const rawData = JSON.parse(jsonMatch[0]);
                console.log('📊 Raw JSON data:', rawData);

                // Convert the nested structure to flat structure for display
                const flatResults = this.flattenResults(rawData);
                console.log('📈 Flattened results:', flatResults);

                this.currentResults = flatResults;
                this.displayResults(flatResults);
                return;
            }

            // Otherwise parse text output
            console.log('📝 No JSON found, parsing text output...');
            this.parseTextOutput(output);
        } catch (error) {
            console.error('❌ Failed to parse results:', error);
            this.updateLiveOutput('Results parsing failed. Raw output above.');
        }
    }

    flattenResults(data) {
        console.log('🔧 Flattening nested results structure...');

        // Extract the first statistics entry
        const stats = data.statistics && data.statistics[0];
        const bandwidth = data.test_results && data.test_results[0] && data.test_results[0].bandwidth;

        if (!stats) {
            console.log('⚠️ No statistics found in data');
            return {};
        }

        const flattened = {
            // Latency
            avg_latency: stats.latency_stats?.avg_ms,
            min_latency: stats.latency_stats?.min_ms,
            max_latency: stats.latency_stats?.max_ms,

            // Packet Loss
            packet_loss: stats.packet_loss_stats?.avg_percent,

            // Jitter
            avg_jitter: stats.jitter_stats?.avg_ms,
            jitter: stats.jitter_stats?.avg_ms, // Alias for compatibility

            // DNS
            dns_resolution: stats.dns_stats?.avg_ms,

            // Bandwidth
            download_speed: bandwidth?.download_speed_mbps,
            upload_speed: null, // Not measured by default

            // Quality
            quality_score: stats.quality_score,

            // Test info
            test_duration: data.test_results?.[0] ?
                (new Date(data.test_results[0].end_time) - new Date(data.test_results[0].start_time)) / 1000 : null
        };

        console.log('✅ Flattened structure created:', flattened);
        return flattened;
    }

    parseTextOutput(output) {
        // Simple text parsing for key metrics
        const results = {
            latency: this.extractMetric(output, /Average Latency.*?(\d+\.?\d*)\s*ms/i),
            packet_loss: this.extractMetric(output, /Packet Loss.*?(\d+\.?\d*)\s*%/i),
            jitter: this.extractMetric(output, /Jitter.*?(\d+\.?\d*)\s*ms/i),
            download_speed: this.extractMetric(output, /Download.*?(\d+\.?\d*)\s*Mbps/i),
            upload_speed: this.extractMetric(output, /Upload.*?(\d+\.?\d*)\s*Mbps/i),
            quality_score: this.extractMetric(output, /Quality Score.*?(\d+\.?\d*)\s*%/i)
        };

        this.currentResults = results;
        this.displayResults(results);
    }

    extractMetric(text, regex) {
        const match = text.match(regex);
        return match ? parseFloat(match[1]) : null;
    }

    displayResults(results) {
        this.latencyValue.textContent = this.formatValue(results.latency || results.avg_latency);
        this.packetLossValue.textContent = this.formatValue(results.packet_loss);
        this.jitterValue.textContent = this.formatValue(results.jitter || results.avg_jitter);
        this.downloadValue.textContent = this.formatValue(results.download_speed);
        this.uploadValue.textContent = this.formatValue(results.upload_speed);
        this.qualityScore.textContent = this.formatValue(results.quality_score);

        this.resultsSummary.style.display = 'grid';
        this.resultsActions.style.display = 'flex';
    }

    formatValue(value) {
        if (value === null || value === undefined) return '-';
        return typeof value === 'number' ? value.toFixed(2) : value;
    }

    updateLiveOutput(data) {
        this.liveOutput.textContent += data;
        this.liveOutput.scrollTop = this.liveOutput.scrollHeight;

        // Show the output toggle button if we have output and it's hidden
        if (this.liveOutput.textContent.trim() && this.liveOutput.style.display === 'none') {
            this.toggleOutputButton.style.display = 'block';
        }
    }

    toggleOutput() {
        const isVisible = this.liveOutput.style.display !== 'none';

        if (isVisible) {
            this.liveOutput.style.display = 'none';
            this.outputToggleIcon.textContent = '📋';
            this.toggleOutputButton.innerHTML = '<span id="output-toggle-icon">📋</span> Show Live Output';
        } else {
            this.liveOutput.style.display = 'block';
            this.outputToggleIcon.textContent = '▲';
            this.toggleOutputButton.innerHTML = '<span id="output-toggle-icon">▲</span> Hide Live Output';
        }

        // Update reference to the new icon element
        this.outputToggleIcon = document.getElementById('output-toggle-icon');
    }

    updateStatus(type, icon, text) {
        this.testStatus.className = `status-${type}`;
        this.testStatus.innerHTML = `<span class="status-icon">${icon}</span><span class="status-text">${text}</span>`;
    }

    updateButtonStates() {
        this.startButton.disabled = this.isRunning;
        this.stopButton.disabled = !this.isRunning;
    }

    showProgress() {
        this.progressContainer.style.display = 'block';
        this.progressFill.style.width = '0%';
        this.progressText.textContent = 'Preparing test...';
    }

    hideProgress() {
        setTimeout(() => {
            this.progressContainer.style.display = 'none';
        }, 1000);
    }

    resetResults() {
        this.liveOutput.textContent = '';
        this.liveOutput.style.display = 'none';
        this.toggleOutputButton.style.display = 'none';
        this.resultsSummary.style.display = 'none';
        this.resultsActions.style.display = 'none';
        this.currentResults = null;
    }

    resetInterface() {
        this.resetResults();
        this.updateStatus('idle', '⏱️', 'Ready to test');
        this.hideProgress();
    }

    toggleAdvanced() {
        const isVisible = this.advancedOptions.style.display !== 'none';

        if (isVisible) {
            this.advancedOptions.style.display = 'none';
            this.toggleIcon.textContent = '⚙️';
            this.toggleAdvancedButton.innerHTML = '<span id="toggle-icon">⚙️</span> Advanced Options';
        } else {
            this.advancedOptions.style.display = 'block';
            this.toggleIcon.textContent = '▲';
            this.toggleAdvancedButton.innerHTML = '<span id="toggle-icon">▲</span> Hide Advanced Options';
        }

        // Update reference to the new icon element
        this.toggleIcon = document.getElementById('toggle-icon');
    }

    async exportResults() {
        if (!this.currentResults) {
            alert('No results to export');
            return;
        }

        try {
            const data = JSON.stringify(this.currentResults, null, 2);
            const result = await window.electronAPI.saveFile(data);

            if (result.success) {
                this.updateStatus('complete', '💾', `Results exported to ${result.path}`);
            } else if (!result.canceled) {
                alert(`Export failed: ${result.error}`);
            }
        } catch (error) {
            alert(`Export failed: ${error.message}`);
        }
    }
}

// Initialize the app when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new NetProbeApp();
});