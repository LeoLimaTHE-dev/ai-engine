# Snapshot técnico da v1

## Identificação

- Versão-alvo: `v1.0.0`.
- Data do snapshot: 23/08/2026.
- Branch: `main`.
- HEAD anterior à criação deste arquivo:
  `ce227e4 Document multimodal image reference template`.
- Package metadata final: `1.0.0`; a tag planejada para o freeze é `v1.0.0`.
- Working tree inicial: limpo.
- Pytest: `866 passed, 0 failed, 1 warning` em 15,00 s.
- Warning conhecido: `DeprecationWarning` interno do `google-genai` sobre
  `_UnionGenericAlias`.

Este documento registra o conteúdo técnico destinado ao freeze v1.0.0. Smokes
manuais são evidência separada da suíte automatizada.

## Arquitetura principal

```text
application/ia_interativa.py
  -> API pública ai_engine
  -> chat/workflow
  -> readers -> DocumentContent[]
  -> individual ou consolidated
  -> multimodal/router
  -> provider adapter
  -> resposta str
  -> parser/validation/planning
  -> actions/exporters
  -> TXT/MD/DOCX/PDF/XLSX
```

Camadas:

| Área | Implementação |
|---|---|
| Aplicação | `application/ia_interativa.py` |
| API pública | `src/ai_engine/__init__.py` |
| Modelos de entrada | `models/document.py` |
| Ingestão | `readers/` |
| Providers | `providers/` |
| Orquestração | `workflow.py`, `batch.py`, `multimodal.py`, `router.py` |
| Structured output | `results.py`, `structured_schema.py`, `structured.py`, `structured_validation.py`, `structured_planning.py` |
| Execução | `actions.py`, `exporters/` |
| Conversa/sessões | `chat.py`, `session.py`, `sessions.py` |
| Guardrails/telemetria | `limits.py`, `usage.py`, `paths.py`, `config.py` |
| Prompts | `actions_prompt.py`, `prompts.py`, `C:\IA\4_Prompts` |

`DocumentContent` é a representação comum entre readers, batch, preflight e
providers. Providers são adapters stateless; contexto conversacional é local.

## Ambiente operacional

`C:\IA` é a raiz operacional e `C:\IA\api` é o repositório/projeto Python.
Sem `IA_ROOT`, os diretórios convencionais são:

- entrada: `C:\IA\2_Entrada`;
- entrada default da aplicação: `C:\IA\2_Entrada\batch_teste`;
- saída: `C:\IA\3_Saída`;
- prompts: `C:\IA\4_Prompts`;
- sessões e usage: `C:\IA\6_Dados`.

O launcher cotidiano `C:\IA\Iniciar IA.bat` inicia a aplicação oficial via
`uv` sem executar sync, testes, Git ou configuração de credenciais/modelos.

`workspace_assets/` guarda cópias versionadas desse launcher e dos quatro
templates para representar a release e permitir reconstrução. O snapshot não
é operacional: o engine continua usando `C:\IA\4_Prompts`, e o launcher usado
no cotidiano continua em `C:\IA\Iniciar IA.bat`.

## Providers e APIs

| Provider | Aliases | API v1 | Structured native | Extração |
|---|---|---|---|---|
| OpenAI | `openai` | Responses API | `text.format`, JSON Schema, `strict=true` | `response.output_text` |
| Anthropic | `anthropic`, `claude` | Messages API | `output_config.format`, JSON Schema | blocos textuais concatenados |
| Gemini | `gemini`, `google` | Interactions API | `response_format`, MIME JSON, schema | `interaction.output_text` |

Todos retornam `str` ao engine. Não há `responses.parse()`, `messages.parse()`
ou Pydantic no domínio da v1.

OpenAI trata `failed`, `incomplete` e blocos de refusal no modo native.
Anthropic rejeita `stop_reason` incompatível com resposta completa. Gemini
rejeita status diferente de `completed`. Erros dos SDKs são normalizados para
`ProviderError` e subclasses.

OpenAI/Anthropic usam retry do engine após desativar retry do SDK. Gemini usa
retry nativo do SDK Interactions. Timeout e usage permanecem específicos por
adapter.

## Modelos e capabilities

Seleção dinâmica:

- `OPENAI_MODEL`;
- `ANTHROPIC_MODEL`;
- `GEMINI_MODEL`.

Combinações supported comprovadas localmente:

| Provider | Modelo |
|---|---|
| OpenAI | `gpt-5` |
| Anthropic | `claude-sonnet-5` |
| Gemini | `gemini-3.5-flash` |

`provider_capabilities.py` normaliza aliases e resolve provider + modelo.
Outros modelos são `unknown`, não declarados incompatíveis, e usam fluxo
legado antes da chamada. Não existe fallback automático depois que uma chamada
native foi iniciada.

## Structured output

### Schema canônico

`structured_schema.py` expõe `get_structured_result_json_schema()`, que retorna
cópia profunda do schema provider-neutral.

Características:

- raiz `object` com `additionalProperties: false`;
- required raiz: `message`, `outputs`;
- formatos: `txt`, `md`, `docx`, `pdf`, `xlsx`;
- OutputRequest fechado e com `format`, `filename`, `title`, `content`,
  `tables` obrigatórios;
- `title` e `content`: string ou null;
- ResultTable fechado, com `name`, `headers`, `rows`;
- headers e células: strings.

### Modelo de domínio

```text
StructuredResult(message: str, outputs: list[OutputRequest])
OutputRequest(format, filename, title, content, tables)
ResultTable(name, headers, rows)
```

### Pipeline v1

```text
expect_outputs=True
  -> capability(provider, modelo)
  -> supported: schema nativo
     unknown: STRUCTURED_OUTPUT_INSTRUCTIONS legado
  -> provider
  -> resposta str
  -> parse_structured_result(expect_outputs=True)
  -> validate_structured_result()
  -> plan_structured_outputs()
  -> execute_structured_result()
  -> exporter/filesystem
```

`expect_outputs=False` preserva resposta textual/compatível. Não há heurística
por conteúdo do prompt.

O parser local permanece depois do transporte nativo. Validation verifica
tipos, formatos, filenames, tables e rows. Planning resolve extensão/path,
nomes reservados, collisions, overwrite e sheets XLSX antes da primeira
escrita. Schema não substitui regras semânticas/filesystem.

`STRUCTURED_OUTPUT_INSTRUCTIONS` permanece no caminho native da v1.

## Readers

| Tipo | Extensões/comportamento |
|---|---|
| Texto | `.txt`, UTF-8 |
| Markdown | `.md`, `.markdown`, texto bruto |
| CSV | tabela, UTF-8 com BOM e detecção de dialeto |
| DOCX | parágrafos, tabelas e imagens de `word/media/` |
| PDF | texto por página, imagens incorporadas e render de páginas com pouco texto |
| Excel | `.xlsx`, `.xlsm`, uma tabela por worksheet |
| Imagem | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`, `.tiff`, `.tif` |

PDF classifica documentos vazios, digitais, escaneados ou mistos. Não existe
OCR local.

## Multimodal

Texto, tabelas serializadas e imagens são enviados na mesma chamada documental.
Imagens passam por normalização visual segura: JPEG permanece JPEG; demais
formatos viram PNG para transporte.

O filename externo original permanece em `DocumentImage.name` e é enviado em
texto adjacente à imagem antes da normalização. Imagens internas de DOCX/PDF
mantêm nomes técnicos; no batch, recebem vínculo com o documento de origem.
Bytes/MIME visuais não foram alterados pelo checkpoint de identidade.

## Batch

- Individual: sequencial, uma chamada por documento, retorna dict por filename.
- Consolidated: combina texto, tabelas, imagens e metadata em documento virtual.
- Auto: individual para um documento, consolidated para dois ou mais.
- O flag native structured é propagado pelos dois modos.

## CLI

A aplicação oficial suporta:

- criação, seleção, restauração e exclusão de sessões;
- providers Gemini, OpenAI e Claude;
- seleção opcional de template na criação, com `[0] Nenhum` como default;
- escolha de arquivo/diretório;
- preflight e confirmação;
- mensagens normais;
- `multiline`/`multi`, encerrado por uma linha contendo somente `/fim`;
- escolha explícita de `expect_outputs`;
- comandos `sair`, `limpar`, `uso`, `provider`, `salvar`;
- autosave após mudanças relevantes e turnos bem-sucedidos;
- execução de outputs e apresentação de erros estruturados/provider.

## Sessões e contexto

`ConversationSession` guarda provider, documentos carregados,
`prompt_template: str | None`, mensagens recentes, resumo e mensagens
pendentes de compactação. Sessões JSON persistem somente o filename opcional,
estado textual e `input_path`, não conteúdo do template nem bytes dos
documentos. Sessões antigas sem a chave restauram `None` e a entrada é relida.

Troca de provider pode preservar histórico. Contexto é reenviado localmente;
não há thread remota. Compactação é explícita e só substitui estado após
sucesso.

## Preflight e usage

Preflight estima caracteres/tokens, imagens, bytes e quantidade de arquivos. A
aplicação coordena a confirmação humana e inclui o conteúdo efetivo do template
ativo. Limites vêm do ambiente. A compactação interna não usa o template.

Usage é registrado em CSV append-only, por default sob
`C:\IA\6_Dados\usage`. Logging ocorre após sucesso remoto e fora do retry.

## Prompts

`load_prompt()` aceita caminho completo, filename ou nome sem extensão e busca
`.md`/`.txt` em `get_paths().prompts_dir`. Templates oficiais usam:

```text
# Nome humano
> Descrição: descrição curta
```

`discover_prompt_templates()` lista apenas arquivos com metadata válida e os
ordena pelo nome humano. Arquivos sem metadata não entram no menu, mas continuam
carregáveis explicitamente. A metadata não é enviada ao modelo.

Templates externos presentes no snapshot operacional:

- `resumir.md`: síntese objetiva;
- `analisar_documentos.md`: fatos, divergências e lacunas;
- `comparar_arquivos.md`: comparação de informações equivalentes;
- `relatorio_multimodal_com_imagens.md`: referências manuais de imagens.

Templates são opt-in. Enter/`0` seleciona Nenhum. A escolha ocorre somente na
criação e é restaurada sem nova pergunta. Template removido gera aviso,
fallback para `None` e save corretivo. O workflow combina template e instrução
do usuário.

## Exporters e formatos

| Formato | Estado v1 |
|---|---|
| TXT | conteúdo UTF-8 |
| MD | Markdown gravado como texto UTF-8 |
| DOCX | título opcional + conteúdo textual |
| PDF | título opcional + conteúdo textual em A4 |
| XLSX linear | sheet `Resultado`, título e linhas |
| XLSX tabular | uma sheet por ResultTable, headers e rows |

DOCX/PDF não têm tabelas ou imagens estruturadas, Markdown avançado nem uso de
documento existente como template visual.

## Referência manual de imagens

Capacidade validada:

```text
[INSERIR IMAGEM: filename]
[INSERIR IMAGEM DO DOCUMENTO: documento | localização | descrição]
```

O modelo pode selecionar semanticamente imagens pertinentes, distinguir
imagens na mesma página e ignorar imagens irrelevantes. Filename externo é
preservado exatamente. Imagem interna continua associada ao documento e à
localização/descrição.

Não há inserção física automática em DOCX/PDF. Fotografias são evidência
visual e exigem cautela para conclusões técnicas não observáveis.

## Testes automatizados

- Configuração: `python_files = ["test_*_offline.py"]`.
- Baseline: `866 passed, 0 failed, 1 warning`.
- Nenhuma chamada real na suíte padrão.
- Cobertura inclui domínio, readers, imagens, batch, routing, três adapters,
  capability, schema, prompt, parser, validation, planning, actions,
  exporters, paths, limits, usage, chat, sessões, API pública e aplicação.

## Smokes e validações manuais

Evidência externa à contagem automatizada:

- OpenAI native: `outputs=[]` PASS; TXT end-to-end PASS.
- Anthropic/Claude native: `outputs=[]` PASS; TXT end-to-end PASS.
- Gemini `gemini-3.5-flash`: `outputs=[]` PASS; TXT end-to-end PASS.
- TXT, MD, XLSX linear, XLSX tabular, DOCX e PDF: PASS.
- Multiline e `/fim`: PASS.
- Leitura multimodal e referências manuais de imagens: PASS.
- Filename externo preservado: PASS.
- Imagem interna referenciada por documento/localização/descrição: PASS.
- Seleção semântica de imagem relevante e descarte de irrelevantes: PASS.
- Persistência sem provider: launcher -> criar sessão com Resumir -> sair ->
  restaurar -> `Template da sessão: Resumir`: PASS.
- Aplicação real: OpenAI + Resumir + `O que tem aqui?` produziu síntese factual
  em uma chamada de API: PASS.

Não foi demonstrado que todos os formatos foram exercitados nos três
providers.

## Higiene do repositório

No início do snapshot, working tree estava limpo. `.env`, caches, bytecode e
artefatos operacionais não são rastreados. Smokes permanecem fora da coleta
padrão. Nenhuma credencial deve ser incluída em documentação ou Git.

## Limitações conhecidas

- Sem inserção física de imagens em DOCX/PDF.
- Sem tabelas estruturadas, imagens ou Markdown avançado em DOCX/PDF.
- Sem rollback transacional para partial writes durante execução.
- Allowlist de capability mínima; modelos unknown usam legado.
- Sem fallback automático pós-falha native.
- Sessões sem versionamento/migração e sem bytes dos documentos.
- Sem troca, CRUD, categorias, favoritos, busca ou seleção automática de
  templates durante a conversa.
- Batch individual sequencial; coleta não recursiva; risco com filenames
  duplicados no resultado intermediário.
- PDF sem OCR local.
- Usage CSV sem locking robusto.
- Aplicação concentra responsabilidades e não há console entry point.
- Scripts auxiliares/legados ainda duplicam paths e fluxos.

## Fora do escopo da v1

- Rich Documents.
- Inserção física de imagens em DOCX/PDF.
- Seções, paragraphs, tables, images, captions e page breaks estruturados.
- Tabelas estruturadas em DOCX/PDF.
- Uso de documento existente como modelo visual.
- Pydantic/parsing tipado.
- Remoção/redução das instruções textuais no caminho native.
- Rollback transacional.
- Catálogo completo/detecção remota de capability.
- Migração automática de sessões, OCR local e modernização integral de scripts.

## Backlog candidato da v2

Itens candidatos, não compromissos fechados:

1. Definir contrato de Rich Documents antes de alterar exporters.
2. Suportar inserção física de imagens em DOCX/PDF.
3. Modelar seções, paragraphs, tables, images, captions e page breaks.
4. Adicionar tabelas estruturadas a DOCX/PDF.
5. Avaliar documento existente como modelo visual.
6. Avaliar Pydantic/parsing tipado somente com benefício mensurável.
7. Medir e possivelmente reduzir o prompt no caminho native.
8. Definir rollback transacional ou política formal de partial writes.
9. Evoluir capability por provider/modelo/API sem assumir suporte.
10. Versionar/migrar sessões e reduzir dívidas de batch, OCR, usage, aplicação
    e scripts legados.

## Regra de imutabilidade

Depois da criação da tag `v1.0.0`, este arquivo representa o snapshot histórico
da versão congelada. Ele não deve ser atualizado para refletir funcionalidades,
arquitetura, baselines, modelos ou decisões da v2. Correções futuras pertencem
à documentação viva e a novos snapshots/version notes; qualquer errata do
registro histórico deve ser tratada explicitamente, sem reescrever a v1 como
se sempre tivesse contido mudanças posteriores.
