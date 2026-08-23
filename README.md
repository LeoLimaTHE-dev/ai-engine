# ai-engine

Engine local multi-provider para ler documentos, manter conversas e gerar
arquivos estruturados com OpenAI, Anthropic/Claude ou Gemini/Google.

## Instalação e execução

Requisitos: Python 3.14+ e [uv](https://docs.astral.sh/uv/).

```powershell
cd C:\IA\api
uv sync
uv run python application\ia_interativa.py
```

Também existe o launcher local histórico:

```powershell
uv run --project C:\IA\api python C:\IA\0_Scripts\ia_interativa.py
```

## Ambiente e modelos

Crie `C:\IA\api\.env` com as credenciais necessárias aos providers. Os nomes
de modelo podem ser definidos no mesmo arquivo ou no ambiente do processo:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...

OPENAI_MODEL=gpt-5
ANTHROPIC_MODEL=claude-sonnet-5
GEMINI_MODEL=gemini-3.5-flash
```

Providers aceitos: `openai`, `anthropic`/`claude` e `gemini`/`google`. Os
modelos são lidos dinamicamente; os exemplos acima não são uma obrigação.

Sem `IA_ROOT`, a aplicação usa `C:\IA\2_Entrada\batch_teste` como entrada
inicial e `C:\IA\3_Saída` para arquivos gerados. `IA_ROOT` permite mudar a
raiz operacional.

## Uso interativo

A CLI pergunta se a resposta deve gerar arquivos. Essa decisão vira
`expect_outputs`:

- `False`: preserva respostas textuais compatíveis;
- `True`: exige o contrato JSON e mantém parser/validação locais fortes.

Para mensagens com várias linhas, digite `multiline` (ou `multi`), cole o
conteúdo e finalize com uma linha contendo somente `/fim`.

## Structured output

Com `expect_outputs=True`, o engine resolve provider e modelo antes da chamada.
Os modelos comprovados na v1 usam structured output nativo:

- OpenAI `gpt-5`;
- Anthropic `claude-sonnet-5`;
- Gemini `gemini-3.5-flash`.

Outros modelos são tratados como `unknown`, não como incompatíveis, e usam o
prompt estruturado legado com o mesmo parser forte. Se uma chamada native já
começou e falha, não existe segunda chamada automática em modo legado.

Os formatos de saída são `txt`, `md`, `docx`, `pdf` e `xlsx`. XLSX aceita
tabelas estruturadas. DOCX e PDF aceitam atualmente título e texto, sem
tabelas/imagens estruturadas ou renderização Markdown avançada.

## Testes

```powershell
uv run pytest -q
```

Baseline documental da v1: `832 passed, 0 failed, 1 warning`. A suíte padrão é
offline e não executa os smokes reais em `tests/smoke/`.
