---
name: Windows Compatibility Issue
about: Report Windows-specific setup or compatibility problems
title: '[WINDOWS] Brief description of the issue'
labels: 'windows, compatibility, bug'
assignees: ''
---

## System Information
**Windows Version:** (e.g., Windows 11 Build 22000)
**Python Version:** (run `python --version`)
**Installation Method:** (e.g., Downloaded ZIP, Git clone)

## Issue Description
A clear and concise description of what the problem is.

## Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected Behavior
A clear and concise description of what you expected to happen.

## Actual Behavior
What actually happened instead.

## Error Messages
```
Paste the complete error message here, including any stack traces
```

## Compatibility Test Results
Please run the Windows compatibility test and paste the results:
```bash
python scripts/test_windows_compatibility.py
```

```
Paste the test output here
```

## Console Encoding
If you're experiencing Unicode/encoding errors, please check your console encoding:
```bash
python -c "import sys; print(f'Console encoding: {sys.stdout.encoding}')"
```

**Console Encoding:** (paste result here)

## Screenshots
If applicable, add screenshots to help explain your problem.

## Additional Context
Add any other context about the problem here, such as:
- Anti-virus software that might be interfering
- Whether you're using PowerShell, Command Prompt, or another terminal
- Any modifications you've made to the setup scripts
- Previous versions that worked (if any)

## Checklist
Before submitting, please confirm:
- [ ] I have read the [Windows Troubleshooting Guide](docs/WINDOWS_TROUBLESHOOTING.md)
- [ ] I have run the Windows compatibility test
- [ ] I have included complete error messages
- [ ] I have tested with the latest version from GitHub
- [ ] I have checked that this isn't a duplicate issue