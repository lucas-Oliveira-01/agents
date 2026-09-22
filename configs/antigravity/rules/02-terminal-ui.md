# Terminal UI

The primary interface is **Kitty terminal** with **Nerd Font** support and rich Markdown rendering.

## Principle

Formatting is subordinate to information. Use visual elements only when they improve readability, scanning, navigation, comparison, or diagnosis. Never use visual formatting merely because it is available.

## Nerd Font Icons

Use icons when they improve scanning. Do not force them into code blocks, commands, or plain text where they reduce clarity.

| Context | Icon |
| :--- | :---: |
| Directory / folder | `` |
| Markdown / document | `` |
| Success / done |  |
| Warning / caution |  |
| Error / failure |  |
| Information / note | `` |
| Git branch | `` |
| Git commit | `` |
| Terminal / command | `` |

## Markdown Structure

- Use headings to separate meaningful sections — not decorative ones.
- Use bullet lists for discrete, unordered items.
- Use numbered lists for sequential steps.
- Use tables for genuine comparisons or structured data.
- Use `blockquotes` (>) for important notes or contextual warnings.
- Avoid large prose blocks. Break them into lists or headed sections.
- Do not over-format simple, short answers.

## Project Tree

When showing directory structure, use tree notation with Nerd Font icons:

```text
 project/
├──  src/
│   ├──  main.rs
│   ├──  index.ts
│   └──  script.py
├──  README.md
└──  .gitignore
```
