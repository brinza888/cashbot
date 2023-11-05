# cashbot
Telegram Bot for GnuCash.

I didn't like anything that brings GnuCash into my mobile device, so made this.

## Requirements
- GnuCash app with database as backend (MySQL, PostgreSQL, ...)
- anything that can be a server (VPS/your PC/Raspberry PI/Dedicated...)
- python3
- pyhon3-venv

## Make it works
### Installation
```
$ git clone https://github.com/brinza888/cashbot.git
$ cd cashbot
```

### Preparations
Create virtual environment and install python requirements.
```
$ python3 -m venv venv
$ ./venv/bin/pip install -r requiremnts.txt
```

### Config
Config stored as .env file in KEY=VALUE format. See `Config variables` section
```
$ nano .env
```
#### Config variables
- **BOT_TOKEN** - Telegram Bot token; obtain it using [@BotFather](https://t.me/BotFather)
- USER_ID - Bot user ID; obtain it using [@my_id_bot](https://t.me/my_id_bot) (you SHOULD set this to secure your financial data and prevent others to interact with bot!)
- **DATABASE_URI** - Database URI (anything that is supported by [piecash](https://piecash.readthedocs.io/en/master/tutorial/index_existing.html#opening-an-existing-book))
- READONLY - prevent any modification in GnuCash database (default to False)
- PER_PAGE - transactions count per one journal message in bot (default to 3)

### Run the bot
The simpliest way is to just run `main.py` script. But this won't run the bot in foreground and it will shutdown after you exit terminal!
```
$ ./venv/bin/python main.py
```
Better variant is to run the bot using `nohup` utility. But this won't start automaticly after server reboot!
```
$ nohup ./venv/bin/python main.py &>cashbot.log &
```
The best variant is to create `systemd` service!

I don't have enough time to teach you using systemd, so try to find something useful on this topic [here](https://www.google.com/search?q=systemd+service+example).

## Found bug or need help?
Feel free to open new issue in Issues section.

Describe everything, that can be useful for bug reproduction.

Describe everything, that can be useful to understanding your question.
