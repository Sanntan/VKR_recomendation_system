from src.parsing.parse_utmn import main as utmn_main
from src.parsing.parse_leaderid import main as leaderid_main


def main():
    print("=== ПАРСИНГ... ===")

    print("\n[1/2] UTMN Parser")
    utmn_main(click_limit=2, headless=True)

    print("\n[2/2] Leader-ID Parser")
    leaderid_main(headless=True)

    print("\n=== ПАРСИНГ ЗАВЕРШЁН УСПЕШНО ===")


if __name__ == "__main__":
    main()
