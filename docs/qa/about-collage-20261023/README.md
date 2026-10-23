# ABOUT collage: evidence 23.10.2026

Baseline: `4ca9034aaff5d7548910bb6c6ca5edd824194009`. Code: `fe41bfac28ec8af4ad60155376f6fbb3d4a6e27d`.

Скриншоты получены из свежего локального public-dist. Исходные PNG неизменны. Для экспорта коллажа целиком высота viewport увеличена до 1400 px, ширина сохранена, изображения снимков — в CSS pixels; fixed header скрыт только при съёмке области коллажа. Responsive assertions выполнены отдельно при стандартных высотах, см. [results.json](results.json).

Google Fonts блокируется сетью Cloud: используется fallback font. Приложение не выбрасывает JS errors; сетевые ограничения отражены в results. Ни TEST, ни PROD не опубликованы и не проверены live.

| Ширина | До | После |
|---|---|---|
| 360 | [PNG](before-360.png) | [PNG](after-360.png) |
| 390 | [PNG](before-390.png) | [PNG](after-390.png) |
| 768 | — | [PNG](after-768.png) |
| 1440 | [PNG](before-1440.png) | [PNG](after-1440.png) |
| 1920 | — | [PNG](after-1920.png) |

Проверки геометрии/масштаба, соседней разметки и десяти public routes можно повторить: собрать public-dist, запустить канонический serve на 4176 и выполнить `node docs/qa/about-collage-20261023/verify.cjs`. Требуются Playwright и `/usr/bin/chromium`; результат пишется в ignored `test-results/about-collage/qa-results.json`. Это диагностический локальный smoke без отправки заявок или загрузки фото.

Полные исходные скриншоты страниц также сохранены в Cloud `test-results/about-collage/`, но не включены в Git из-за размера. Для продолжения использовать [TEST HANDOFF](../../ABOUT-COLLAGE-TEST-HANDOFF-20261023.md).
