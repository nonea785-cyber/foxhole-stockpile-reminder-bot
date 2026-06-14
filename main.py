import os
from foxhole_buddy.utils.env import load_env_file, required_env
from foxhole_buddy.core.store import StockpileStore
from foxhole_buddy.core.bot import StockpileBot

def main() -> None:
    load_env_file()
    token = required_env("DISCORD_TOKEN")
    data_file = os.getenv("DATA_FILE", "data/stockpiles.json")

    bot = StockpileBot(store=StockpileStore(data_file))
    bot.run(token)

if __name__ == "__main__":
    main()
