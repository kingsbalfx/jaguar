# 🧪 LOCAL TESTING GUIDE FOR KIDS (Grade 3 Level)

## What is "Testing"? 🤔

Testing is like **practicing before the real game**! ⚽

- **Soccer**: Practice in park → get good → play real game ✓
- **Code**: Test on computer → find problems → then share online ✓
- **Why?**: If you share broken code, people get angry! 😠

**Testing = Checking your work before sharing it!**

---

## What We Test

```
┌─────────────────────────────────────────┐
│     IS YOUR CODE WORKING RIGHT?         │
├─────────────────────────────────────────┤
│  ✓ Does the web app start?             │
│  ✓ Do buttons click?                    │
│  ✓ Does the bot turn on?                │
│  ✓ Can the bot trade?                   │
│  ✓ Do tests pass (green ✓)?             │
└─────────────────────────────────────────┘
```

---

## Before You Start Testing

### Install These Things (Do ONCE)

**1. Node.js** (for web app - Google "download nodejs")
```
Download from: nodejs.org
Click "Download" (green button)
Run installer (click Next, Next, Done)
Close and restart computer
```

**2. Python 3.11** (for trading bot - Google "download python")
```
Download from: python.org
Download version 3.11 (or newer)
Run installer
✅ CHECK: "Add Python to PATH" before clicking Install!
Finish
Close and restart computer
```

**3. Docker** (optional but helpful - Google "download docker desktop")
```
Download from: docker.com
Run installer
Click Next, Next, Done
Restart computer
```

---

## Test 1: Web App Health Check ✓

### "Is the website alive?"

Like checking if a light turns on when you flip the switch! 💡

**Step by Step:**

```bash
1. Open Command Prompt (or PowerShell)
   Windows: Press Windows key + R → type "cmd" → Enter

2. Go to project folder:
   cd C:\Users\YOUR_NAME\Downloads\kingsbal\kingsbal\ magix\ trading

3. Install web app dependencies (do ONCE):
   npm install

4. Start the web app:
   npm run dev

5. Watch for this message:
   "ready - started server on 0.0.0.0:3000"
   ✅ Success! Website is alive!

6. Open web browser:
   Go to: https://kingsbalfx.name.ng
   
7. You should see the home page!
   ✅ Web app working!

8. Stop it: Press Ctrl+C in the command prompt
```

**What did you test?**
- ✓ Web app starts without error
- ✓ Website shows on browser
- ✓ No broken imports or missing files

---

## Test 2: Bot Health Check ✓

### "Is the robot alive?"
3.
Like checking if a robot's lights turn on! 🤖

**Step by Step:**

```bash
1. Open NEW Command Prompt (keep web one running)
   Windows: Press Windows key + R → type "cmd" → Enter

2. Go to bot folder:
   cd C:\Users\YOUR_NAME\Downloads\kingsbal\kingsbal\ magix\ trading\ict_trading_bot

3. Install bot dependencies (do ONCE):
   pip install -r requirements.txt
   
   (This might take 2-3 minutes)
   Wait for: "Successfully installed ..."
   ✅ Done!

4. Check the .env file:
   - Make sure you copied .env.example to .env
   - Set MT5 credentials in the Admin panel (stored in Supabase)
   - Important: BOT_ENABLED=true
   
5. Start the bot:
   python main.py

6. Watch for this message in the window:
   "Bot started successfully"
   "Flask API running on https://your-bot-host:8000"
   ✅ Success! Bot is alive!

7. Stop it: Press Ctrl+C
```

**What did you test?**
- ✓ Bot starts without error
- ✓ Flask API starts (port 8000)
- ✓ No missing libraries or configuration

---

## Test 3: Check Health Endpoints 💓

### "Can we talk to the robot?"

Like calling the robot on the phone to ask "Are you there?" 📞

**You need TWO command prompts open:**

```
Window 1: Web app (npm run dev - running)
Window 2: Bot (python main.py - running)
Window 3: NEW - for testing
```

**Step by Step:**

```bash
1. Open NEW Command Prompt (Window 3)

2. Check BOT is alive:
   curl https://your-bot-host:8000/health
   
   You should see:
   {"status":"healthy","uptime":"1 minute"}
   ✅ Bot is responding!

3. Check WEB is alive:
   curl https://kingsbalfx.name.ng/api/health
   
   You should see:
   {"status":"ok","timestamp":"..."}
   ✅ Web is responding!

4. Get BOT status:
   curl https://your-bot-host:8000/status
   
   You should see:
   {"trades_today":0,"errors":0,"last_trade":"N/A"}
   ✅ Bot is working!
```

**What did you test?**
- ✓ Bot API responds to requests
- ✓ Web API responds to requests
- ✓ Communication working between them

---

## Test 4: Run Automated Tests ✅

### "Let the computer test itself!"

Like having a robot check another robot! 🤖 checking 🤖

**For Web App:**

```bash
1. Go to root folder:
   cd C:\Users\YOUR_NAME\Downloads\kingsbal\kingsbal\ magix\ trading

2. Run web tests:
   npm test

3. You'll see output like:
   PASS __tests__/api.test.js
   ✓ Validation tests (5)
   ✓ Error handling tests (3)
   ✓ API tests (4)
   
   Test Suites: 1 passed, 1 total
   Tests: 12 passed, 12 total
   ✅ All tests pass!

4. If you see RED X's:
   ❌ Tests failed
   Read the error message
   Fix the code
   Run tests again
```

**For Bot App:**

```bash
1. Go to bot folder:
   cd ict_trading_bot

2. Run bot tests:
   pytest tests/test_config.py -v

3. You'll see output like:
   test_valid_symbols PASSED ✓
   test_valid_risk PASSED ✓
   test_valid_hours PASSED ✓
   test_config_file_exists PASSED ✓
   
   4 passed in 0.23s
   ✅ All tests pass!

4. If you see RED X's:
   ❌ Tests failed
   Read error message
   Fix code
   Run again
```

**What did you test?**
- ✓ Validation works (checks inputs)
- ✓ Error handling works (catches problems)
- ✓ Configuration is correct
- ✓ All test cases pass

---

## Test 5: Try a Real Action 🎮

### "Can the website do things?"

**Test: Try to Log In**

```
1. Open browser: https://kingsbalfx.name.ng
2. Click "Login" button
3. See login form? ✅
4. Try email + password
5. Should show message or error
   ✅ Login working (or shows expected error)!
```

**Test: Try Bot Control API**

```bash
1. Open Command Prompt

2. Tell bot to start:
   curl -X POST https://your-bot-host:8000/control/start
   
   Should see:
   {"status":"bot_started"}
   ✅ Control API works!

3. Tell bot to stop:
   curl -X POST https://your-bot-host:8000/control/stop
   
   Should see:
   {"status":"bot_stopped"}
   ✅ Stop works!
```

**What did you test?**
- ✓ Web pages load and display
- ✓ Forms work
- ✓ Bot responds to commands
- ✓ Control API functions

---

## The Test Checklist ✅

### Before Pushing to GitHub, Check ALL These:

```
WEB APP TESTS:
□ npm install works (no errors)
□ npm run dev starts without error
□ Website shows at https://kingsbalfx.name.ng
□ npm test passes (12 tests green)
□ Can click buttons and navigate

BOT TESTS:
□ pip install -r requirements.txt works
□ python main.py starts without error
□ Bot says "started successfully"
□ curl https://your-bot-host:8000/health returns OK
□ pytest tests/test_config.py passes (4 tests green)

INTEGRATION TESTS:
□ curl https://your-bot-host:8000/health works
□ curl https://kingsbalfx.name.ng/api/health works
□ Both apps running together (no conflicts)

DOCKER (Optional):
□ docker-compose build works
□ docker-compose up starts both apps
□ Both containers healthy

IF ALL BOXES ✅:
→ Don't see any RED ❌
→ Don't see any ERROR messages
→ All tests PASS ✓
→ READY TO PUSH TO GITHUB! 🚀
```

---

## Understanding Test Results 📊

### GREEN ✅ = GOOD!

```
PASS  __tests__/api.test.js
✓ Email validation works
✓ Error handling catches problems

Test Suites: 1 passed
Tests: 12 passed, 12 total

Status: ✅ READY TO PUSH!
```

**What it means:** Everything works! Push to GitHub! 🎉

### RED ❌ = BROKEN!

```
FAIL  __tests__/api.test.js
✗ Email validation fails
  Expected false, got true
  
Tests: 11 passed, 1 failed

Status: ❌ DON'T PUSH YET!
```

**What to do:**
1. Read the error message
2. Find the broken code
3. Fix it
4. Run tests again
5. Keep going until all GREEN ✅

---

## Detailed Process: Step by Step

### The COMPLETE Test Flow

```
START
  ↓
1. npm install (web dependencies)
  ↓
2. pip install -r requirements.txt (bot dependencies)
  ↓
3. npm run dev (start web in terminal 1)
  ↓
4. python main.py (start bot in terminal 2)
  ↓
5. Test web at https://kingsbalfx.name.ng (browser)
  ↓
6. Test bot with curl (terminal 3)
  ↓
7. npm test (run web tests)
  ↓
8. pytest (run bot tests)
  ↓
9. Check all results:
   - All tests GREEN ✅?
   - No errors?
   - No broken buttons?
  ↓
YES? → READY TO PUSH! 🚀
NO?  → Find & fix problems → Start at Step 7 again
```

---

## Common Problems & Fixes 🚨

### Problem: "npm install fails"
```
Error: npm not installed

✅ Fix:
1. Download NodeJS from nodejs.org
2. Install it
3. Restart computer
4. Try again
```

### Problem: "pip install fails"
```
Error: pip not found

✅ Fix:
1. Download Python 3.11 from python.org
2. During install, CHECK "Add Python to PATH"
3. Restart computer
4. Try again
```

### Problem: "Port 3000 already in use"
```
Error: Address already in use

Someone else is using port 3000!

✅ Fix:
1. Find other program using port 3000:
   netstat -ano | findstr :3000

2. Stop it or use different port:
   npm run dev -- -p 3001
   (web on 3001 instead)
```

### Problem: "Bot won't start - no .env file"
```
Error: No such file .env

✅ Fix:
1. Find .env.example
2. Copy it
3. Rename copy to .env
4. Set MT5 credentials in the Admin panel
5. Try again
```

### Problem: "Tests fail randomly"
```
Tests pass sometimes, fail sometimes

✅ Fix:
1. Kill all Node/Python processes:
   Ctrl+C in all terminals

2. Wait 10 seconds

3. Run just one test:
   npm test -- --testNamePattern="Email"
   
4. See what breaks
5. Fix it
6. Run all tests again
```

### Problem: "Health check returns error"
```
curl: error

✅ Fix:
1. Check bot is actually running:
   command prompt shows "started successfully"?

2. Wait 5 seconds after starting:
   Bot takes time to boot

3. Check port number:
   Bot on 8000?
   Web on 3000?
   
4. Check nothing blocking ports:
   Close other programs

5. Try this instead:
   curl -v https://your-bot-host:8000/health
   (shows more details)
```

---

## Quick Reference Card 📋

### Start Everything

**Terminal 1:**
```bash
cd kingsbal
npm install
npm run dev
```

**Terminal 2:**
```bash
cd ict_trading_bot
pip install -r requirements.txt
python main.py
```

**Terminal 3:**
```bash
# Check everything works
curl https://kingsbalfx.name.ng/api/health
curl https://your-bot-host:8000/health

# Run tests
npm test
pytest tests/test_config.py -v
```

### Stop Everything
```
All terminals: Press Ctrl+C
```

---

## Next Steps 🚀

✅ **After tests pass:**

1. Read: `GITHUB_GUIDE_SIMPLE.md`
2. Follow: GitHub push steps
3. Go online: See your code on GitHub!

✅ **Then deploy:**

1. Read: `DEPLOYMENT_CHECKLIST.md`
2. Deploy to production (Vercel, AWS, etc.)

---

## Remember! 💡

**Testing = Time SAVED!**

- Test locally = Catch problems early
- Catch early = Fix is easy
- Fix early = Code is good
- Good code = Happy users!

**Don't skip testing!**

---

## Questions? 🤔

1. Ask your teacher
2. Read error messages carefully
3. Search Google: "how to run pytest"
4. Try once more, slowly

**You got this!** 💪

---

**NEXT**: Read GITHUB_GUIDE_SIMPLE.md to push your code! 👈


