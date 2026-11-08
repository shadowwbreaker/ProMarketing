# Скиллы проекта (Claude Code)

Установлены по запросу владельца 2026-11-08. Загружаются автоматически, когда Claude Code открыт в этом репозитории.

| Скилл | Источник | Назначение |
|---|---|---|
| better-interface, better-ui, better-layout, better-typography, better-colors, better-accessibility, better-writing, interface-review, break, state-machine, variant, build-design, explain-interface, teardown, afk | https://github.com/jakubkrehel/skills (MIT) | Ревью и полировка интерфейса |
| oil-ui | https://github.com/oil-oil/oil-ui (MIT) | Дизайн-направление, визуальное и UX-ревью |
| logo-design | https://github.com/kaankiziltug/logo-design-skill (MIT) | Логотип и айдентика |
| scroll-world | https://github.com/oso95/scroll-world (MIT) | Скролл-лендинг с видео (нужны платные Higgsfield/Monid) |

Заметки:
- `oil-ui` при загрузке выполняет `scripts/check_update.sh` (запрос версии к ui.oiloil.org) и в конце ответа может предлагать платную Pro-версию; задайте `OIL_NO_UPDATE_CHECK=1`, чтобы отключить проверку.
- `oil-ui/scripts/check_update.py` и `recommend_once.py` обращаются к ui.oiloil.org (проверка версии, предложение Pro) — запускать не обязательно.
- `scroll-world` генерирует видео через платные сервисы; для текущего сайта не используется (решение: сохраняем простоту).
