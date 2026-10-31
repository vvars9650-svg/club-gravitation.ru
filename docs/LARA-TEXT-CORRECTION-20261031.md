# Визитка Лары — текстовая корректировка, 31.10.2026

## Result

Актуальный кандидат на визуальную приёмку. По новой правке Влада логотип отменён:
на слайде 1 слева «Гравитация / Клуб живых встреч / и знакомств», справа
`+7 915 423-47-12` со ссылкой `tel:+79154234712`. Весь блок использует
Cormorant Garamond, как имя и должность. На mobile сохраняются две колонки.
Фото, имя и должность сохранены. На слайдах 2–5 убраны все конечные точки,
включая однословные фразы слайда 3; дизайн, ссылки и навигация сохранены.
Оригинальный SVG сохранён в истории/материалах, в текущей странице не используется.

## Where

- Worktree: `C:/Users/VLAD/Documents/ChatGPT/Сайт Гравитации/.worktrees/lara-visual-update2`.
- Ветка: `codex/lara-visual-update2-20261031`.
- GitHub: https://github.com/vvars9650-svg/club-gravitation.ru/tree/codex/lara-visual-update2-20261031
- Локальное превью: http://localhost:4176/
- Актуальные снимки: `prototypes/lara-card/exports/text-correction/`.
- Предыдущие снимки в `exports/visual-update2/` исторические, с логотипом и точками.
- Изменены index.html, style.css, prepare-test-release.mjs, verify-candidate.mjs,
  candidate-manifest.json, README; добавлены этот отчёт, 6 JPEG и checks.json.
- SHA-256 автономной страницы:
  `48ac02c5c18d456160d2a2c7c9625b133c1b68131a9dbc3517ea167ba0fb9a29` (1799701 байт).

## Verified

- `verify-candidate.mjs`: источники, контрольные суммы слайдов, tel, кнопки,
  точки навигации, клавиатура, моделируемые touch-события, две одинаковые сборки — PASS.
- Browser: все 5 слайдов при 1080×1080, 390×844, 360×800 — PASS.
- Конечные точки в текстах слайдов 2–5 отсутствуют; телефон корректен;
  computed font-family текстового блока — Cormorant Garamond.
- Horizontal/text overflow отсутствует; console warn/error пусто.
- `git diff --check` — PASS. DPR 1; HiDPI и физический touch не проверялись.

## Current blocker

Нет. Требуется визуальная приёмка кандидата, а не техническое исправление.

## Next task

Влад и Лара оценивают новый текстовый блок и отсутствие точек.
Публикация TEST/PROD требует отдельного поручения.

## Guardrails

accepted-manifest.json, QR, TEST/PROD, основной сайт, backend не изменены.
Чужие изменения основной рабочей копии и предыдущий worktree не затронуты.
