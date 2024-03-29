# 🚶‍♂️ Step Counter

Есть чатик, члены которого считают шаги и ведут статистику.

Данный бот реализует автоматизацю этого процесса:

- Каждый день участники указывают количество пройденных шагов
- В конце месяца отмечается победитель

# 🗒 Дорожная карта

Ведётся в Trello: [Step Counter](https://trello.com/b/V2Gv4nIh/step-counter)

# 🏗 Архитектура

```mermaid
flowchart LR
  user((Actor))
  telegram[Telegram API]

  subgraph representation
    request
    response
  end

  subgraph events
    bus[(Events)]
  end

  subgraph logic
    handler
    recurrent
  end

  subgraph data
    database[(database)]
    images[(images)]
  end

  user <--> telegram

  telegram --> request
  response --> telegram

  request --> bus --> handler
  recurrent --> bus --> response

  handler -.-> data
  recurrent -.-> data
```
