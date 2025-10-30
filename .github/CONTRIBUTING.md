# Contributing to NetProbe

Thank you for your interest in contributing to NetProbe! This document provides guidelines for contributing to the project.

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/netprobe.git
   cd netprobe
   ```

2. **Set up Python environment**
   ```bash
   pipenv install --dev
   ```

3. **Set up Node.js environment**
   ```bash
   npm install
   node build-setup.js
   ```

4. **Run tests to verify setup**
   ```bash
   ./test.py
   ```

## Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow existing code style and conventions
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   ./test.py                    # Run test suite
   npm run electron-dev         # Test desktop app
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: describe your changes"
   ```

## Code Style Guidelines

### Python Code
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Add docstrings for public functions and classes
- Keep functions focused and small

### JavaScript Code
- Use modern ES6+ syntax
- Follow consistent naming conventions
- Add comments for complex logic
- Use async/await for asynchronous operations

## Testing

- **All tests must pass** before submitting a PR
- **Add tests** for new functionality
- **Mock network calls** in tests (tests should run in <1 second)
- **Test on multiple platforms** when possible

## Documentation

- Update README.md for user-facing changes
- Update CLAUDE.md for development changes
- Add inline comments for complex logic
- Include examples in documentation

## Pull Request Process

1. **Ensure tests pass** and code follows style guidelines
2. **Update documentation** as needed
3. **Create pull request** with:
   - Clear title and description
   - Link to related issues
   - Screenshots for UI changes
   - Test results on different platforms

4. **Address review feedback** promptly
5. **Squash commits** before merge if requested

## Release Process

Releases are automated through GitHub Actions:

1. **Create a tag** following semantic versioning:
   ```bash
   git tag -a v1.2.3 -m "Release version 1.2.3"
   git push origin v1.2.3
   ```

2. **GitHub Actions** will automatically:
   - Build for macOS and Windows
   - Run tests on multiple platforms
   - Create GitHub release with binaries

## Reporting Issues

When reporting issues, please include:

- **Clear description** of the problem
- **Steps to reproduce** the issue
- **Environment details** (OS, Python version, etc.)
- **Expected vs actual behavior**
- **Error messages or logs**

## Getting Help

- **Documentation**: Check README.md and CLAUDE.md first
- **Issues**: Search existing issues before creating new ones
- **Discussions**: Use GitHub Discussions for questions

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow GitHub's community guidelines

Thank you for contributing to NetProbe!