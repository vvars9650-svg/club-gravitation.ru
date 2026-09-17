PARTICIPANT_STATUSES = ("Кандидат", "Одобрен", "Не одобрен", "Неактивен")
PROCESSING_STATES = ("Разрешена", "Заблокирована")

# CRM V2 values belong to one immutable club Application. Participant status is
# intentionally kept separate because event participation and club membership
# are different domains.
APPLICATION_STATUSES = (
    "Новая заявка",
    "На рассмотрении",
    "Нужен контакт",
    "Интервью назначено",
    "Интервью пройдено",
    "Одобрен",
    "Ожидаем ответ",
    "Пауза",
    "Активный участник",
    "Не подходит",
)
APPLICATION_DECISIONS = APPLICATION_STATUSES[1:]
APPLICATION_OWNERS = ("Влад", "Лара")
APPLICATION_PRIORITIES = ("Высокий", "Средний", "Низкий")
APPLICATION_NEXT_ACTIONS = (
    "Рассмотреть",
    "Связаться",
    "Назначить интервью",
    "Провести интервью",
    "Обсудить",
    "Пригласить",
    "Дождаться ответа",
    "Добавить в участники",
    "Связаться позже",
)

INITIAL_PARTICIPANT_STATUS = PARTICIPANT_STATUSES[0]
INITIAL_APPLICATION_STATUS = APPLICATION_STATUSES[0]
