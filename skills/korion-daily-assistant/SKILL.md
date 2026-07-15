---
name: korion-daily-assistant
description: Activate this skill only when the user explicitly invokes it through slash mode, or when the user's message starts with the Chinese prefix "管家". For those explicitly triggered requests, use this skill to manage household nutrition, refrigerator inventory, body metrics, and travel planning, including meal recording or analysis, nutrition advice, food inventory tracking, refrigerator management, blood pressure and other physical indicators, hydration tracking, grocery planning, family meal coordination, trip planning, destination weather checks, attraction recommendations, transportation and lodging planning, local food suggestions, packing lists, and travel precautions.
version: 1.0.0
author: "Korion.Kang"
---

>Language / 语言: This skill supports both English and Chinese. Detect the user's language from their first message and respond in the same language throughout. Below are instructions in both languages — follow the one matching the user's language.

>Execution Root / 执行根目录: Run all Bash commands from the directory that contains this SKILL.md. All tools/... and prompts/... paths below are relative to the skill root.

>Critical rule / 关键规则: Do not prepend commands with guessed host-specific paths such as cd ~/.hermes/..., cd ~/.claude/..., cd ~/.openclaw/..., cd ~/.codex/..., or hard-coded /Users/.../dot-skill paths. The current working directory is already the correct skill root. Run python3 tools/... directly.


# Triggering conditions

Only activate this skill through one of the following two entry modes:

* Slash mode: the user explicitly invokes this skill through a slash-style command entry.
* Prefix mode: the user's message starts with the Chinese word `管家`, for example `管家，帮我记录一下今天晚饭。`

If neither condition is met, do not activate this skill, even if the message content appears related to nutrition, refrigerator management, body metrics, or travel planning.


**Do not use for:**

* General knowledge questions unrelated to household health or food management
* Software engineering tasks
* Creative writing


**Compatible Hosts:**

* Claude Code
* OpenClaw
* Hermes
* Codex

---

# How to Extract User ID(Open ID)

## From Platform Messages
When receiving messages from platforms like Feishu, the message contains metadata with user information:
- Look for the `open_id` in the message context
- Extract the value that starts with "ou_" (e.g., "ou_0823d5314de079be140fed13214ef820")
- This becomes your {open_id}

## From CLI
If you receive a message from the CLI, you can use 'cli_open_id' as your {open_id}.

---

# Main Flow

## Domain Routing
Carefully determine the user's intent based on domain.

### Nutrition And Diet
Use `prompts/nutrition_manager.md` when the request is about meals, diet, or nutrition, including:
* Recording meals
* Asking what to eat today or tomorrow
* Requesting nutrition analysis, reports, or review
* Requesting personalized diet suggestions
* Reviewing recent food intake

### Refrigerator Management
Use `prompts/fridge_manager.md` when the request is about refrigerator or food inventory management, including:
* Adding newly purchased ingredients into inventory
* Recording food consumption from inventory
* Checking what is in the refrigerator
* Check which foods in the refrigerator are about to expire
* Managing storage location, expiry, or grocery replenishment

### Body Metrics Management
Use `prompts/metrics_manager.md` when the request is about health metrics or body indicators, including:
* Recording blood pressure, blood glucose, weight, heart rate, or similar metrics
* Reviewing recent metric records
* Checking trends or reminding around metric management

### Travel Management
Use `prompts/travel_manager.md` when the request is about travel planning or destination research, including:
* Planning a trip or building an itinerary
* Checking destination weather or travel season conditions
* Requesting attraction or photo spot recommendations
* Planning transportation, cross-city travel, or lodging
* Requesting local food recommendations
* Generating packing lists or travel precautions

