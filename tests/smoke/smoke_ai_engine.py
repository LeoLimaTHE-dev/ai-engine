from ai_engine import ask_ai


def main():
    response = ask_ai(
        provider="gemini",
        prompt=(
            "Faça uma legenda para o Instagram com o tema sessão nesse domingo "
            "do filme Inception, coloque a data para hoje as 16 hrs"
        ),
    )
    print(response)


if __name__ == "__main__":
    main()
