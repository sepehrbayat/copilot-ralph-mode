# Contributing to Copilot Ralph Mode

Thank you for your interest in contributing! 🎉

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/YOUR_USERNAME/copilot-ralph-mode/issues)
2. If not, create a new issue with:
   - A clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, bash version, etc.)

### Suggesting Features

1. Open an issue with the `enhancement` label
2. Describe the feature and its use case
3. Explain how it fits with the Ralph philosophy

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `bash tests/test-ralph-mode.sh`
5. Commit with clear messages: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Code Style

- Use `shellcheck` for bash scripts
- Follow existing patterns in the codebase
- Add tests for new functionality
- Update documentation as needed
- Follow the task standard in [docs/EXECUTION_GUIDE.md](docs/EXECUTION_GUIDE.md) when adding or editing tasks

### Testing

Run the test suite before submitting:

```bash
bash tests/test-ralph-mode.sh
```

## Philosophy

Remember the core Ralph principles:

1. **Iteration > Perfection** - Small improvements are welcome
2. **Failures Are Data** - Bugs help us improve
3. **Persistence Wins** - Keep iterating on your PR if needed

## Questions?

Feel free to open an issue for any questions!
