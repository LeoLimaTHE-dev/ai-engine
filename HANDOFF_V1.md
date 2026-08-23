# Handoff da v1 do ai-engine

Este documento é um ponto de entrada autocontido para uma nova IA assumir o
projeto em outra conversa. Ele descreve o estado consolidado imediatamente
antes do freeze da v1.0.0, como operar o ambiente e quais decisões devem ser
preservadas.

## Resumo do projeto

`ai-engine` é uma biblioteca e aplicação local Python para:

- ler documentos, planilhas, PDFs e imagens;
- enviar conteúdo textual e multimodal a OpenAI, Anthropic ou Gemini;
- manter conversa e sessões localmente;
- solicitar respostas estruturadas com schema nativo quando comprovado;
- validar, planejar e exportar TXT, MD, DOCX, PDF e XLSX;
- registrar usage e executar preflight antes de chamadas reais.

A aplicação oficial é `C:\IA\api\application\ia_interativa.py`. O arquivo
`C:\IA\0_Scripts\ia_interativa.py` é apenas um launcher local fino.
Para uso cotidiano, `C:\IA\Iniciar IA.bat` foi validado por duplo clique,
abertura do menu e saída normal.

## Estado da v1

- Versão-alvo do freeze: `v1.0.0`.
- Data deste handoff: 23/08/2026.
- Branch no checkpoint: `main`.
- HEAD antes da criação deste documento:
  `ce227e4 Document multimodal image reference template`.
- Baseline: `866 passed, 0 failed, 1 warning`.
- Warning conhecido: `DeprecationWarning` interno do `google-genai` sobre
  `_UnionGenericAlias`.
- Núcleo funcional concluído; faltam apenas freeze/versionamento e decisões
  explícitas sobre o início da v2.

## Estrutura de diretórios

```text
C:\IA                         workspace operacional, não é o repo Git
├── 0_Scripts\                launcher, ferramentas e scripts manuais/legados
├── 1_Projetos\               documentos organizados pelo usuário
├── 2_Entrada\                entrada convencional
│   └── batch_teste\          entrada default da aplicação
├── 3_Saída\                  saída default dos arquivos gerados
├── 4_Prompts\                templates externos reutilizáveis
├── 5_Modelos\                reservado; sem modelos locais integrados
├── 6_Dados\
│   ├── sessions\             sessões JSON
│   └── usage\                CSV de usage
├── 7_Temporario\             reservado
└── api\                      repositório Git e projeto Python
    ├── application\          aplicação interativa oficial
    ├── src\ai_engine\        biblioteca
    ├── tests\                suíte offline e smokes manuais isolados
    ├── pyproject.toml
    └── documentação
```

`C:\IA\api\workspace_assets` contém a cópia versionada do launcher e dos
quatro templates externos para release/reconstrução. Não mude paths de produção
para essa pasta: a operação continua usando `C:\IA\Iniciar IA.bat` e
`C:\IA\4_Prompts`. Sincronizações futuras devem ser deliberadas antes de uma
release.

## Regra crítica de localização

`C:\IA` é o workspace operacional. `C:\IA\api` é o repositório Git e o
projeto Python. Nunca presuma que comandos Git ou pytest devem rodar na raiz
`C:\IA`.

## Como começar qualquer nova sessão de desenvolvimento

```powershell
cd C:\IA\api
git status
git branch --show-current
git log -5 --oneline
uv run pytest -q
```

Se o working tree não estiver limpo, identifique e preserve mudanças do usuário
antes de editar. Não faça commit sem revisão/autorização explícita.

## Instalação e execução

Requisitos: Python 3.14+ e `uv`.

Após o freeze da `v1.0.0`, a release v1.1.0 passou a contar com
`scripts\setup_workspace.ps1`, `.env.example` e `SETUP_WORKSPACE.md`. O contrato
é `<Root>\api`; o setup é idempotente, não move o repo, não sobrescreve dados e
usa `workspace_assets` como fonte controlada. Não atribua esse mecanismo ao
snapshot histórico da v1.0.0.

Em uma instalação nova:

```powershell
git clone <URL_DO_REPOSITORIO> C:\IA\api
cd C:\IA\api
.\scripts\setup_workspace.ps1
```

```powershell
cd C:\IA\api
uv sync
uv run python application\ia_interativa.py
```

Launcher histórico:

```powershell
uv run --project C:\IA\api python C:\IA\0_Scripts\ia_interativa.py
```

Ainda não existe entry point de console empacotado.

Na v1.1.1, documentos passaram a ser opcionais na aplicação interativa. A
criação e a restauração usam `load_documents(..., allow_empty=True)`: uma pasta
válida vazia ou sem extensões suportadas produz `documents=[]` e segue para
chat textual. O workflow usa o adapter textual, mantém templates e parser
structured, e ativa native structured quando aplicável. Não relaxe
`collect_files()` globalmente; paths inexistentes e arquivos explicitamente não
suportados permanecem erros.

## Configuração e `.env`

O `.env` fica em `C:\IA\api\.env`, não deve ser versionado e contém as
credenciais necessárias. Também é possível definir tudo no ambiente do
processo.

Variáveis principais:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...

OPENAI_MODEL=...
ANTHROPIC_MODEL=...
GEMINI_MODEL=...
```

`IA_ROOT` altera a raiz operacional. Timeout e retry usam
`AI_PROVIDER_TIMEOUT_SECONDS`, `AI_PROVIDER_MAX_RETRIES`,
`AI_PROVIDER_RETRY_BASE_DELAY_SECONDS` e
`AI_PROVIDER_RETRY_MAX_DELAY_SECONDS`.

## Providers, aliases e APIs

| Provider | Aliases | API atual | Retorno ao engine |
|---|---|---|---|
| OpenAI | `openai` | Responses API | `str` via `output_text` |
| Anthropic | `anthropic`, `claude` | Messages API | `str` dos blocos textuais |
| Gemini | `gemini`, `google` | Interactions API | `str` via `output_text` |

Os adapters são stateless e separados porque envelopes, status, erros, retry,
usage e payload multimodal diferem entre SDKs. Não crie uma abstração comum
apenas para reduzir linhas semelhantes.

OpenAI e Anthropic desabilitam retry do SDK e usam retry do engine. Gemini
mantém retry nativo do SDK porque a Interactions API instalada usa `_gaos` e
não oferece controle público confiável equivalente.

## Structured output e capability

`expect_outputs` é uma decisão explícita, nunca uma heurística baseada em
palavras do prompt.

```text
expect_outputs=True
  -> resolve provider + modelo documental efetivo
  -> consulta capability
  -> supported: structured output nativo
  -> unknown: prompt estruturado legado antes da chamada
  -> resposta str
  -> parse_structured_result(expect_outputs=True)
  -> validation
  -> planning
  -> actions/exporters

expect_outputs=False
  -> modo textual/compatível
```

Modelos comprovados e allowlisted na v1:

| Provider | Modelo supported |
|---|---|
| OpenAI | `gpt-5` |
| Anthropic/Claude | `claude-sonnet-5` |
| Gemini/Google | `gemini-3.5-flash` |

Qualquer outro modelo é `unknown`, não “incompatível”. A troca via variável de
ambiente é dinâmica. Um modelo unknown usa o prompt legado antes da chamada e
continua sujeito ao parser forte.

Não há fallback pós-falha. Se uma chamada native começa e ocorre refusal,
incomplete, schema rejection ou outro `ProviderError`, o erro é propagado; não
se faz uma segunda geração legada e não se duplica custo.

Envelopes native:

- OpenAI: `text.format`, `type=json_schema`, `strict=true`;
- Anthropic: `output_config.format`, `type=json_schema`;
- Gemini: `response_format`, `mime_type=application/json`, `schema`.

`STRUCTURED_OUTPUT_INSTRUCTIONS` permanece também no caminho native da v1,
pois contém regras semânticas não expressas pelo schema comum.

## Schema, parser, validation, planning e actions

`src/ai_engine/structured_schema.py` contém o JSON Schema canônico e interno.
`get_structured_result_json_schema()` sempre devolve uma cópia profunda.

Domínio:

```text
StructuredResult
  message: str
  outputs: list[OutputRequest]

OutputRequest
  format: str
  filename: str
  title: str | None
  content: str | None
  tables: list[ResultTable]

ResultTable
  name: str
  headers: list[str]
  rows: list[list[str]]
```

O schema usa `additionalProperties: false`, exige os campos canônicos, permite
`title`/`content` nulos e aceita apenas `txt`, `md`, `docx`, `pdf`, `xlsx`.

Não mova para o schema regras de filename, extensão, paths, collisions,
overwrite, largura de rows, tables apenas em XLSX ou nomes de sheets. Essas
regras continuam em `structured_validation.py` e `structured_planning.py`.
Planning ocorre antes da primeira escrita. Falhas reais durante exporters não
têm rollback transacional.

## Readers e multimodal

Readers suportados:

- TXT UTF-8;
- Markdown bruto (`.md`, `.markdown`);
- CSV;
- DOCX com texto, tabelas e imagens de `word/media/`;
- PDF com texto, imagens incorporadas e renderização de páginas escaneadas;
- XLSX/XLSM com uma tabela por worksheet;
- PNG, JPG/JPEG, WebP, BMP, GIF e TIFF.

`DocumentContent` é a representação canônica com texto, tabelas, imagens e
metadados. Imagens são normalizadas para payload seguro sem alterar o arquivo
original. Cada adapter recebe texto adjacente identificando
`DocumentImage.name`.

Imagem externa independente preserva exatamente seu filename. Imagens internas
de DOCX/PDF mantêm nomes técnicos e, em batch consolidado, são prefixadas pela
origem documental. Não transforme imagem interna em suposto arquivo externo.

## Batch

- `individual`: uma chamada sequencial por documento.
- `consolidated`: combina os documentos em um `DocumentContent` virtual e faz
  uma chamada.
- `auto`: um documento usa individual; dois ou mais usam consolidated.

Batch é sequencial. A coleta não é recursiva. Filenames repetidos podem colidir
no dicionário intermediário do modo individual.

## CLI, sessões e contexto

A CLI oferece criação/restauração/exclusão de sessões, troca de provider,
preflight, usage, autosave e execução dos outputs.

Comandos: `sair`, `limpar`, `uso`, `provider`, `salvar`, `multiline`/`multi`.
No modo multiline, uma linha contendo somente `/fim` encerra a mensagem.

Na criação, o fluxo é provider -> template opcional -> entrada. O default é
`[0] Nenhum — conversa normal` por Enter ou `0`; não há troca durante o chat.

`ConversationSession` guarda provider, documentos em memória,
`prompt_template: str | None`, mensagens, resumo e pendências de compactação.
O JSON persiste somente o filename do template, caminho de entrada e estado
textual, não conteúdo do template nem bytes dos documentos. Sessões antigas
sem a chave restauram `None`.

Compactação é explícita e pode exigir chamada adicional. Falha de provider não
adiciona turno fictício nem destrói o estado anterior.

## Preflight e usage

Preflight estima texto/tokens, imagens, bytes e quantidade de arquivos. A
aplicação apresenta warnings/limites e pede confirmação; o engine não executa
essa confirmação automaticamente dentro do workflow.

O conteúdo efetivo do template entra no preflight principal. A compactação de
memória é uma operação interna separada e não recebe o template da sessão.

Usage é append-only em `C:\IA\6_Dados\usage\api_usage.csv` por default. Falha
ao gravar usage ocorre fora do retry e não repete uma chamada remota já
bem-sucedida.

## Formatos de saída

- TXT e MD: texto UTF-8.
- DOCX: título opcional e texto.
- PDF: título opcional e texto em A4.
- XLSX linear: sheet `Resultado`.
- XLSX tabular: uma sheet por tabela, com headers e rows.

DOCX/PDF não aceitam atualmente tabelas ou imagens estruturadas, nem renderizam
Markdown avançado. A inserção física automática de imagens não existe na v1.

## Referência manual de imagens

O template externo
`C:\IA\4_Prompts\relatorio_multimodal_com_imagens.md` é carregável por:

```python
load_prompt("relatorio_multimodal_com_imagens")
```

Marcadores validados:

```text
[INSERIR IMAGEM: filename]
[INSERIR IMAGEM DO DOCUMENTO: documento | localização | descrição]
```

O modelo pode selecionar imagens pertinentes e ignorar imagens irrelevantes.
Filename externo é preservado; imagem interna permanece vinculada ao documento.
Fotografia é evidência visual, não prova automática de propriedades técnicas
não observáveis.

## Prompts externos

`load_prompt()` procura caminho explícito ou nomes `.md`/`.txt` em
`get_paths().prompts_dir`, por default `C:\IA\4_Prompts`. Metadata válida usa:

```text
# Nome humano
> Descrição: descrição curta
```

`discover_prompt_templates()` lista somente arquivos com esse cabeçalho;
arquivos experimentais sem metadata continuam carregáveis explicitamente, mas
ficam fora do menu. `load_prompt()` remove a metadata do conteúdo enviado.
Templates oficiais:

- `resumir.md`: síntese objetiva preservando fatos;
- `analisar_documentos.md`: fatos, divergências, lacunas e correlação;
- `comparar_arquivos.md`: comparação de informações equivalentes;
- `relatorio_multimodal_com_imagens.md`: relatório com referências manuais.

Templates são opcionais e escolhidos somente na criação. Se um filename salvo
deixar de ser descobrível, a CLI avisa, muda para `None` e salva a correção.
Não existem comandos de troca nem CRUD, categorias, busca, favoritos ou seleção
automática na v1. Crie um template somente quando instruções estáveis estiverem
sendo repetidas; antes, confira se um oficial já cobre a necessidade.

## Testes automatizados e smokes

Comando padrão:

```powershell
uv run pytest -q
```

`pyproject.toml` coleta somente `test_*_offline.py`. Baseline: 866 testes
offline, todos passando, com um warning. Não há chamadas reais na coleta
padrão.

`tests/smoke/` contém harnesses manuais protegidos por `main()`. Não os execute
sem pedido explícito, credenciais, expectativa de custo e escopo controlado.

Evidência manual separada:

- OpenAI native: `outputs=[]` PASS e TXT end-to-end PASS;
- Anthropic/Claude native: os mesmos dois casos PASS;
- Gemini `gemini-3.5-flash`: os mesmos dois casos PASS;
- TXT, MD, XLSX linear, XLSX tabular, DOCX e PDF: PASS;
- multiline e `/fim`: PASS;
- multimodal, identidade e referência manual de imagens: PASS;
- seleção de imagem relevante e descarte de imagens irrelevantes: PASS;
- persistência de template sem provider (`Iniciar IA.bat` -> Resumir -> sair ->
  reabrir -> `Template da sessão: Resumir`): PASS;
- aplicação real do template OpenAI/Resumir à pergunta `O que tem aqui?`:
  síntese factual produzida em uma chamada de API: PASS.

Não conclua que todos os formatos foram testados nos três providers.

## Arquivos e módulos principais

- `README.md`: uso rápido.
- `PROJECT_STATE.md`: estado operacional vivo.
- `ARCHITECTURE.md`: arquitetura técnica do engine.
- `SYSTEM_ARCHITECTURE.md`: arquitetura de `C:\IA`.
- `NATIVE_STRUCTURED_OUTPUT_AUDIT.md`: auditoria histórica e consolidação.
- `V1_SNAPSHOT.md`: registro imutável depois da tag v1.0.0.
- `src/ai_engine/models/`: domínio documental.
- `src/ai_engine/readers/`: ingestão.
- `src/ai_engine/providers/`: adapters e erros.
- `provider_capabilities.py`: capability mínima provider + modelo.
- `structured_schema.py`: schema canônico.
- `structured.py`, `structured_validation.py`, `structured_planning.py`:
  pipeline estruturado local.
- `workflow.py`, `batch.py`, `multimodal.py`: orquestração.
- `prompts.py`: metadata, descoberta controlada, validação e carregamento.
- `chat.py`, `session.py`, `sessions.py`: conversa e persistência.
- `actions.py`, `exporters/`: execução e escrita.
- `application/ia_interativa.py`: aplicação oficial.
- `tests/test_prompts_offline.py` e
  `tests/test_interactive_application_templates_offline.py`: contratos de
  descoberta, menu e fallback.

## Decisões arquiteturais a preservar

- Workspace e repo são diretórios diferentes.
- `DocumentContent` é a fronteira comum de entrada.
- Providers permanecem stateless e específicos por SDK.
- `expect_outputs` é explícito.
- Capability é provider + modelo; unknown usa legado antes da chamada.
- Não há fallback pós-falha native.
- Schema, parsing, validation, planning e execução são camadas distintas.
- Parser/guardrails locais permanecem após provider native.
- Planning antecede a primeira escrita.
- Aplicação cuida de interação, confirmação e paths; engine fornece operações.
- Smokes reais ficam fora da suíte automatizada.
- Compatibilidade observável e testes têm prioridade sobre preferências de
  organização.

## O que não deve ser refatorado por estética

- Não unifique adapters apenas porque todos usam um booleano ou schema.
- Não migre dataclasses para Pydantic sem ganho comprovado e plano compatível.
- Não remova o parser forte porque providers aceitam schema nativo.
- Não remova `STRUCTURED_OUTPUT_INSTRUCTIONS` sem avaliar regras semânticas e
  smokes.
- Não mova confirmação de preflight para o engine sem redefinir a fronteira da
  aplicação.
- Não mova diretórios de `C:\IA` nem scripts legados sem contrato explícito.
- Não altere API pública, defaults, aliases ou sessão por preferência de nome.
- Não migre Gemini de Interactions para outra API apenas para obter `.parsed`.

## Limitações conhecidas da v1

- Sem inserção física de imagens em DOCX/PDF.
- Sem tabelas estruturadas ou Markdown avançado em DOCX/PDF.
- Sem rollback transacional após uma falha real de escrita.
- Capability é allowlist mínima, não catálogo completo de modelos.
- Sessões não persistem documentos e não têm versionamento/migração de schema.
- Batch individual é sequencial e coleta de diretórios não é recursiva.
- PDF não faz OCR local.
- Usage CSV não possui locking robusto.
- Scripts auxiliares/legados ainda duplicam fluxos e paths.
- Aplicação interativa concentra várias responsabilidades.
- Templates não podem ser trocados durante o chat nem gerenciados pela CLI.

## Backlog candidato da v2

Este backlog não é compromisso fechado:

- Rich Documents como contrato explícito;
- inserção física de imagens em DOCX/PDF;
- seções, paragraphs, tables, images, captions e page breaks;
- tabelas estruturadas em DOCX/PDF;
- documento existente como modelo visual;
- parsing tipado/Pydantic somente se justificar custo e migração;
- redução do prompt no caminho native após medição;
- rollback transacional ou política explícita de partial writes;
- capability mais rica por provider/modelo/API;
- evolução/versionamento de sessões;
- batch paralelo, coleta recursiva e resolução de filenames duplicados;
- OCR local e evolução de scripts/telemetria.

## Procedimento seguro para iniciar a v2

1. Confirme tag/branch e baseline limpo da v1.
2. Leia `V1_SNAPSHOT.md`, este handoff e os testes da área escolhida.
3. Escolha um checkpoint pequeno com fronteiras e arquivos permitidos.
4. Caracterize o comportamento atual antes de alterar.
5. Implemente de forma opt-in/compatível quando houver risco de quebra.
6. Use fakes/mocks; execute provider real somente com autorização explícita.
7. Rode focais, suíte completa e verificações Git.
8. Atualize documentação viva; não reescreva o snapshot histórico da v1.

## Instruções para a próxima IA

- Não presuma que `C:\IA` é o repositório Git; use `C:\IA\api`.
- Leia documentação, código e testes reais antes de alterar.
- Confirme working tree e baseline no começo.
- Não quebre compatibilidade por preferência arquitetural ou estética.
- Preserve a suíte offline e não converta smokes reais em testes automáticos.
- Não execute smokes/providers reais sem pedido explícito.
- Não faça commit, add ou push sem revisão/autorização.
- Prefira migração incremental e checkpoints reversíveis.
- Mantenha adapters separados quando a semântica dos SDKs for diferente.
- Preserve schema canônico, parser, validation, planning e actions como
  defesas complementares.
- Se o estado real divergir deste handoff, trate Git, código e testes como
  evidência primária e relate a divergência antes de prosseguir.
