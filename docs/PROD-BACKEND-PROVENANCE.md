# Источник PROD backend и независимый rollback

Подтверждённое действующее соответствие: Function `d4e8kk0f5bqulombl18j`, version `d4ej2creip5g0iloi3vh`, tag `$latest`, description `V5 PROD protected Admin CRM route`, created 19.09.2026 00:41:01 UTC. Прочитано через Cloud CLI без изменения функции.

Сохранённая история Codex от 19.09 (chat `01a0b6e9-06b6-7100-a6f5-587490f0f8e2`) содержит command `build_deployment.py --output backend/v5/dist/v5-prod-admin.zip` и последующий `version create` для этой функции с совпадающим description. Рабочий source находился в `prod-intake-20260919/club-gravitation.ru`. Предшествующие metadata-token и submit-fix ZIP относятся к другим версиям и не приняты за активную сборку.

Исходный worktree удалён при архивировании, но найден его Git snapshot `b306cf4a4a94cc92395485d8986c445c070d2c42`, ref `refs/codex/snapshots/d43a2b31696a75d9bb91ec8ec05558a9597d4956`, parent `ba8fc4751247cae34943f7139df994121ae5d328`, backend tree `50f233166bd484034a9e20b8557774f48babe470`. Snapshot сохраняет production runtime_config, factory, packaged frozen consent, per-repository environment, handler health/response environment и исправление JOIN. Эти механизмы восстановлены в RC с сохранением принятой короткой формы и новых YDB/photo исправлений.

Граница доказательства: происхождение сборки и восстановленный source подтверждены историей деплоя и сохранённым Git snapshot. Исходный `v5-prod-admin.zip` и его deploy-time checksum не найдены; Cloud metadata исходный ZIP/hash не возвращает. Побайтовое равенство пересобранного ZIP фактически загруженному в сентябре не заявляется. Найденные `v5-prod-deployment-s3.zip` и `v5-prod-metadata-token.zip` имеют одинаковый SHA-256 `be20fff3c616af4246193baa4be6153f8538dd33f5afca9ccc2d280ed0a10507` и отличаются от итогового source — это не rollback active version.

## Кандидат

`python -m backend.v5.build_production --output backend/v5/dist/production-rc.zip` создаёт отдельную production-сборку из текущего Git source, с file hashes и manifest. Entry point отказывает, если `V5_ENVIRONMENT` не PROD. Runtime не использует TEST credentials как fallback. Старый контракт 2.2 сохраняется; сервер отклоняет FORM-2.3 до отдельного юридического activation commit. Frozen 2.3 и неутверждённые тексты в ZIP не включаются. Сборка не выполняет deployment.

После утверждения комплекта нужно отдельно подключить PPD/CONSENT/FORM-2.3 и canonical hash именно утверждённого текста; до этого нельзя открыть новую форму в PROD. TEST runtime совместим с существующими TEST YDB_* параметрами и продолжает использовать TEST-marked hash.

## Независимый rollback

Основной rollback backend — возврат `$latest` на сохранённую действующую версию, без пересборки и без зависимости от Selectel symlink:

```powershell
# Только после отдельного разрешения на production rollback
yc serverless function version set-tag --id d4ej2creip5g0iloi3vh --tag '$latest'
yc serverless function version get-by-tag --function-id d4e8kk0f5bqulombl18j --tag '$latest'
```

До deployment вновь проверить Gateway binding/tag и сохранить spec, действующую версию и ссылки на secrets/configuration. При отказе новой формы сначала закрыть её frontend, затем вернуть backend tag. Данные и счётчики не откатываются. Миграций этой задачи нет.

Архивный snapshot позволяет восстановить baseline source для аварийной пересборки, но эту операцию следует отдельно принять как восстановленную сборку, а не как первоначальный ZIP. Сохранённая cloud version остаётся предпочтительной точкой rollback.
