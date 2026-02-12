# Run Ralph (macOS) — Contribution‑Ready, AI‑Friendly Guide

این سند یک راهنمای استاندارد و یکپارچه برای **راه‌اندازی و اجرای Ralph روی macOS** است. هدف این است که اگر این فایل به یک هوش مصنوعی دیگر داده شود، بتواند **بدون ابهام** Ralph را دقیقاً همان‌طور اجرا کند.

> دامنه: این سند مخصوص macOS است (MacBook Air/Pro). اگر روی Linux/Windows هستید، از راهنمای عمومی پروژه استفاده کنید.

---

## فهرست
- هدف
- پیش‌نیازها
- ساختار مسیرها
- راه‌اندازی Dev Container
- تنظیمات Mac (SSH mount + Sleep)
- آماده‌سازی پروژه داخل workspace
- آماده‌سازی Ralph و تسک‌ها
- نصب و احراز هویت Copilot CLI (قطعی)
- اجرای Ralph Loop
- مانیتورینگ پیشرفت
- عیب‌یابی سریع
- چک‌لیست نهایی

---

## هدف
- اجرای Ralph به صورت batch روی تسک‌های پروژه در Dev Container
- اطمینان از اجرای پایدار در macOS
- قابلیت تکرار کامل توسط یک AI دیگر

---

## پیش‌نیازها
- Git
- Docker Desktop (فعال)
- VS Code + Dev Containers
- اکانت GitHub با دسترسی Copilot

---

## ساختار مسیرها (استاندارد)
- ریشه Ralph: `/workspace`
- پروژه داخل کانتینر: `/workspace/projects/<PROJECT_DIR>`

در میزبان macOS:
- Ralph repo: `/Users/<USER>/projects/ralph-latest`
- پروژه روی میزبان: `/Users/<USER>/projects/<YOUR_PROJECT>`

---

## راه‌اندازی Dev Container (macOS)

### 1) کلون Ralph
```bash
git clone https://github.com/sepehrbayat/copilot-ralph-mode.git /Users/<USER>/projects/ralph-latest
```

### 2) کپی پروژه داخل ساختار Ralph
```bash
mkdir -p "/Users/<USER>/projects/ralph-latest/projects/<PROJECT_DIR>"
cp -R "/Users/<USER>/projects/<YOUR_PROJECT>/.\" \"/Users/<USER>/projects/ralph-latest/projects/<PROJECT_DIR>/"
```

### 3) تنظیم devcontainer.json
فایل:
- `.devcontainer/devcontainer.json`

تنظیمات کلیدی:
- `workspaceFolder` = `/workspace/projects/<PROJECT_DIR>`
- `postCreateCommand` و `postStartCommand` طوری اجرا شوند که اسکریپت‌ها از `/workspace/.devcontainer/...` اجرا شوند.

### 4) فیکس خطای mount SSH (macOS)
فایل:
- `.devcontainer/docker-compose.yml`

اگر `${USERPROFILE}` وجود دارد، آن را با `${HOME}` جایگزین کنید:
```yaml
${HOME}/.ssh:/home/vscode/.ssh:ro
```

### 5) مشکل reuse کانتینر قدیمی
اگر VS Code کانتینر قبلی را reuse می‌کند، کانتینر را حذف کنید و مجدداً Dev Container را بسازید تا mount اصلاح شود.

### 6) فیکس post-create (requirements-dev.txt)
فایل:
- `.devcontainer/post-create.sh`

در ابتدای اسکریپت اضافه کنید:
```bash
cd /workspace
```

### 7) راستی‌آزمایی در کانتینر
```bash
pip install -r requirements-dev.txt
pip install -e .
pytest
```

---

## تنظیمات Mac برای جلوگیری از توقف
برای جلوگیری از توقف اجرای Ralph در طول شب:

```bash
# غیرفعال کردن اسکرین‌سیور
defaults -currentHost write com.apple.screensaver idleTime -int 0
killall cfprefsd

# بیدار نگه‌داشتن سیستم برای 8 ساعت
caffeinate -t 28800
```

---

## آماده‌سازی پروژه داخل کانتینر
در کانتینر باید مسیر پروژه این باشد:
```text
/workspace/projects/<PROJECT_DIR>
```

---

## آماده‌سازی Ralph و تسک‌ها

### 1) ساخت تسک‌ها
- همه تسک‌ها در: `tasks/*.md`
- گروه: `tasks/_groups/<PROJECT_GROUP>.json`
- لیست تسک‌ها: `tasks/tasks.json`

### 2) تنظیم مدل پیش‌فرض
در نسخه جدید:
- `production/tools/copilot-ralph-mode/ralph_mode/constants.py`

مقدار:
```python
DEFAULT_MODEL = "claude-sonnet-4.5"
```

### 3) فعال کردن Agent Table (اگر پشتیبانی می‌شود)
```bash
python -m ralph_mode table init "<PROJECT_GROUP_TITLE>"
python -m ralph_mode table status
```

### 4) Batch Init
```bash
python -m ralph_mode batch-init \
  --tasks-file tasks/tasks.json \
  --max-iterations 5 \
  --completion-promise "TASK_DONE" \
  --model "claude-sonnet-4.5"
```

---

## نصب و احراز هویت Copilot CLI (مسیر قطعی)

### 1) نصب
```bash
npm install -g @github/copilot
```

### 2) Login با OAuth (Device Flow)
> Fine‑Grained PAT معمولاً کافی نیست. مسیر قطعی OAuth است.

```bash
copilot login
```
- برو به: `https://github.com/login/device`
- کد را وارد کن
- Authorize کن

اگر توکن ذخیره نشد:
```bash
mkdir -p ~/.copilot
copilot login --config-dir ~/.copilot
```

### 3) تست
```bash
copilot -p "Say hello"
```

---

## اجرای Ralph Loop

### 1) آماده‌سازی state
```bash
python -m ralph_mode disable
python -m ralph_mode run \
  --group <PROJECT_GROUP> \
  --model "claude-sonnet-4.5" \
  --max-iterations 5 \
  --completion-promise "TASK_DONE"
```

### 2) اجرای loop واقعی
> `run` فقط state را می‌نویسد؛ اجرای واقعی با loop است.

```bash
RALPH_SKIP_TASK_VALIDATION=1 \
RALPH_SKIP_PREFLIGHT=1 \
bash production/tools/copilot-ralph-mode/ralph-loop.sh run
```

---

## مانیتورینگ پیشرفت (اختیاری)
```bash
while true; do
  python - <<'PY'
from pathlib import Path
import json
hist=Path("/workspace/projects/<PROJECT_DIR>/.ralph-mode/history.jsonl")
state=json.loads(Path("/workspace/projects/<PROJECT_DIR>/.ralph-mode/state.json").read_text())
completed=0
for line in hist.read_text().splitlines():
    try:
        obj=json.loads(line)
    except Exception:
        continue
    if obj.get("status")=="task_completed":
        completed+=1

total=state.get("tasks_total") or 0
pct=(completed/total*100) if total else 0
print(f"Completed: {completed}/{total}  ({pct:.1f}%)")
print(f"Current: {state.get('current_task_id')} — {state.get('current_task_title')}")
print(f"Iteration: {state.get('iteration')}  Last: {state.get('last_iterate_at')}")
PY
  sleep 5
  clear
done
```

---

## عیب‌یابی سریع
- اگر loop متوقف شد، اول `copilot -p "ping"` را تست کن.
- در صورت auth نبودن Copilot، `copilot login` را دوباره انجام بده.
- زمانی که validation تسک‌ها رد شد، `RALPH_SKIP_TASK_VALIDATION=1` ضروری است.
- اگر performance کند شد، RAM Docker Desktop را حداقل 8GB بگذار.

---

## چک‌لیست نهایی
- [ ] Dev Container سالم و پروژه در `/workspace/projects/<PROJECT_DIR>`
- [ ] تسک‌ها و گروه آماده
- [ ] مدل پیش‌فرض تنظیم شده
- [ ] Copilot CLI نصب و auth شده
- [ ] `ralph_mode run` اجرا شده
- [ ] `ralph-loop.sh run` در حال اجرا

---

**End of file.**
