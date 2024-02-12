# cashbot
Telegram Bot for GnuCash.

I didn't like anything that brings GnuCash into my mobile device, so made this.

## Requirements
- GnuCash app with database as backend (MySQL / PostgreSQL)
- Anything that can be a server (VPS/your PC/Raspberry PI/Dedicated...)
- Docker (~~or just clone sources and run main.py~~)

## Install with Docker
Create file with configuration (see below)
```bash
editor cashbot.env
```
Run the container from image
```bash
docker run --name cashbot --env-file cashbot.env -d brinza888/cashbot
```

## Configuration
Required configuration variables:
- BOT_TOKEN - Telegram Bot token; obtain it using [@BotFather](https://t.me/BotFather)
- DATABASE_URI - Database URI (anything that is supported by [piecash](https://piecash.readthedocs.io/en/master/tutorial/index_existing.html#opening-an-existing-book))

Optional configuration variables:
- USER_ID - Bot user ID; obtain it using [@my_id_bot](https://t.me/my_id_bot) (you SHOULD set this to secure your financial data and prevent others to interact with bot!)
- READONLY - prevent any modification in GnuCash database (default to False)
- PER_PAGE - transactions count per one journal message in bot (default to 3)
- LANG_CODE - language code
  - 'en' for English language (default),
  - 'ru' for Russian language.
- LANG_FILE - file with i18n configuration. Use it with Docker bind mount to load custom language.

## Found bug or need help?
Feel free to open new issue in Issues section.

For bug reports:
- Describe everything, that can be useful for bug reproduction.

For questions:
- Describe everything, that can be useful to understanding your question.
