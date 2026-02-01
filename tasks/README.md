# 📋 Task Library

این پوشه شامل تسک‌های آماده برای استفاده با Ralph Mode است.

## ساختار فایل‌ها

```
tasks/
├── README.md              # این فایل
├── _groups/               # گروه‌بندی تسک‌ها
│   ├── rtl.json           # تسک‌های RTL
│   ├── testing.json       # تسک‌های تست
│   └── refactor.json      # تسک‌های ریفکتور
└── *.md                   # تسک‌های منفرد
```

## فرمت فایل تسک (.md)

```markdown
---
id: TASK-001
title: عنوان تسک
tags: [rtl, ui]
model: gpt-5.2-codex
max_iterations: 20
completion_promise: DONE
---

توضیحات کامل تسک...
```

## استفاده

```bash
# اجرای یک تسک با نام فایل
python3 ralph_mode.py run --task rtl-fixes.md

# اجرای یک تسک با ID
python3 ralph_mode.py run --task TASK-001

# اجرای گروهی از تسک‌ها
python3 ralph_mode.py run --group rtl

# لیست تسک‌ها
python3 ralph_mode.py tasks list

# جستجوی تسک
python3 ralph_mode.py tasks search "RTL"
```
