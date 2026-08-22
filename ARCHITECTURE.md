# Arquitetura técnica

Este documento descreve apenas o que existe atualmente em `src/ai_engine`.

## Estrutura de `ai_engine`

| Área | Módulos | Responsabilidade atual |
|---|---|---|
| API pública | `__init__.py` | Define e reexporta explicitamente os contratos usados pela aplicação, além de roteamento, multimodal, batch, workflows, chat e sessões. |
| Configuração | `config.py`, `paths.py` | Localiza o `.env` do projeto e representa, separadamente, os paths operacionais. |
| Modelo de entrada | `models/document.py` | Representação comum de documentos, imagens e tabelas. |
| Ingestão | `readers/` | Converte arquivos suportados em `DocumentContent`. |
| Providers | `providers/` | Chamadas diretas aos SDKs Gemini, OpenAI e Anthropic. |
| Multimodal | `multimodal.py`, `images.py` | Roteia documentos e normaliza imagens. |
| Orquestração | `batch.py`, `workflow.py`, `prompts.py` | Coleta, leitura, prompt, modo individual/consolidado e workflow. |
| Saídas | `results.py`, `structured.py`, `actions_prompt.py`, `actions.py`, `exporters/` | Contrato de resposta, parsing, execução e gravação de arquivos. |
| Guardrails e telemetria | `limits.py`, `usage.py` | Estimativa/confirmação prévia e log de tokens reportados. |
| Conversa e persistência | `chat.py`, `session.py`, `sessions.py` | Histórico local, compactação, troca de provider e JSON de sessão. |
| Texto sem documentos | `router.py` | Carrega ambiente e roteia prompts simples ao provider. |
| Testes offline | `tests/test_*_offline.py` | Suíte de regressão automatizada com pytest e 228 testes, sem chamadas reais a providers. |
| Smoke tests | `tests/smoke/` | Verificações manuais com providers reais, protegidas contra execução durante importação e fora da coleta padrão. |

## API pública raiz

`ai_engine.__init__` é a fronteira suportada pela aplicação oficial. Além dos
18 símbolos já públicos de roteamento, documentos, batch, workflows, chat e
sessões, o contrato inclui os tipos `OperationalPaths`, `PreflightReport` e
`StructuredResult` e as operações:

- `get_paths()` e `load_documents()`;
- `analyze_documents()` e `format_preflight()`;
- `build_summary_prompt()` e `summarize_session()`;
- `execute_structured_result()`;
- `get_usage_totals()`, `usage_difference()` e `format_usage_summary()`.

`application/ia_interativa.py` importa esses serviços somente com
`from ai_engine import (...)`. Ela não importa diretamente `ai_engine.actions`,
`ai_engine.chat`, `ai_engine.limits`, `ai_engine.paths`, `ai_engine.usage` ou
`ai_engine.workflow`.

Essa superfície está estabilizada para a aplicação atual, mas pode evoluir de
forma compatível. Testes de contrato verificam presença em `__all__`, identidade
com os objetos dos módulos de origem, compatibilidade dos imports antigos,
ausência de ciclos e ausência de clients ou chamadas externas durante import.

## Paths operacionais

`paths.py` define `OperationalPaths`, um dataclass imutável com raiz e
diretórios derivados para entrada, saída, prompts, modelos, dados, sessões,
usage e temporários. `get_paths(root=...)` usa a seguinte precedência:

1. raiz explícita;
2. `IA_ROOT` já presente em `os.environ`;
3. fallback `C:\IA`.

O módulo não carrega `.env`, não cria diretórios e não participa da resolução
do pacote Python. Ele não manipula `sys.path`, `PYTHONPATH`, `.venv`, uv ou a
localização de `api`.

`prompts.py`, `sessions.py` e `usage.py` consultam `get_paths()` no momento de
cada operação sem argumento explícito. Assim, `IA_ROOT` não fica congelada na
importação. `prompts_dir`, `sessions_dir` e `usage_file` explícitos continuam
prevalecendo. As constantes `DEFAULT_*` históricas permanecem como aliases de
compatibilidade para os caminhos sob `C:\IA`.

## Modelo documental

`DocumentImage` contém `name`, bytes em `data` e `media_type` opcional. `DocumentTable` contém `rows: list[list[str]]`, nome e origem opcionais. Não há conceito separado de cabeçalho na entrada.

`DocumentContent` agrega `source_path`, texto extraído, listas de tabelas e imagens e metadados livres. Expõe propriedades de presença/conveniência e `to_text()`, que concatena texto e tabelas e acrescenta apenas a contagem das imagens.

Essa é a fronteira comum do sistema. Readers produzem o objeto; batch o combina; preflight o mede; providers consomem sua forma textual e seus bytes de imagem. `to_text()` inclui cada linha de tabela uma única vez.

## Readers e formatos

`read_document()` escolhe o reader pela extensão; `read_documents()` processa sequencialmente uma lista.

| Formato | Extensões | Conteúdo produzido |
|---|---|---|
| Texto | `.txt` | UTF-8 em `text`. |
| Markdown | `.md`, `.markdown` | UTF-8 bruto em `text`; não interpreta Markdown. |
| CSV | `.csv` | Uma tabela; usa UTF-8 com BOM, tenta detectar dialeto nos primeiros 4096 caracteres e cai no dialeto padrão. |
| Word | `.docx` | Parágrafos, tabelas e todos os itens sob `word/media/` no ZIP. |
| PDF | `.pdf` | Texto por página e imagens incorporadas; páginas com menos de 30 caracteres são renderizadas em PNG a 150 dpi. Classifica como `empty`, `digital`, `scanned` ou `mixed`. Não faz OCR local. |
| Excel | `.xlsx`, `.xlsm` | Valores calculados (`data_only=True`) como uma tabela por worksheet e metadados; linhas totalmente vazias são ignoradas e worksheet vazia produz tabela com `rows=[]`. |
| Imagem | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`, `.tiff`, `.tif` | Uma `DocumentImage` com bytes e MIME inferido. |

`workflow.collect_files()` aceita um arquivo ou apenas os filhos diretos de um diretório, filtra pelas mesmas extensões e ordena os caminhos.

## Providers Gemini, OpenAI e Claude

Há dois caminhos por provider: texto simples (`ask_gemini`, `ask_openai`, `ask_anthropic`), usado por `router.ask_ai()` e compactação; e documento (`ask_*_document`), usado por `multimodal.ask_document()`.

Os adaptadores criam um cliente a cada chamada, leem o modelo do ambiente e usam o SDK nativo:

- Gemini: `genai.Client().interactions.create`; texto e imagens são itens de `input`.
- OpenAI: `OpenAI().responses.create`; documentos usam `input_text` e `input_image` com data URL.
- Anthropic/Claude: `Anthropic().messages.create`; imagens base64 precedem o texto e há `max_tokens` explícito.

Aliases são `google` para Gemini e `anthropic`/`claude` para Anthropic. Os adaptadores não mantêm thread remota nem ID de conversa.

## Multimodal

`ask_document()` seleciona o adaptador. Antes do envio, cada imagem passa por `normalize_image()`: JPEG é regravado como JPEG; os demais formatos são regravados como PNG; erro de decodificação vira `ValueError`.

O prompt contém a instrução e `document.to_text()`. Imagens são anexadas separadamente no formato do SDK. Tabelas chegam como texto delimitado por `|`; imagens chegam como payload multimodal.

## Batch individual e consolidated

`process_batch_individual()` percorre documentos sequencialmente, faz uma chamada por item e retorna `dict[filename, response]`.

`process_batch_consolidated()` usa `combine_documents()` para criar um `DocumentContent` virtual com `source_path=Path("batch")`: prefixa texto com filename, copia e renomeia tabelas e imagens e agrega metadados. Uma única chamada multimodal processa esse documento. Em `auto`, um documento usa `individual`; dois ou mais usam `consolidated`.

## Workflow e prompts livres

`run_workflow()` coleta e lê um caminho; `run_workflow_documents()` recebe documentos já carregados, evitando releitura após preflight externo. `build_prompt()` exige instrução livre não vazia. Opcionalmente, `load_prompt()` carrega um caminho existente ou procura `.md`/`.txt` em `get_paths().prompts_dir`, concatenando template e instrução específica.

Os equivalentes estruturados acrescentam o contrato textual de outputs e convertem a resposta para `StructuredResult`.

## Outputs estruturados e actions

`actions_prompt.py` instrui o modelo a responder normalmente para análise ou retornar somente JSON quando o usuário pedir arquivos. As estruturas são `ResultTable`, `OutputRequest` e `StructuredResult`.

`parse_structured_result()` usa `json.loads`. JSON inválido ou raiz não-objeto vira mensagem textual sem outputs. Não há schema rígido.

`execute_structured_result()` percorre outputs. `execute_output()` valida TXT/MD/DOCX/PDF/XLSX, reduz filename ao basename contra traversal, acrescenta extensão quando ausente e delega ao exporter. Parsing não cria arquivos automaticamente: o chamador precisa invocar a action.

## Exporters

- TXT e MD: escrita UTF-8 direta.
- DOCX: heading opcional e um parágrafo com conteúdo.
- PDF: ReportLab/A4, título opcional, linhas como parágrafos e escaping de markup.
- XLSX textual: planilha `Resultado`, título em A1 e linhas na coluna A.
- XLSX tabular: uma planilha por tabela, nome truncado a 31 caracteres e headers em negrito.

## Preflight e limites

`analyze_documents()` produz `PreflightReport` com arquivos, caracteres, tokens estimados por `ceil(caracteres/4)`, imagens e bytes. O ambiente controla `AI_WARN_ESTIMATED_TEXT_TOKENS`, `AI_MAX_ESTIMATED_TEXT_TOKENS`, `AI_WARN_IMAGES`, `AI_MAX_IMAGES`, `AI_WARN_IMAGE_MB`, `AI_MAX_IMAGE_MB` e `AI_MAX_BATCH_FILES`.

O engine calcula o relatório com `analyze_documents()` e o converte em texto
com `format_preflight()`. A aplicação o apresenta e pede autorização em
`confirm_preflight_interactively()`: acima dos máximos exige `CONFIRMAR`; nos
demais casos aceita `s`, `sim`, `y` ou `yes`. Preflight não está conectado
automaticamente a workflow ou chat.

`ai_engine.limits.confirm_preflight()` mantém a política interativa antiga para
compatibilidade com consumidores existentes, mas não integra a API pública raiz
nem `ai_engine.__all__`.

## Usage tracking

Cada adaptador registra usage após a chamada. `UsageRecord` comporta input, output, total, thought e cached tokens. `log_usage()` acrescenta uma linha a `get_paths().usage_dir / "api_usage.csv"` quando não recebe arquivo explícito. Há funções para somar o CSV, calcular deltas e formatar resumo. Gemini preenche thought/cached quando disponíveis; os demais registram campos básicos.

## Chat contínuo e memória compactada

`ConversationSession` guarda provider, documentos, mensagens recentes, resumo e `pending_summary`. `chat()` monta prompt com resumo/histórico/pedido, executa workflow estruturado nos documentos e adiciona usuário e `result.message` ao histórico. A continuidade vem do reenvio do contexto local, não de estado remoto.

Acima de `max_history_messages` (10), mensagens antigas migram para `pending_summary`. Ao atingir `summary_batch_size` (4), `summarize_session()` pode fazer uma chamada textual separada combinando resumo anterior e pendências; depois substitui o resumo e limpa a fila.

A compactação não ocorre dentro de `chat()`. Enquanto não resumidas, mensagens pendentes não entram no prompt conversacional.

## Troca de provider preservando contexto

`change_provider()` valida e normaliza o provider. Com `keep_history=True`, mantém resumo, mensagens, pendências e documentos, que são reenviados ao novo provider. Com `False`, limpa memória textual, mas mantém documentos. Nenhum estado específico do provider é migrado.

## Sessões persistentes

`save_session()` grava JSON com nome, provider, `input_path`, resumo, limites de memória, mensagens e pendências em `get_paths().sessions_dir` por padrão. Há listagem, leitura e remoção. Um `sessions_dir` explícito prevalece.

`restore_conversation_session(data, documents)` exige documentos já carregados: o JSON guarda o caminho, não bytes ou `DocumentContent`. A camada chamadora precisa recarregar os documentos.

## Testes automatizados offline

A coleta padrão do pytest está configurada em `pyproject.toml` para descobrir somente arquivos `test_*_offline.py`. Assim, `uv run pytest` executa atualmente os 228 testes da suíte offline, todos passando. A suíte usa arquivos temporários, fakes, mocks e monkeypatch e cobre contratos observáveis de:

- models e readers;
- batch, workflow e prompts;
- structured outputs, actions e exporters;
- limits/preflight e usage tracking;
- chat, memória compactada e sessões persistentes;
- paths operacionais, resolução dinâmica e defaults da aplicação;
- API pública raiz, identidade dos reexports, ausência de ciclos e separação
  entre cálculo de preflight e confirmação humana;
- routing, multimodal, normalização de imagens e adapters de OpenAI, Gemini e Anthropic com clientes mockados.

Os adapters são testados sem credenciais ou rede: os testes verificam roteamento, payload básico, logging de usage e retorno textual contra clientes falsos. Isso não valida a integração real com os serviços.

Os quatro módulos em `tests/smoke/` são smoke tests manuais e não são executados pela coleta padrão. Seus nomes não correspondem a `test_*_offline.py`, e toda chamada real está dentro de uma função `main()` protegida por `if __name__ == "__main__":`; portanto, importar os módulos não dispara chamadas de rede. `smoke_ai_engine.py` cobre manualmente o caminho público `ai_engine.ask_ai()`, enquanto `smoke_openai.py`, `smoke_gemini.py` e `smoke_anthropic.py` exercitam diretamente os respectivos SDKs.

## Fluxo completo de dados

```text
arquivo/diretório
      |
collect_files -> readers -> DocumentContent[] -> preflight/confirm (externo)
                            |
                 prompt livre ou estruturado
                            |
                  individual / consolidated
                     |              |
             chamada por item   combine_documents
                     +------|-------+
                            v
                      ask_document
                            |
                      multimodal.py
                 (seleção do provider)
                            |
             to_text + normalize_image + adaptador
                            |
               Gemini / OpenAI / Anthropic
                  |                    |
                  +-> usage CSV        v
                                  resposta str
                                    |       |
                              retorno str   parse JSON
                                              |
                                      StructuredResult
                                        |           |
                                  histórico     actions
                                                  |
                                      TXT/MD/DOCX/PDF/XLSX
```

O caminho textual é separado: `ask_ai()` usa `router.py` para selecionar
`ask_gemini()`, `ask_openai()` ou `ask_anthropic()`. Ele é usado, por exemplo,
na compactação da memória e não participa do roteamento de `ask_document()`.

No chat, `session.documents` volta ao workflow e resumo/histórico entram no prompt. Persistência serializa somente estado textual e caminho de entrada; a restauração recarrega documentos fora do módulo de sessões.
