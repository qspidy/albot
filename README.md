# Albot

🤖 A Simple IRC BOT Written in Python. 🤖

![](assets/albot_demo.gif)

Visit [My Blog](https://orange.wastaken.xyz/2024/11/22/Implementing-An-Simple-IRC-Bot-Using-Python/) to learn about Albot more.

## Capabilities

* **Act as AI**: Utilize `ollama` in backend for AI-driven responses.

* **Custom Commands**: Execute custom scripts on host for advanced functionality.

* **Concurrent Conversations**: Enable simultaneous conversations by setting `THREAD_COUNT_IN_POOL` in `bot/bot.py`.

* **High Performance**: Achieve fast response times with minimal latency.

* **Dependency-Free**: Leverage only built-in Python 3 packages to minimize dependencies.

* **Minimal Complexity**: Implement the simplest, most efficient IRC bot possible.

## Quickstart

* **Prerequisites**: Install `python3` on your OS and `ollama`(optional) for Albot functionality.

* **Clone Repo**: Fetch the repository:

```bash
git clone https://github.com/qspidy/albot.git

cd albot
```

* **Generate Config**: Edit `config.json` and customize settings as needed:

```bash
cp config.json.example config.json

vim config.json
```

* **Run Bot**: Execute Albot:

```bash
python3 main.py
```

## License

[MIT](https://github.com/qspidy/albot/raw/master/LICENSE)

---

Part of [MrOrange](https://orange.wastaken.xyz).

<a href="https://orange.wastaken.xyz/"><img alt="MrOrange" src="https://orange.wastaken.xyz/img/avatar.png" width="200"></a>

MrOrange热爱开源 • MrOrange loves open source

