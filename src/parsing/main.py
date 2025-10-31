from src.parsing.parse_utmn import main as utmn_main
from src.parsing.parse_leaderid import main as leaderid_main
from src.parsing.parse_znanie import main as znanie_main


def main():
    print("=== ПАРСИНГ... ===")

    print("\n[1/3] UTMN Parser")
    utmn_main(click_limit=2, headless=True)

    print("\n[2/3] Leader-ID Parser")
    leaderid_main(headless=False)

    print("\n[3/3] Znanie Parser")
    znanie_main(headless=True)

    print("\n=== ПАРСИНГ ЗАВЕРШЁН УСПЕШНО ===")


if __name__ == "__main__":
    main()
