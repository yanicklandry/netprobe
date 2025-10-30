#!/usr/bin/env node
/**
 * Automated testing script for NetProbe Electron app
 * Runs tests in a loop to catch and debug issues
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

class NetProbeTestRunner {
    constructor() {
        this.testCount = 0;
        this.maxTests = 5; // Run 5 tests by default
        this.testDuration = 10; // Short 10-second tests
    }

    async runTest() {
        this.testCount++;
        console.log(`\n🧪 Running automated test ${this.testCount}/${this.maxTests}`);
        console.log('=' .repeat(50));

        return new Promise((resolve, reject) => {
            const testArgs = [
                '--duration', this.testDuration.toString(),
                '--json', `test-auto-${this.testCount}.json`,
                '--debug'
            ];

            console.log('🚀 Starting NetProbe with args:', testArgs.join(' '));

            const process = spawn('python', ['netprobe.py', ...testArgs], {
                stdio: ['pipe', 'pipe', 'pipe']
            });

            let stdout = '';
            let stderr = '';

            process.stdout.on('data', (data) => {
                stdout += data.toString();
                // Show real-time output
                process.stdout.write(data);
            });

            process.stderr.on('data', (data) => {
                stderr += data.toString();
                console.error('STDERR:', data.toString());
            });

            process.on('close', (code) => {
                console.log(`\n✅ Test ${this.testCount} completed with exit code: ${code}`);

                // Check if results file was created
                const resultsFile = path.join(__dirname, 'results', `test-auto-${this.testCount}.json`);
                if (fs.existsSync(resultsFile)) {
                    console.log(`📁 Results file created: ${resultsFile}`);
                    try {
                        const data = JSON.parse(fs.readFileSync(resultsFile, 'utf8'));
                        console.log('📊 Test results preview:', {
                            duration: data.test_duration,
                            latency: data.avg_latency,
                            packet_loss: data.packet_loss,
                            quality_score: data.quality_score
                        });
                    } catch (error) {
                        console.error('❌ Failed to parse results file:', error.message);
                    }
                } else {
                    console.log('⚠️ No results file created');
                }

                resolve({ code, stdout, stderr });
            });

            process.on('error', (error) => {
                console.error('❌ Process error:', error);
                reject(error);
            });

            // Set a timeout slightly longer than test duration
            setTimeout(() => {
                if (!process.killed) {
                    console.log('⏰ Test timeout, killing process...');
                    process.kill();
                    resolve({ code: -1, stdout, stderr, timeout: true });
                }
            }, (this.testDuration + 15) * 1000);
        });
    }

    async runAllTests() {
        console.log('🎯 Starting automated NetProbe testing');
        console.log(`📋 Will run ${this.maxTests} tests of ${this.testDuration}s each`);

        const results = [];

        for (let i = 0; i < this.maxTests; i++) {
            try {
                const result = await this.runTest();
                results.push(result);

                if (result.timeout) {
                    console.log('⚠️ Test timed out');
                } else if (result.code !== 0) {
                    console.log('⚠️ Test failed with non-zero exit code');
                }

                // Wait 2 seconds between tests
                if (i < this.maxTests - 1) {
                    console.log('⏸️ Waiting 2 seconds before next test...');
                    await new Promise(resolve => setTimeout(resolve, 2000));
                }

            } catch (error) {
                console.error(`❌ Test ${i + 1} failed:`, error);
                results.push({ error: error.message });
            }
        }

        this.generateReport(results);
    }

    generateReport(results) {
        console.log('\n' + '=' .repeat(60));
        console.log('📊 AUTOMATED TESTING REPORT');
        console.log('=' .repeat(60));

        const successful = results.filter(r => r.code === 0).length;
        const failed = results.filter(r => r.code !== 0 || r.error).length;
        const timeouts = results.filter(r => r.timeout).length;

        console.log(`✅ Successful tests: ${successful}/${this.maxTests}`);
        console.log(`❌ Failed tests: ${failed}/${this.maxTests}`);
        console.log(`⏰ Timed out tests: ${timeouts}/${this.maxTests}`);

        if (failed > 0) {
            console.log('\n🔍 Issues found:');
            results.forEach((result, index) => {
                if (result.code !== 0 || result.error) {
                    console.log(`- Test ${index + 1}: ${result.error || 'Exit code ' + result.code}`);
                }
            });
        }

        // Check results directory
        const resultsDir = path.join(__dirname, 'results');
        if (fs.existsSync(resultsDir)) {
            const files = fs.readdirSync(resultsDir).filter(f => f.startsWith('test-auto-'));
            console.log(`\n📁 Created ${files.length} result files in results/`);
            files.forEach(file => console.log(`   - ${file}`));
        }

        console.log('\n🎉 Automated testing complete!');
    }
}

// Parse command line arguments
const args = process.argv.slice(2);
const testCount = args.includes('--count') ? parseInt(args[args.indexOf('--count') + 1]) || 5 : 5;
const duration = args.includes('--duration') ? parseInt(args[args.indexOf('--duration') + 1]) || 10 : 10;

const runner = new NetProbeTestRunner();
runner.maxTests = testCount;
runner.testDuration = duration;

if (args.includes('--help')) {
    console.log(`
NetProbe Automated Testing Tool

Usage: node test-app.js [options]

Options:
  --count N      Number of tests to run (default: 5)
  --duration N   Duration of each test in seconds (default: 10)
  --help         Show this help message

Examples:
  node test-app.js                    # Run 5 tests of 10s each
  node test-app.js --count 3          # Run 3 tests of 10s each
  node test-app.js --duration 5       # Run 5 tests of 5s each
  node test-app.js --count 10 --duration 15  # Run 10 tests of 15s each
`);
    process.exit(0);
}

runner.runAllTests().catch(console.error);