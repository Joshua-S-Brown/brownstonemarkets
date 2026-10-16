---
name: review-story
description: Review a backlog story implemented by GPT/Codex from its pasted 8-part report, fix confirmed findings, close it in docs/backlog.md and suggest a commit message. Use when the user pastes an implementation report or asks to review or close a story.
---

The procedure lives in `docs/prompts/story-review.md`, so GPT/Codex and Claude read the same text. Read that file and follow the steps inside its `text` block, with the story ID from the user's message (or the report) as `<STORY_ID>` and the pasted report as the implementation report. Don't commit.
