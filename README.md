# ai-engine

Engine local multi-provider para ler documentos, manter conversas e gerar
arquivos estruturados com OpenAI, Anthropic/Claude ou Gemini/Google.

## Instalação e execução

Requisitos: Python 3.14+ e [uv](https://docs.astral.sh/uv/).

A release v1.1.0 inclui um fluxo de instalação reproduzível. Para uma
instalação nova, clone o repositório diretamente em `<Root>\api` e execute o
setup idempotente:

```powershell
git clone <URL_DO_REPOSITORIO> C:\IA\api
cd C:\IA\api
.\scripts\setup_workspace.ps1
```

Outra raiz pode ser usada quando o clone respeita o mesmo contrato, por
exemplo `D:\IA\api`:

```powershell
.\scripts\setup_workspace.ps1 -Root "D:\IA"
```

O setup cria a árvore operacional, instala launcher, prompts e o manual humano
a partir de `workspace_assets`, cria `.env` somente se ausente e executa
`uv sync`. O manual fica em
`<Root>\Guia_Ambiente_IA_Multi_Provider_v1.1.1.docx`. Consulte
[`SETUP_WORKSPACE.md`](SETUP_WORKSPACE.md) para `-SkipSync`, `-Force` e a
política não destrutiva.

Para uso cotidiano, dê dois cliques em `C:\IA\Iniciar IA.bat`. Para executar
manualmente ou diagnosticar a inicialização:

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

Use o `.env` local criado a partir de `.env.example` e preencha as credenciais
necessárias aos providers. O setup nunca substitui um `.env` existente. Os nomes
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

Na criação de uma sessão, o fluxo é provider -> template opcional -> entrada.
`[0] Nenhum — conversa normal` é o default, inclusive ao pressionar Enter. O
template escolhido é salvo pelo filename e reaplicado ao restaurar a sessão.

A v1.1.1 adiciona sessões interativas sem documentos. Se uma pasta válida
estiver vazia ou não tiver arquivos suportados, a sessão começa com zero
documentos e funciona como chat textual. Paths inexistentes e arquivos
explicitamente não suportados continuam sendo rejeitados. `collect_files()`
permanece estrito por padrão; somente a interface ativa `allow_empty`.

A CLI pergunta se a resposta deve gerar arquivos. Essa decisão vira
`expect_outputs`:

- `False`: preserva respostas textuais compatíveis;
- `True`: exige o contrato JSON e mantém parser/validação locais fortes.

Para mensagens com várias linhas, digite `multiline` (ou `multi`), cole o
conteúdo e finalize com uma linha contendo somente `/fim`.

## Templates externos

`C:\IA\4_Prompts` contém uma biblioteca opcional de instruções reutilizáveis:

- `resumir.md`: síntese objetiva com preservação dos fatos;
- `analisar_documentos.md`: correlação de fatos, divergências e lacunas;
- `comparar_arquivos.md`: comparação de informações equivalentes;
- `relatorio_multimodal_com_imagens.md`: relatório com referências manuais de
  imagens.

Templates oficiais usam `# Nome humano` e `> Descrição: ...`. Arquivos sem essa
metadata não aparecem no menu. Se um template salvo desaparecer, a restauração
avisa, muda a sessão para Nenhum e salva a correção. Não há troca de template
durante o chat na v1. Se estiver em dúvida, escolha Nenhum.

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

Para documentos multimodais, o template externo
`relatorio_multimodal_com_imagens` pode ser carregado de `C:\IA\4_Prompts`.
Ele orienta referências para inserção manual: imagens externas usam o filename
exato; imagens internas usam documento, localização e descrição inequívoca.
A inserção física automática de imagens em DOCX/PDF permanece fora da v1.

## Testes

```powershell
uv run pytest -q
```

Baseline documental da v1: `866 passed, 0 failed, 1 warning`. A suíte padrão é
offline e não executa os smokes reais em `tests/smoke/`.
