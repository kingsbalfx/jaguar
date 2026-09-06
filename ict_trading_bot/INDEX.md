#!/usr/bin/env python3
"""
INDEX - ICT Trading Bot Documentation
This file helps you navigate all the documentation and tools.
"""

DOCUMENTATION_STRUCTURE = """
╔════════════════════════════════════════════════════════════════════════════╗
║                ICT TRADING BOT - DOCUMENTATION INDEX                       ║
║                    Fixed: Supabase Error Handling                          ║
║                    Date: September 6, 2026                                  ║
╚════════════════════════════════════════════════════════════════════════════╝
"""

# Quick navigation
QUICK_START = """
┌─ QUICK START (Choose Your Path)
├─ First Time User
│  1. python check_bot_health.py          ← Validate setup
│  2. python configure_credentials.py     ← (Optional) Configure Supabase
│  3. python main.py                      ← Start bot
│
├─ Experienced User
│  • python main.py                       ← Just start
│  • python quick_start.py                ← Safe start with validation
│
└─ Troubleshooting
   python check_bot_health.py              ← Diagnose issues
   Get-Content bot.log -Tail 50           ← View recent logs
   Read: QUICK_REFERENCE.md                ← Quick fixes
   Read: ERROR_TROUBLESHOOTING.md         ← Detailed solutions
"""

# Files by category
FILES_BY_CATEGORY = """
┌─ EXECUTABLE SCRIPTS
├─ configure_credentials.py
│  Purpose: Set up Supabase/MT5/Mirror trading credentials
│  Usage: python configure_credentials.py
│  Audience: All users, especially first-timers
│
├─ check_bot_health.py
│  Purpose: Validate bot configuration before running
│  Usage: python check_bot_health.py
│  Audience: Troubleshooting, DevOps, first-time setup
│
├─ quick_start.py
│  Purpose: Safe bot startup with automatic validation
│  Usage: python quick_start.py
│  Audience: All users who want safe startup
│
└─ main.py
   Purpose: The actual bot (existing file, now enhanced)
   Usage: python main.py
   Audience: Regular bot operation

┌─ DOCUMENTATION - GETTING STARTED
├─ QUICK_REFERENCE.md   (THIS FILE)
│  Purpose: Quick navigation and common tasks
│  Length: 2 pages
│  When to Read: Before anything else
│
├─ SETUP_CREDENTIALS_GUIDE.md
│  Purpose: Step-by-step setup instructions
│  Length: 5 pages
│  When to Read: First time setup
│
└─ QUICK_REFERENCE.md
   Purpose: Quick fixes and common tasks
   Length: 1 page
   When to Read: Quick answers

┌─ DOCUMENTATION - TROUBLESHOOTING
├─ ERROR_TROUBLESHOOTING.md
│  Purpose: Detailed error explanations and fixes
│  Length: 8+ pages
│  When to Read: Something isn't working
│  Covers: 7 common errors with step-by-step solutions
│
└─ bot.log
   Purpose: Bot execution logs
   When to Read: Debugging issues
   View: Get-Content bot.log -Tail 100

┌─ DOCUMENTATION - TECHNICAL
├─ IMPLEMENTATION_SUMMARY.md
│  Purpose: Technical details of all changes
│  Length: 10+ pages
│  Audience: Developers, DevOps, architects
│  Includes: Architecture, flows, code examples
│
├─ FILES_MODIFIED_AND_CREATED.md
│  Purpose: Detailed file-by-file changelog
│  Length: 8 pages
│  Audience: Developers doing code review
│  Includes: What changed, why it changed, impact analysis
│
└─ README.md (existing)
   Purpose: General bot documentation
   Audience: All users
   Includes: Features, requirements, usage
"""

# Decision tree
DECISION_TREE = """
                           START HERE
                               ↓
                    Have you used the bot before?
                         /          \\
                       YES           NO
                       ↓             ↓
            "Local-Only" or    Do you want
            "Cloud Mode"?      cloud features
                ↓              (Supabase)?
              Both!            /        \\
           Works now!        Yes       No
           See Quick           ↓        ↓
           Ref below.    Run:      Run:
           If issues,   python    python
           read Error   config_   main.py
           Trouble      cred.py
           shoot.                      ↓
                              Local-only
                              mode works
                              perfect! ✅

                    DECISION COMPLETE
                         ↓
                    Run: python
                    main.py
"""

# File locations
FILE_LOCATIONS = """
┌─ CONFIGURATION FILES
├─ .env                                    (In bot directory)
│  • Environment variables for bot config
│  • Optional if using credentials.json
│
├─ accounts.json                          (In bot directory)  
│  • For multi-account setup
│
└─ ~/.ict_trading_bot/credentials.json    (In home directory)
   • Local credential storage (secure)
   • Auto-created by configure_credentials.py

┌─ OUTPUT FILES
├─ bot.log                                 (In bot directory)
│  • Bot execution logs
│  • View: Get-Content bot.log -Tail 100
│
└─ ./data/mirror_signals.json             (In bot directory)
   • Local mirror trading coordination
   • Used if Supabase unavailable

┌─ DOCUMENTATION
├─ *.md files in bot directory
│  • All markdown files are documentation
│  • Read in order: Quick Ref → Setup → Specific Topic
"""

# Troubleshooting decision tree
TROUBLESHOOTING_TREE = """
                     Bot Not Starting?
                            ↓
                   Run check_bot_health.py
                            ↓
            ┌───────────────┬────────────────┐
            ↓               ↓                ↓
        8/10 PASS      4-7/10 PASS      <4/10 PASS
        But failing?   Fix issues       Install
            ↓          shown by tool    dependencies:
        Check error    ↓                pip install
        code in bot.log Read output     -r requirements
                       for what        .txt
        "error=X"      to fix          
                       ↓               Then:
                       Try again       python
                                      check_bot_
                                      health.py
        
        STILL FAILING?
                ↓
        Read: ERROR_TROUBLESHOOTING.md
        Find your error message
        Follow step-by-step fix
"""

# Color codes for terminal
COLOR_CODES = """
Files can be viewed with color:
✅ Green      = Success, all good
⚠️  Yellow    = Warning, continue but monitor
❌ Red       = Error, needs fixing
ℹ️  Blue     = Information
"""

# Code snippets for common tasks
COMMON_TASKS = """
TASK: Configure Supabase credentials
→ python configure_credentials.py
→ Select option 1
→ Enter URL and API key
→ Tool validates and saves

TASK: Check current configuration  
→ python configure_credentials.py
→ See summary at top

TASK: Run bot safely with validation
→ python quick_start.py
→ Checks everything first
→ Shows recovery options if fails

TASK: Deep diagnostic
→ python check_bot_health.py
→ Validates all systems
→ Reports status

TASK: View bot logs
→ Get-Content bot.log -Tail 100
→ Get-Content bot.log -Tail 50 -Wait

TASK: Search for errors
→ Select-String "ERROR\\|FAIL" bot.log

TASK: Enable debug logging
→ Edit .env: LOG_LEVEL=DEBUG
→ Restart bot

TASK: Reset everything
→ python configure_credentials.py
→ Select option 4: Reset credentials
→ Delete .env if needed
→ Run again and reconfigure
"""

# Feature comparison
FEATURE_MATRIX = """
FEATURE                 BEFORE           AFTER            TOOL
Configure creds         Edit .env        Interactive      configure_credentials.py
Validate setup          Manual           Automated        check_bot_health.py  
Clear errors            Minimal          Comprehensive    ERROR_TROUBLESHOOTING.md
Local storage           None             Encrypted JSON   credentials.json
Help guidance           None             Full docs        SETUP_CREDENTIALS_GUIDE.md
Safe startup            None             Validation       quick_start.py
Supabase optional       No (crashes)     Yes (local mode) (automatic)
Multi-account           Works            Enhanced         main.py (updated)
Mirror trading          Yes              Enhanced         (automatic fallback)
"""

# Support resources
SUPPORT_RESOURCES = """
ISSUE                           SOLUTION
────────────────────────────────────────────────────────────────
Supabase error                  · Read: ERROR_TROUBLESHOOTING.md #1
                                · Run: configure_credentials.py
                                · Or use local-only mode

MT5 connection error            · Read: ERROR_TROUBLESHOOTING.md #2
                                · Ensure MT5 is running
                                · Restart both MT5 and bot

Bot won't start                 · Run: check_bot_health.py
                                · Install: pip install -r requirements.txt
                                · Check: bot.log

Mirror trading issue            · Read: ERROR_TROUBLESHOOTING.md #7
                                · Run: configure_credentials.py (option 3)
                                · Verify: accounts.json setup

Any other error                 · Search: ERROR_TROUBLESHOOTING.md
                                · Enable: LOG_LEVEL=DEBUG in .env
                                · Review: bot.log with tail -f
"""

# Key files to read
KEY_READS = """
SITUATION                               FILES TO READ
──────────────────────────────────────────────────────────
I'm new to the bot                      1. QUICK_REFERENCE.md
                                        2. SETUP_CREDENTIALS_GUIDE.md
                                        3. README.md

Something isn't working                 1. QUICK_REFERENCE.md  
                                        2. ERROR_TROUBLESHOOTING.md
                                        3. bot.log

I want technical details                1. IMPLEMENTATION_SUMMARY.md
                                        2. FILES_MODIFIED_AND_CREATED.md
                                        3. Code in dashboard/bridge.py

I'm deploying to production             1. SETUP_CREDENTIALS_GUIDE.md
                                        2. IMPLEMENTATION_SUMMARY.md
                                        3. FILES_MODIFIED_AND_CREATED.md

I'm doing code review                   1. IMPLEMENTATION_SUMMARY.md
                                        2. FILES_MODIFIED_AND_CREATED.md
                                        3. Source code changes

I need help quickly                     1. QUICK_REFERENCE.md
                                        2. This file (INDEX)
                                        3. ERROR_TROUBLESHOOTING.md
"""

# Print everything
if __name__ == "__main__":
    print(DOCUMENTATION_STRUCTURE)
    print(QUICK_START)
    print("\n" + "="*80 + "\n")
    print(FILES_BY_CATEGORY)
    print("\n" + "="*80 + "\n")
    print(DECISION_TREE)
    print("\n" + "="*80 + "\n")
    print(FILE_LOCATIONS)
    print("\n" + "="*80 + "\n")
    print(TROUBLESHOOTING_TREE)
    print("\n" + "="*80 + "\n")
    print(COLOR_CODES)
    print("\n" + "="*80 + "\n")
    print(COMMON_TASKS)
    print("\n" + "="*80 + "\n")
    print(FEATURE_MATRIX)
    print("\n" + "="*80 + "\n")
    print(SUPPORT_RESOURCES)
    print("\n" + "="*80 + "\n")
    print(KEY_READS)
    print("\n" + "="*80 + "\n")
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                        DOCUMENTATION QUICK LINKS                           ║
╠════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  START HERE:                                                               ║
║  • QUICK_REFERENCE.md              - Quick answers and common tasks        ║
║  • SETUP_CREDENTIALS_GUIDE.md      - First-time setup                      ║
║                                                                            ║
║  IF SOMETHING IS WRONG:                                                    ║
║  • ERROR_TROUBLESHOOTING.md        - Find and fix your error              ║
║  • check_bot_health.py             - Run diagnostic (python)              ║
║                                                                            ║
║  FOR DEVELOPERS:                                                           ║
║  • IMPLEMENTATION_SUMMARY.md       - Technical overview                    ║
║  • FILES_MODIFIED_AND_CREATED.md   - What changed and why                 ║
║                                                                            ║
║  SCRIPTS TO RUN:                                                           ║
║  • python configure_credentials.py  - Set up credentials                  ║
║  • python check_bot_health.py       - Validate everything                 ║
║  • python quick_start.py            - Safe startup                        ║
║  • python main.py                   - Start the bot                       ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

Questions?
→ Check QUICK_REFERENCE.md first (super quick answers)  
→ Then ERROR_TROUBLESHOOTING.md (detailed error fixes)
→ Then documentation for your specific topic

Still stuck?
→ Run: python check_bot_health.py
→ View: tail bot.log
→ Enable: LOG_LEVEL=DEBUG in .env and check logs again

Documentation created: September 6, 2026
Last updated: September 6, 2026
Status: ✅ Ready for Production
""")
