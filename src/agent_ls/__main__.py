from dotenv import load_dotenv

load_dotenv()

from agent_ls.cli import app

if __name__ == "__main__":
    app()
