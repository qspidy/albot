from bot.bot import IRCBot

if __name__ == "__main__":
    bot = IRCBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("Bot terminated.")
