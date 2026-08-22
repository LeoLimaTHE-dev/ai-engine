from pathlib import Path

from ai_engine import (
    ConversationSession,
    PreflightReport,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    analyze_documents,
    build_summary_prompt,
    chat,
    delete_session,
    execute_structured_result,
    format_preflight,
    format_usage_summary,
    get_paths,
    get_usage_totals,
    list_sessions,
    load_documents,
    load_session_data,
    restore_conversation_session,
    save_session,
    summarize_session,
    usage_difference,
)

PATHS = get_paths()

DEFAULT_INPUT = PATHS.input_dir / "batch_teste"

DEFAULT_OUTPUT_DIR = PATHS.output_dir


def format_error_for_user(exc: Exception) -> str:
    if not isinstance(exc, ProviderError):
        return str(exc)

    provider = exc.provider.strip() or "desconhecido"
    lines = [f"Provider: {provider}"]

    if isinstance(exc, ProviderRateLimitError):
        lines.append(
            "A chamada foi recusada por limite de uso ou quota do provider."
        )

        retry_after = exc.retry_after_seconds
        if retry_after is not None and retry_after > 0:
            lines.append(
                "O provider informou que uma nova tentativa pode ser feita "
                f"em aproximadamente {retry_after:g} segundos."
            )

    elif isinstance(exc, ProviderTimeoutError):
        lines.append("A chamada excedeu o tempo configurado para o provider.")

    elif isinstance(exc, ProviderConnectionError):
        lines.append("Não foi possível comunicar com o provider.")

    elif isinstance(exc, ProviderRequestError):
        lines.append(
            "O provider recusou a requisição. "
            "Repetir sem alterar a solicitação pode não resolver."
        )

        if exc.status_code is not None:
            lines.append(f"Status HTTP: {exc.status_code}")

        if exc.error_code is not None:
            lines.append(f"Código do erro: {exc.error_code}")

    else:
        lines.append("A chamada ao provider falhou.")
        if exc.retryable:
            lines.append("A falha parece transitória.")
        else:
            lines.append("A falha não foi classificada como transitória.")

    return "\n".join(lines)


def confirm_preflight_interactively(
    report: PreflightReport,
) -> bool:
    print()
    print(format_preflight(report))

    print()

    if report.errors:
        print("=" * 60)
        print("ATENÇÃO: A REQUISIÇÃO ULTRAPASSA OS LIMITES CONFIGURADOS.")
        print("=" * 60)

        print()
        print(
            "Ela ainda pode ser executada, "
            "mas poderá consumir uma quantidade "
            "elevada de tokens ou recursos."
        )

        print()

        choice = input('Digite "CONFIRMAR" para continuar: ').strip()

        return choice == "CONFIRMAR"

    choice = input("Continuar com a chamada da API? [s/N]: ").strip().lower()

    return choice in (
        "s",
        "sim",
        "y",
        "yes",
    )


# ============================================================
# PROVIDERS
# ============================================================


def choose_provider() -> str:
    print()
    print("Escolha o provider:")
    print("1 - Gemini")
    print("2 - OpenAI")
    print("3 - Claude")

    choice = input("Provider [1]: ").strip().lower()

    if choice in (
        "",
        "1",
        "1 - gemini",
        "gemini",
    ):
        return "gemini"

    if choice in (
        "2",
        "2 - openai",
        "openai",
    ):
        return "openai"

    if choice in (
        "3",
        "3 - claude",
        "claude",
        "anthropic",
    ):
        return "claude"

    raise ValueError("Provider inválido.")


def choose_new_provider(
    current_provider: str,
) -> str | None:
    print()
    print(f"Provider atual: {current_provider}")

    print()
    print("Escolha o novo provider:")
    print("1 - Gemini")
    print("2 - OpenAI")
    print("3 - Claude")
    print("0 - Cancelar")

    choice = input("Novo provider: ").strip().lower()

    if choice.startswith("1") or choice == "gemini":
        return "gemini"

    if choice.startswith("2") or choice == "openai":
        return "openai"

    if choice.startswith("3") or choice == "claude" or choice == "anthropic":
        return "claude"

    if choice.startswith("0") or choice == "cancelar":
        return None

    print()
    print("Opção inválida.")

    return None


def change_session_provider(
    session: ConversationSession,
) -> bool:
    old_provider = session.provider

    new_provider = choose_new_provider(
        current_provider=old_provider,
    )

    if new_provider is None:
        print()
        print("Troca de provider cancelada.")

        return False

    if new_provider == old_provider:
        print()
        print("Esse provider já está em uso.")

        return False

    print()

    keep_choice = input("Manter histórico da conversa? [S/n]: ").strip().lower()

    keep_history = keep_choice not in (
        "n",
        "nao",
        "não",
        "no",
    )

    session.change_provider(
        provider=new_provider,
        keep_history=keep_history,
    )

    print()
    print(f"Provider alterado: {old_provider} → {session.provider}")

    if keep_history:
        print("Histórico da conversa preservado.")
    else:
        print("Histórico da conversa apagado.")

    print("Os documentos continuam carregados.")

    return True


# ============================================================
# INPUT
# ============================================================


def choose_input() -> Path:
    print()

    print(f"Entrada padrão: {DEFAULT_INPUT}")

    value = input("Arquivo ou pasta [Enter = usar padrão]: ").strip()

    if not value:
        return DEFAULT_INPUT

    return Path(value.strip('"'))


def recover_missing_input(
    old_path: str | Path,
) -> Path:
    print()
    print("=" * 60)
    print("CAMINHO DA SESSÃO NÃO ENCONTRADO")
    print("=" * 60)

    print()
    print(f"Caminho original:")

    print(old_path)

    print()
    print("Informe a nova localização dos arquivos desta sessão.")

    while True:
        value = input("Novo arquivo ou pasta: ").strip()

        path = Path(value.strip('"'))

        if path.exists():
            return path

        print()
        print("Caminho não encontrado. Tente novamente.")


# ============================================================
# USAGE
# ============================================================


def print_operation_usage(
    before: dict[str, int],
    after: dict[str, int],
) -> None:
    usage = usage_difference(
        before=before,
        after=after,
    )

    print()
    print(format_usage_summary(usage))


# ============================================================
# SESSION CREATION / RESTORE
# ============================================================


def create_new_session():
    print()
    print("=" * 60)
    print("NOVA SESSÃO")
    print("=" * 60)

    print()

    while True:
        session_name = input("Nome da sessão: ").strip()

        if session_name:
            break

        print("O nome da sessão não pode ficar vazio.")

    provider = choose_provider()

    input_path = choose_input()

    print()
    print("Carregando documentos...")

    documents = load_documents(input_path)

    print(f"Documentos carregados: {len(documents)}")

    session = ConversationSession(
        provider=provider,
        documents=documents,
    )

    saved_path = save_session(
        name=session_name,
        session=session,
        input_path=input_path,
    )

    print()
    print(f"Sessão criada:")

    print(saved_path)

    return (
        session_name,
        session,
        input_path,
    )


def select_existing_session_name() -> str | None:
    sessions = list_sessions()

    if not sessions:
        print()
        print("Nenhuma sessão salva.")

        return None

    print()
    print("Sessões disponíveis:")

    for index, name in enumerate(
        sessions,
        start=1,
    ):
        print(f"{index} - {name}")

    print("0 - Cancelar")

    print()

    choice = input("Escolha a sessão: ").strip()

    if choice == "0":
        return None

    if choice.isdigit():
        index = int(choice)

        if 1 <= index <= len(sessions):
            return sessions[index - 1]

    if choice in sessions:
        return choice

    print()
    print("Sessão inválida.")

    return None


def restore_saved_session():
    session_name = select_existing_session_name()

    if session_name is None:
        return None

    print()
    print("Restaurando sessão...")

    data = load_session_data(session_name)

    input_path = Path(data["input_path"])

    if not input_path.exists():
        input_path = recover_missing_input(input_path)

    print("Recarregando documentos...")

    documents = load_documents(input_path)

    session = restore_conversation_session(
        data=data,
        documents=documents,
    )

    # Update saved path in case it had moved.
    save_session(
        name=session_name,
        session=session,
        input_path=input_path,
    )

    print()
    print("Sessão carregada.")

    print()
    print(f"Provider: {session.provider}")

    print(f"Documentos: {len(session.documents)}")

    print(f"Mensagens recentes: {session.message_count}")

    print("Memória resumida: " + ("Sim" if session.summary else "Não"))

    return (
        session_name,
        session,
        input_path,
    )


# ============================================================
# SESSION MANAGEMENT MENU
# ============================================================


def show_sessions() -> None:
    sessions = list_sessions()

    print()
    print("=" * 60)
    print("SESSÕES SALVAS")
    print("=" * 60)

    if not sessions:
        print()
        print("Nenhuma sessão salva.")

        return

    for index, name in enumerate(
        sessions,
        start=1,
    ):
        print(f"{index} - {name}")


def remove_saved_session() -> None:
    session_name = select_existing_session_name()

    if session_name is None:
        return

    print()

    confirmation = input(f'Excluir a sessão "{session_name}"? [s/N]: ').strip().lower()

    if confirmation not in (
        "s",
        "sim",
        "y",
        "yes",
    ):
        print()
        print("Exclusão cancelada.")

        return

    deleted = delete_session(session_name)

    print()

    if deleted:
        print("Sessão excluída.")
    else:
        print("Sessão não encontrada.")


def startup_menu():
    while True:
        print()
        print("=" * 60)
        print("IA MULTI-PROVIDER")
        print("=" * 60)

        print()
        print("1 - Nova sessão")
        print("2 - Continuar sessão")
        print("3 - Listar sessões")
        print("4 - Excluir sessão")
        print("0 - Sair")

        print()

        choice = input("Escolha: ").strip()

        if choice == "1":
            return create_new_session()

        if choice == "2":
            restored = restore_saved_session()

            if restored is not None:
                return restored

        elif choice == "3":
            show_sessions()

        elif choice == "4":
            remove_saved_session()

        elif choice == "0":
            return None

        else:
            print()
            print("Opção inválida.")


# ============================================================
# CHAT
# ============================================================


def run_chat(
    session_name: str,
    session: ConversationSession,
    input_path: Path,
) -> None:
    print()
    print("=" * 60)
    print("CHAT INICIADO")
    print("=" * 60)

    print()
    print(f"Sessão: {session_name}")

    print(f"Provider: {session.provider}")

    print(f"Entrada: {input_path}")

    print()
    print("Comandos:")
    print("  sair     -> salvar e encerrar")
    print("  limpar   -> apagar memória da conversa")
    print("  uso      -> mostrar uso total registrado")
    print("  provider -> trocar o provider atual")
    print("  salvar   -> salvar sessão manualmente")

    print()
    print("A sessão é salva automaticamente após mudanças importantes.")

    while True:
        print()

        user_message = input("Você: ").strip()

        if not user_message:
            continue

        command = user_message.lower()

        # ----------------------------------------------------
        # EXIT
        # ----------------------------------------------------

        if command == "sair":
            save_session(
                name=session_name,
                session=session,
                input_path=input_path,
            )

            break

        # ----------------------------------------------------
        # CLEAR
        # ----------------------------------------------------

        if command == "limpar":
            session.clear_history()

            save_session(
                name=session_name,
                session=session,
                input_path=input_path,
            )

            print()
            print("Memória da conversa apagada.")

            print("Sessão salva.")

            continue

        # ----------------------------------------------------
        # MANUAL SAVE
        # ----------------------------------------------------

        if command == "salvar":
            saved_path = save_session(
                name=session_name,
                session=session,
                input_path=input_path,
            )

            print()
            print(f"Sessão salva em:")

            print(saved_path)

            continue

        # ----------------------------------------------------
        # USAGE
        # ----------------------------------------------------

        if command == "uso":
            usage = get_usage_totals()

            print()
            print(format_usage_summary(usage))

            continue

        # ----------------------------------------------------
        # PROVIDER
        # ----------------------------------------------------

        if command == "provider":
            changed = change_session_provider(session)

            if changed:
                save_session(
                    name=session_name,
                    session=session,
                    input_path=input_path,
                )

                print("Sessão salva.")

            continue

        # ====================================================
        # MEMORY COMPACTION
        # ====================================================

        if session.should_update_summary:
            print()
            print("=" * 60)
            print("COMPACTAÇÃO DE MEMÓRIA")
            print("=" * 60)

            print()
            print("O histórico antigo precisa ser compactado.")

            print("Isso exige uma chamada adicional à API.")

            summary_prompt = build_summary_prompt(session)

            summary_report = analyze_documents(
                documents=[],
                extra_text=summary_prompt,
            )

            summary_confirmed = confirm_preflight_interactively(summary_report)

            if not summary_confirmed:
                print()
                print("Compactação não autorizada.")

                print(
                    "A mensagem atual não será enviada para evitar perda de contexto."
                )

                continue

            usage_before = get_usage_totals()

            print()
            print("Compactando memória...")

            try:
                summarize_session(session)

            except ProviderError as exc:
                print()
                print("=" * 60)
                print("ERRO NA COMPACTAÇÃO")
                print("=" * 60)

                print()
                print(format_error_for_user(exc))

                print()
                print("A sessão continua aberta.")

                continue

            except Exception as exc:
                print()
                print("=" * 60)
                print("ERRO NA COMPACTAÇÃO")
                print("=" * 60)

                print()
                print(format_error_for_user(exc))

                print()
                print("A sessão continua aberta.")

                continue

            usage_after = get_usage_totals()

            save_session(
                name=session_name,
                session=session,
                input_path=input_path,
            )

            print()
            print("Memória compactada e sessão salva.")

            print()
            print("Consumo da compactação:")

            print_operation_usage(
                before=usage_before,
                after=usage_after,
            )

        # ====================================================
        # MAIN PREFLIGHT
        # ====================================================

        conversation_prompt = session.build_conversation_prompt(
            current_user_message=(user_message),
        )

        report = analyze_documents(
            documents=session.documents,
            extra_text=conversation_prompt,
        )

        print()
        print("=" * 60)
        print("REQUISIÇÃO PRINCIPAL")
        print("=" * 60)

        confirmed = confirm_preflight_interactively(report)

        if not confirmed:
            print()
            print("Mensagem cancelada.")

            print("Nenhuma chamada de API foi realizada.")

            continue

        # ====================================================
        # API CALL
        # ====================================================

        usage_before = get_usage_totals()

        print()
        print("Enviando para a IA...")

        try:
            result = chat(
                session=session,
                user_message=user_message,
            )

        except ProviderError as exc:
            print()
            print("=" * 60)
            print("ERRO NA CHAMADA DA API")
            print("=" * 60)

            print()
            print(format_error_for_user(exc))

            print()
            print("Sua mensagem NÃO foi adicionada ao histórico.")

            print()
            print("A sessão continua aberta.")

            continue

        except Exception as exc:
            print()
            print("=" * 60)
            print("ERRO NA CHAMADA")
            print("=" * 60)

            print()
            print("Ocorreu um erro local ou interno:")

            print()
            print(format_error_for_user(exc))

            print()
            print("A sessão continua aberta.")

            continue

        usage_after = get_usage_totals()

        # ====================================================
        # AUTOSAVE AFTER SUCCESSFUL TURN
        # ====================================================

        save_session(
            name=session_name,
            session=session,
            input_path=input_path,
        )

        # ====================================================
        # RESPONSE
        # ====================================================

        print()
        print("=" * 60)
        print("RESPOSTA")
        print("=" * 60)

        print()

        if result.message:
            print(result.message)

        # ====================================================
        # STRUCTURED ACTIONS
        # ====================================================

        if result.has_outputs:
            print()
            print(f"Arquivos solicitados: {result.output_count()}")

            try:
                created_files = execute_structured_result(
                    result=result,
                    output_dir=(DEFAULT_OUTPUT_DIR),
                )

            except Exception as exc:
                print()
                print("Erro ao criar os arquivos:")

                print(str(exc))

            else:
                print()
                print("Arquivos criados:")

                for file in created_files:
                    print(file)

        # ====================================================
        # USAGE
        # ====================================================

        print()
        print("=" * 60)
        print("CONSUMO DESTE TURNO")
        print("=" * 60)

        print_operation_usage(
            before=usage_before,
            after=usage_after,
        )

        print()
        print("Sessão salva automaticamente.")

    print()
    print("=" * 60)
    print("SESSÃO ENCERRADA")
    print("=" * 60)

    print()
    print("Sessão salva em:")

    print(PATHS.sessions_dir)


# ============================================================
# MAIN
# ============================================================


def main() -> None:
    startup = startup_menu()

    if startup is None:
        print()
        print("Programa encerrado.")

        return

    session_name, session, input_path = startup

    run_chat(
        session_name=session_name,
        session=session,
        input_path=input_path,
    )


if __name__ == "__main__":
    main()
