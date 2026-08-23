# Estado do projeto

> Checkpoint de consolidação documental da v1 em 23/08/2026. Antes de novas
> mudanças, confira este documento, o código e a suíte atual.

## Situação da v1

O núcleo técnico da v1 está concluído e próximo do freeze. O `ai-engine` lê
documentos, trabalha com OpenAI, Anthropic/Claude e Gemini/Google, mantém
contexto local e produz TXT, MD, DOCX, PDF e XLSX pelo contrato estruturado.

Baseline deste checkpoint:

```text
866 passed, 0 failed, 1 warning
```

O warning é um `DeprecationWarning` interno do `google-genai`. A suíte padrão é
offline; os smokes reais listados abaixo são evidência manual separada e não
integram essa contagem.

## Fluxo estruturado atual

```text
expect_outputs=True
  -> resolve provider + modelo configurado
  -> consulta capability native structured
  -> modelo supported: envelope structured nativo
  -> modelo unknown: prompt estruturado legado
  -> resposta textual str
  -> parse_structured_result(expect_outputs=True)
  -> validate_structured_result()
  -> plan_structured_outputs()
  -> actions/exporters
```

`expect_outputs=False` continua sendo o default compatível: não força modo
nativo e o parser aceita resposta textual normal. Não existe heurística por
palavras do prompt.

### Providers e transporte nativo

- OpenAI usa Responses API com `text.format`, `type="json_schema"` e
  `strict=true`.
- Anthropic/Claude usa Messages API com `output_config.format` e JSON Schema.
- Gemini/Google usa Interactions API com `response_format`, MIME
  `application/json` e schema.

Os três adapters continuam retornando `str` para o engine. Mesmo no caminho
nativo, a resposta passa pelo parser forte local e depois pelas camadas de
validação, planning e execução.

### Schema canônico

`src/ai_engine/structured_schema.py` contém o contrato canônico e expõe
`get_structured_result_json_schema()`, que retorna uma cópia profunda. O schema
representa `StructuredResult`, `OutputRequest` e `ResultTable`, aceita somente
`txt`, `md`, `docx`, `pdf` e `xlsx`, fecha os objetos com
`additionalProperties: false` e expressa `title`/`content` como string ou null.

O schema não tenta representar segurança de filename, coerência de extensão,
tables somente em XLSX, largura de rows, colisões, overwrite ou nomes de
sheets. Essas regras continuam em validation e planning.

### Capability por provider e modelo

`src/ai_engine/provider_capabilities.py` normaliza aliases, resolve o modelo
documental efetivo e responde se a combinação possui evidência local para
native structured output. A allowlist conservadora da v1 é:

| Provider | Modelo supported |
|---|---|
| OpenAI | `gpt-5` |
| Anthropic/Claude | `claude-sonnet-5` |
| Gemini/Google | `gemini-3.5-flash` |

Qualquer outro nome é `unknown`: isso não significa incompatibilidade, apenas
ausência de comprovação local nesta v1. Nesse caso, o workflow escolhe o prompt
estruturado legado antes da chamada e ainda exige JSON válido pelo parser
forte.

Os modelos são lidos dinamicamente de `OPENAI_MODEL`, `ANTHROPIC_MODEL` e
`GEMINI_MODEL`, definidos no `.env` do projeto ou no ambiente do processo. A
troca não exige alteração de código.

### Política de fallback e erros

O fallback é decidido exclusivamente antes da chamada:

- supported: native structured;
- unknown: prompt estruturado legado.

Depois que uma chamada native começa, não há segunda chamada automática em
modo legado. Refusal, incomplete, limite de tokens, schema rejection e demais
falhas normalizadas como `ProviderError` são propagadas. Isso evita custo,
retry e geração duplicados.

`STRUCTURED_OUTPUT_INSTRUCTIONS` permanece no prompt inclusive no caminho
nativo da v1. Além de a combinação ter sido validada nos smokes, as instruções
carregam regras semânticas que o schema portável não expressa. Reduzi-las é
uma avaliação de v2.

## Pipeline local e formatos

Parsing não grava arquivos. `parse_structured_result()` constrói e valida o
domínio; `execute_structured_result()` planeja todos os outputs antes da
primeira escrita e então chama os exporters.

- TXT e MD: conteúdo textual UTF-8.
- XLSX linear: sheet `Resultado`, título opcional e linhas na coluna A.
- XLSX tabular: uma sheet por `ResultTable`, com headers e rows.
- DOCX: título e texto; sem tabelas/imagens estruturadas ou Markdown avançado.
- PDF: título e texto; sem tabelas/imagens estruturadas ou Markdown avançado.

O template externo `relatorio_multimodal_com_imagens`, disponível em
`C:\IA\4_Prompts`, permite produzir documentos textuais com marcadores para
inserção manual de imagens. Imagem externa é referenciada pelo filename exato;
imagem interna é referenciada pelo documento, localização e descrição
inequívoca. A v1 não insere imagens fisicamente em DOCX/PDF.

Validation rejeita contrato e tipos inválidos. Planning resolve filename,
extensão, destino, colisões, overwrite e nomes de sheets. Falha anterior à
execução não inicia escrita. Uma falha real de exporter pode deixar arquivos
anteriores gravados, pois não há rollback transacional.

## Aplicação e operação

A aplicação oficial é `application/ia_interativa.py`; o launcher histórico em
`C:\IA\0_Scripts\ia_interativa.py` apenas delega para ela. Sem `IA_ROOT`, os
paths operacionais usam `C:\IA`, com entrada convencional em
`C:\IA\2_Entrada` (default da aplicação: `batch_teste`) e saída em
`C:\IA\3_Saída`.

Para uso cotidiano, `C:\IA\Iniciar IA.bat` entra no projeto e executa a
aplicação via `uv`, sem sync, testes, Git ou configuração de credenciais.

A CLI pergunta explicitamente se espera arquivos. O comando `multiline` (ou
`multi`) inicia entrada multilinha e uma linha contendo apenas `/fim` encerra
a mensagem.

### Templates externos e sessões

Na criação, o fluxo é provider -> template opcional -> entrada. Enter ou `0`
seleciona `[0] Nenhum — conversa normal`. `discover_prompt_templates()` lista
somente `.md`/`.txt` de `C:\IA\4_Prompts` com metadata válida:

```text
# Nome humano
> Descrição: descrição curta
```

Os oficiais são `resumir.md`, `analisar_documentos.md`,
`comparar_arquivos.md` e `relatorio_multimodal_com_imagens.md`.
`ConversationSession.prompt_template: str | None` persiste apenas o filename;
sessões antigas usam `None`. Ao restaurar, um template válido é preservado sem
nova pergunta. Se tiver desaparecido ou deixado de ser descobrível, a CLI
avisa, muda para `None` e salva a correção.

`load_prompt()` remove a metadata antes da composição. O conteúdo efetivo do
template entra no preflight e na chamada principal, mas não na compactação
interna. A v1 não permite trocar, criar, editar ou excluir templates no chat.

## Evidência manual separada

Smokes native structured reais:

| Provider | `outputs=[]` | TXT end-to-end |
|---|---:|---:|
| OpenAI (`gpt-5`) | PASS | PASS |
| Anthropic/Claude (`claude-sonnet-5`) | PASS | PASS |
| Gemini/Google (`gemini-3.5-flash`) | PASS | PASS |

Também permanecem válidos os testes manuais anteriores de exporters/fluxo:

```text
TXT            PASS
Markdown       PASS
XLSX linear    PASS
XLSX tabular   PASS
DOCX           PASS
PDF            PASS
```

Smokes manuais da integração de templates:

- persistência sem provider: `Iniciar IA.bat` -> criar sessão -> selecionar
  Resumir -> sair -> reabrir -> continuar -> `Template da sessão: Resumir`:
  PASS;
- aplicação real: OpenAI + Resumir + pergunta `O que tem aqui?`: a resposta
  veio como síntese e preservou os fatos, apesar de o usuário não pedir resumo
  explicitamente; uma chamada de API: PASS.

Essas duas listas têm escopos diferentes. Não há evidência de que todos os
formatos tenham sido testados nos três providers.

## Decisões preservadas na v1

- `DocumentContent` é a fronteira comum entre readers, batch e providers.
- Providers são stateless; conversa e persistência permanecem locais.
- `expect_outputs` é explícito e não deriva do texto do usuário.
- Schema/transporte, parsing, validation, planning e escrita são camadas
  distintas.
- O parser e os guardrails locais permanecem depois do transporte nativo.
- Não há fallback silencioso depois de uma chamada native.

## Itens de v2

- Pydantic ou parsing tipado dos SDKs.
- Redução de `STRUCTURED_OUTPUT_INSTRUCTIONS` no caminho native.
- Tabelas, imagens e renderização avançada em DOCX/PDF.
- Rollback transacional de escritas parciais.
- Capability mais rica que a allowlist mínima da v1.
- Evolução de sessões, scripts legados, batch paralelo e OCR local.
- UX avançada de templates, como troca no chat, CRUD, categorias, favoritos,
  busca ou seleção automática.

## Próximos passos para fechar a v1

1. Executar regressão final.
2. Cumprir o checklist manual final, sem ampliar escopo.
3. Fazer freeze e versionamento da v1.

## Portabilidade após o freeze da v1.0.0

A tag `v1.0.0` permanece como snapshot congelado. A release v1.1.0 adiciona
instalação reproduzível com o contrato `<Root>\api`:

- `scripts\setup_workspace.ps1` cria a árvore operacional sem apagar dados;
- `workspace_assets` fornece os quatro prompts oficiais e o template do
  launcher;
- o launcher gerado define `IA_ROOT` e aponta para o repo instalado;
- `.env.example` contém somente nomes de configuração e placeholders;
- `.env` existente nunca é lido ou substituído pelo setup;
- conflitos de launcher/prompts são preservados, salvo `-Force` explícito;
- `uv sync` é padrão, com `-SkipSync` para preparação offline.

Detalhes operacionais estão em `SETUP_WORKSPACE.md`.

## Sessões sem documentos — v1.1.1

A aplicação interativa aceita sessões com `documents=[]`. Uma pasta válida sem
arquivos suportados inicia chat textual, mantendo template, preflight, memória,
structured output e persistência. `collect_files()` e os workflows
programáticos baseados em path continuam estritos por default; a interface usa
explicitamente `load_documents(..., allow_empty=True)`. Paths inexistentes e
arquivos explicitamente não suportados continuam sendo erros.
