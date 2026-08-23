# Auditoria de Structured Outputs nativo

## Objetivo e escopo

Esta auditoria avalia se o contrato atual de `StructuredResult` pode substituir
ou complementar o fluxo “prompt pedindo JSON + `parse_structured_result()`”
com geração estruturada nativa de OpenAI, Gemini e Anthropic.

Esta etapa não altera produção nem testes. Toda a evidência foi obtida offline,
a partir do código do projeto, testes e SDKs instalados. Nenhuma chamada de API,
smoke test ou consulta à internet foi realizada.

As afirmações são classificadas assim:

- **Projeto:** comprovado pelo código ou testes do `ai-engine`.
- **SDK:** comprovado por versão, assinatura, tipo, docstring ou fonte instalada.
- **Recomendação:** inferência arquitetural, ainda não implementada.
- **Verificação externa:** comportamento do serviço/modelo que o SDK local não
  consegue provar.

## Baseline

- Data da auditoria: 23/08/2026.
- Branch: `main`.
- HEAD: `408d4ce Add multiline input mode to interactive CLI`.
- Working tree inicial: limpo.
- `uv run pytest -q`: **717 passed, 0 failed, 1 warning** em 13,28 s.
- Warning: `DeprecationWarning` interno de `google-genai`.

## Versões instaladas

| SDK | Versão | Evidência |
|---|---:|---|
| `openai` | 3.1.0 | `uv pip show openai` |
| `google-genai` | 2.18.1 | `uv pip show google-genai` |
| `anthropic` | 0.122.0 | `uv pip show anthropic` |
| `pydantic` | 2.13.4 | dependência transitiva no lockfile |

`pydantic` não é dependência direta do projeto em `pyproject.toml`; chega
pelos SDKs.

## Arquitetura atual

### Fluxo efetivo

**Projeto.** O fluxo structured atual é:

```text
CLI define expect_outputs explicitamente
  -> chat()
  -> run_structured_workflow_documents()
  -> STRUCTURED_OUTPUT_INSTRUCTIONS no prompt
  -> ask_document()
  -> adapter do provider
  -> string
  -> parse_structured_result()
  -> validate_structured_result()
  -> StructuredResult
  -> execute_structured_result()
  -> plan_structured_outputs()
  -> exporter
  -> arquivo
```

Mesmo com `expect_outputs=False`, o workflow acrescenta as instruções de
structured output ao prompt; o flag decide se o parser aceita fallback textual
ou exige JSON válido. Não existe detecção por palavras da mensagem.

### APIs atualmente usadas

| Provider | API do adapter | Texto | Documento/multimodal |
|---|---|---|---|
| OpenAI | Responses API | `client.responses.create()` | mesma API com `input_text` e `input_image` |
| Gemini | Interactions API | `client.interactions.create()` | mesma API com itens `text` e `image` |
| Anthropic | Messages API | `client.messages.create()` | mesma API com blocos `image` e `text` |

Os adapters retornam `str`: `response.output_text`, `interaction.output_text`
ou concatenação dos blocos textuais do Anthropic. Nenhum adapter envia schema
hoje.

Defaults encontrados:

| Provider | Texto | Documento |
|---|---|---|
| OpenAI | `gpt-5` | `gpt-5.6` |
| Gemini | `gemini-3.6-flash` | `gemini-3.7-flash` |
| Anthropic | `claude-sonnet-5` | `claude-sonnet-5` |

Os tipos instalados reconhecem esses nomes. Isso prova compatibilidade de
tipagem do cliente, não disponibilidade na conta nem suporte remoto ao recurso.

## Contrato atual de StructuredResult

### Modelo de domínio

**Projeto.**

```text
StructuredResult
  message: str
  outputs: list[OutputRequest] = []

OutputRequest
  format: str
  filename: str
  title: str | None = None
  content: str | None = None
  tables: list[ResultTable] = []

ResultTable
  name: str
  headers: list[str] = []
  rows: list[list[str]] = []
```

Formatos aceitos após normalização: `txt`, `md`, `docx`, `pdf` e
`xlsx`.

### Contrato conceitual em JSON Schema

Um schema canônico conservador para transporte seria:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "message": {"type": "string"},
    "outputs": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "format": {
            "type": "string",
            "enum": ["txt", "md", "docx", "pdf", "xlsx"]
          },
          "filename": {"type": "string"},
          "title": {"anyOf": [{"type": "string"}, {"type": "null"}]},
          "content": {"anyOf": [{"type": "string"}, {"type": "null"}]},
          "tables": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "name": {"type": "string"},
                "headers": {
                  "type": "array",
                  "items": {"type": "string"}
                },
                "rows": {
                  "type": "array",
                  "items": {
                    "type": "array",
                    "items": {"type": "string"}
                  }
                }
              },
              "required": ["name", "headers", "rows"]
            }
          }
        },
        "required": [
          "format",
          "filename",
          "title",
          "content",
          "tables"
        ]
      }
    }
  },
  "required": ["message", "outputs"]
}
```

Esse schema é mais explícito que o parser histórico, mas representa sem perda o
resultado validado que os exporters consomem. Campos opcionais do domínio são
expressos como obrigatórios e anuláveis, solução compatível com schemas
estritos.

### Nuances do parser existente

**Projeto.** O contrato efetivamente aceito pelo parser não é idêntico ao
schema acima:

- no modo forte, a raiz precisa ser objeto JSON;
- `message` ausente vira `""`;
- `outputs` ausente ou não-lista vira `[]`;
- itens não-objeto de outputs/tables são ignorados;
- `format` e `filename` ausentes acabam inválidos quando existe um output;
- valores de headers, rows e células são convertidos para `str` durante a
  construção;
- `title` e `content` precisam ser `str | None` após construção.

Portanto, a adoção nativa deve escolher um contrato canônico explícito, sem
tentar reproduzir toda a tolerância histórica do parser.

### JSON Schema versus validação semântica

Regras apropriadas ao schema:

- raiz objeto;
- tipos de todos os campos;
- enum de formatos;
- arrays e objetos aninhados;
- células, headers e rows como strings;
- nullable de `title` e `content`;
- ausência de propriedades adicionais.

Regras que devem continuar no engine:

- filename seguro, basename portátil, nomes reservados e limite do filesystem;
- extensão coerente e path final;
- colisões entre outputs e política de overwrite;
- tabelas permitidas somente para XLSX;
- largura de todas as rows igual aos headers ou entre si;
- deduplicação, caracteres e truncamento de nomes de sheets;
- execução dos exporters e tratamento de efeitos parciais.

A igualdade de largura entre arrays depende de dados irmãos e não é portável
nos subconjuntos de JSON Schema observados. Condicionais por formato também
teriam suporte desigual. Não devem ser a única defesa.

## Separação das camadas

Structured output nativo fortalece principalmente:

A. geração estruturada pelo provider;
B. decodificação/parsing do retorno.

Ele não substitui:

C. `validate_structured_result()`;
D. `plan_structured_outputs()`;
E. `execute_structured_result()` e exporters.

`OutputValidationError` e `OutputExecutionError` continuam necessários.

## OpenAI

### Suporte encontrado

**SDK.** O adapter já usa Responses API. Em OpenAI 3.1.0:

- `Responses.create(..., text=ResponseTextConfigParam)` aceita
  `text.format`;
- o formato JSON Schema contém `type="json_schema"`, `name`, `schema`,
  `description` opcional e `strict` opcional;
- `Responses.parse(..., text_format=Tipo)` existe e retorna
  `ParsedResponse[T]`;
- o helper de parsing aceita `pydantic.BaseModel` e tipos dataclass-like via
  `pydantic.TypeAdapter`;
- o SDK converte o tipo para schema com `strict=True`;
- em schemas estritos, o helper acrescenta
  `additionalProperties: false` a objetos e marca todas as propriedades como
  obrigatórias;
- `ParsedResponseOutputText.parsed` contém `T | None`;
- recusas são blocos separados `ResponseOutputRefusal` com campo `refusal`;
- a resposta representa estados `failed` e `incomplete`; detalhes
  incompletos distinguem `max_output_tokens` e `content_filter`.

Também é possível usar `responses.create` com schema manual e continuar lendo
`output_text`, sem adotar parsing tipado de imediato.

### Compatibilidade

Classificação: **compatível com adaptação pequena**.

O contrato usa apenas objetos, arrays, strings, null e enum. A forma estrita
deve exigir todos os campos, usando null para opcionais. Filename, relações
entre formato/tables e largura das rows permanecem na validação local.

### Pontos que exigem verificação externa

- suporte efetivo de `gpt-5`, `gpt-5.6` e aliases configurados ao schema;
- subconjunto exato de JSON Schema aceito pelo serviço nesses modelos;
- comportamento remoto em refusal e schema impossível;
- disponibilidade dos nomes de modelo na conta.

## Gemini

### Suporte encontrado

**SDK.** O projeto usa `client.interactions.create`, não
`models.generate_content`.

Na Interactions API instalada:

- `response_format` “enforces” um objeto JSON conforme o schema, segundo a
  docstring local;
- o formato textual usa
  `{"type": "text", "mime_type": "application/json", "schema": {...}}`;
- `response_mime_type` existe, mas está marcado como deprecated no modelo de
  Interaction em favor de `response_format`;
- o retorno `Interaction` possui `output_text`, mas não campo `.parsed`;
- status incluem `completed`, `failed`, `incomplete`,
  `budget_exceeded` e outros; errors têm `code` e `message`;
- os modelos `gemini-3.6-flash` e `gemini-3.7-flash` constam no tipo
  `Model` instalado.

Em uma API diferente do mesmo SDK, `models.generate_content`:

- aceita `response_mime_type="application/json"`;
- aceita `response_schema` como subconjunto OpenAPI-like, dict, tipo,
  `Schema` ou union;
- aceita `response_json_schema` como alternativa JSON Schema;
- expõe `GenerateContentResponse.parsed` quando `response_schema` é usado;
- documenta suporte a objetos, arrays, enums, `anyOf`, propriedades,
  `additionalProperties`, required e outros keywords, mas não ao JSON Schema
  completo.

Migrar de Interactions para `generate_content` apenas para obter `.parsed`
seria uma adaptação maior e interferiria no adapter, payload, erros/retry e
usage. Não é recomendada como primeiro passo.

### Compatibilidade

Classificação no caminho atual de Interactions: **compatível com adaptação
pequena a moderada**.

O schema canônico pode ser enviado manualmente em `response_format`; o
`output_text` ainda precisa ser decodificado e convertido para
`StructuredResult`. Arrays aninhados, objetos e enum cabem no formato
declarado, mas restrições semânticas permanecem locais.

### Pontos que exigem verificação externa

- suporte remoto de structured output por `gemini-3.6-flash` e
  `gemini-3.7-flash` na Interactions API;
- subconjunto e limites de JSON Schema específicos de `response_format`;
- comportamento remoto com opcionais/null, schema complexo, truncation e
  safety refusal;
- estabilidade da Interactions API, que usa internamente `_gaos`.

## Anthropic

### Suporte encontrado

**SDK.** Anthropic 0.122.0 oferece structured output na API estável de Messages:

- `messages.create(..., output_config=...)`;
- `output_config.format` recebe
  `{"type": "json_schema", "schema": {...}}`;
- `messages.parse(..., output_format=Tipo)` existe e retorna
  `ParsedMessage[T]`;
- o método tipado usa `pydantic.TypeAdapter`, gera JSON Schema, transforma-o
  para o subconjunto esperado e popula
  `ParsedTextBlock.parsed_output`;
- o tipo pode ser qualquer tipo aceito por `TypeAdapter`, não somente
  `BaseModel`;
- `Message.stop_reason` distingue `max_tokens`, `refusal`,
  `model_context_window_exceeded` e outros motivos.

O transformador instalado demonstra limitações importantes:

- objetos recebem `additionalProperties: false`;
- `oneOf` é convertido para `anyOf`;
- apenas tipos e formatos suportados ficam como keywords efetivos;
- constraints não suportados são movidos para `description`, tornando-os
  orientação ao modelo, não validação garantida;
- em arrays, apenas `minItems` 0 ou 1 é preservado; outros valores viram
  descrição.

### Tool use como alternativa

**SDK.** `ToolParam` oferece `input_schema` e `strict: bool`. Tool use pode
forçar argumentos estruturados e continua útil quando a intenção é executar
uma operação/função. Entretanto, é semanticamente diferente de pedir uma
resposta final estruturada: gera bloco `tool_use`, exige escolha/roteamento de
tool e possivelmente um ciclo de resultado da ferramenta.

Para `StructuredResult`, `output_config.format` é a correspondência direta.
Tool use não deve ser o caminho principal apenas para transportar a resposta.

### Compatibilidade

Classificação: **compatível com adaptação pequena** para schema manual;
**adaptação moderada** se `messages.parse` e modelos tipados forem introduzidos.

Objetos, arrays, enums e nullables simples são adequados. Constraints avançados
devem continuar locais. O default `claude-sonnet-5` aparece em `ModelParam`,
mas isso não comprova suporte remoto ao recurso.

### Pontos que exigem verificação externa

- modelos Anthropic que aceitam `output_config.format`;
- comportamento remoto de refusal com structured output;
- limites oficiais do schema e eventual header/recurso especial;
- disponibilidade de `claude-sonnet-5` na conta.

## Matriz comparativa

| Tema | OpenAI 3.1.0 | google-genai 2.18.1 | Anthropic 0.122.0 |
|---|---|---|---|
| API usada hoje | Responses | Interactions | Messages |
| Schema nativo na mesma API | sim, `text.format` | sim, `response_format` | sim, `output_config.format` |
| JSON Schema manual | sim | sim | sim |
| Parsing tipado na mesma API | `responses.parse` | não observado em Interactions | `messages.parse` |
| Pydantic/tipo automático | sim, inclusive dataclass-like | em `generate_content`, não no caminho atual | sim via TypeAdapter |
| Campo parsed | `parsed` no bloco textual | apenas em `GenerateContentResponse`, não Interaction | `parsed_output` no bloco textual |
| Refusal distinguível | bloco refusal | status/errors; sem tipo refusal específico observado | `stop_reason="refusal"` |
| Multimodal na mesma chamada | sim | sim | sim |
| Compatibilidade do contrato | adaptação pequena | pequena a moderada | pequena/manual; moderada/tipada |
| Verificação de modelo remoto | necessária | necessária | necessária |

## Schema único versus adapters

### Alternativa A: um schema enviado sem adaptação

É simples, mas frágil. Os SDKs e serviços usam envelopes diferentes e
subconjuntos diferentes. OpenAI força propriedades obrigatórias no modo
estrito; Anthropic transforma ou rebaixa constraints; Gemini possui superfícies
OpenAPI-like e JSON Schema distintas, e o projeto usa Interactions.

### Alternativa B: schema canônico e adapter por provider

**Recomendação.** Manter um schema canônico do engine e gerar uma representação
conservadora por provider:

```text
contrato StructuredResult
  -> schema canônico
  -> adapter OpenAI: text.format / responses.parse
  -> adapter Gemini: response_format + output_text
  -> adapter Anthropic: output_config.format / messages.parse
```

Os adapters devem alterar apenas envelope, keywords aceitos e estratégia de
extração. A validação semântica recebe sempre o mesmo `StructuredResult`.

## Dataclasses versus Pydantic

### Manter dataclasses + schema manual

Vantagens:

- preserva a API e os modelos atuais;
- evita duplicar modelos de domínio;
- funciona nos três envelopes;
- permite controlar um subconjunto conservador e estável;
- mantém parsing e validação independentes do SDK.

Custos:

- schema e dataclasses podem divergir se não houver testes de contrato;
- conversão dict → dataclass continua sendo responsabilidade do engine.

### Introduzir Pydantic

Vantagens:

- schema e parsing tipado automáticos em OpenAI e Anthropic;
- validação de tipos e mensagens de erro maduras;
- google-genai também aceita tipos/Pydantic em `generate_content`.

Custos:

- seria nova dependência direta do projeto, embora já esteja instalada
  transitivamente;
- pode duplicar modelos ou exigir migração de dataclasses públicas;
- schemas gerados ainda precisam ser adaptados aos subconjuntos dos providers;
- acopla transporte e domínio a Pydantic e às transformações de cada SDK.

**Recomendação:** primeira implementação com dataclasses atuais, schema
canônico manual e testes que comprovem sua equivalência. Avaliar Pydantic
depois, como decisão separada. Se passar a ser importado pelo engine, declará-lo
como dependência direta.

## Papel futuro de parse_structured_result()

`parse_structured_result()` deve continuar existindo:

- fallback para provider/modelo sem suporte nativo;
- compatibilidade de APIs antigas e `expect_outputs=False`;
- decodificação do `output_text` estruturado do Gemini Interactions;
- defesa adicional quando o provider retorna texto inesperado;
- ponto testado para conversão em `StructuredResult`.

No caminho tipado de OpenAI/Anthropic, pode surgir uma conversão direta do
objeto parseado para as dataclasses, seguida sempre de
`validate_structured_result()`. Não convém forçar objetos já parseados a
voltar para JSON apenas para reutilizar o parser textual.

## Fallback recomendado

**Recomendação.**

```text
expect_outputs=False
  -> fluxo textual compatível atual

expect_outputs=True
  + provider/modelo com capability nativa confirmada
  -> structured output nativo
  -> conversão para StructuredResult
  -> validação + planning + execução existentes

expect_outputs=True
  + capability ausente/desconhecida
  -> STRUCTURED_OUTPUT_INSTRUCTIONS atual
  -> parser forte atual
  -> validação + planning + execução existentes
```

Fallback não deve ocorrer silenciosamente depois de uma refusal ou erro de
schema em uma chamada já feita, pois poderia duplicar custo e esconder falhas.
Uma segunda tentativa deve depender de política explícita e ser contabilizada.

## Capability detection

A capability pertence a **provider e modelo**, além da superfície/API usada.
Um booleano apenas no provider é insuficiente.

Representação futura sugerida:

```text
ProviderCapabilities
  native_structured_output: supported | unsupported | unknown
  typed_parsing: bool
  schema_dialect: openai_strict | json_schema_subset | anthropic_subset
  multimodal_with_structured_output: supported | unsupported | unknown
```

A resolução deve considerar provider, nome/alias do modelo, versão do SDK e
caminho da API. Modelos configurados por ambiente e aliases desconhecidos
devem começar como `unknown` e usar fallback, não como suportados por
suposição.

## Impacto nos erros

### StructuredParseError

Continua relevante no fallback textual, no JSON de Gemini Interactions e em
respostas nativas vazias/inconsistentes. Pode ser menos frequente.

### OutputValidationError

Continua obrigatório. Schema nativo não cobre com portabilidade regras de
filename, formato/tables, largura de rows, colisões ou sheets.

### OutputExecutionError

Não muda: ocorre depois de validation/planning, no exporter/filesystem.

### Falhas novas a classificar futuramente

- schema rejeitado antes da geração;
- provider/modelo sem suporte;
- refusal;
- resposta incomplete/truncada ou limite de tokens;
- content filter/safety;
- structured generation sem objeto parseado;
- incompatibilidade entre versão do SDK e payload.

Hoje erros HTTP do SDK são normalizados como `ProviderError` e subclasses.
Uma futura implementação deve decidir, sem redesenhar agora, se refusal e
incomplete são erros de provider, parsing ou novos estados de domínio.

## Token e custo

Qualitativamente:

- o prompt atual repete contrato, regras e exemplos em texto;
- o modo nativo envia um schema, que também consome payload/contexto;
- um schema conservador tende a ser menor e menos ambíguo que instruções e
  exemplos extensos;
- maior confiabilidade pode reduzir parsing failures e tentativas repetidas;
- parsing tipado local não reduz por si só tokens;
- fallback/retry automático pode duplicar custo e deve ser explícito;
- não há dados offline para quantificar economia.

## Compatibilidade multimodal

**SDK.** Os três recursos estruturados coexistem na assinatura das mesmas APIs
que recebem os payloads multimodais atuais:

- OpenAI `responses.parse/create` recebe o mesmo `input` com texto/imagem e
  acrescenta `text_format` ou `text.format`;
- Gemini `interactions.create` recebe `input` e `response_format` na mesma
  chamada;
- Anthropic `messages.parse/create` recebe os mesmos `MessageParam` com
  blocos de imagem/texto e acrescenta `output_format` ou `output_config`.

Isso demonstra compatibilidade estrutural do cliente. A combinação real de
cada modelo com imagens e structured output requer smoke controlado e
verificação documental externa antes da liberação.

## Testabilidade offline futura

Preservar adapters mockados e smoke separado.

### OpenAI

- afirmar payload `text.format` com schema/name/strict;
- simular `ParsedResponse` com `parsed`;
- simular `ResponseOutputRefusal`;
- simular status incomplete por max tokens/content filter;
- preservar usage e normalização de BadRequest/schema rejection;
- repetir casos textual e multimodal.

### Gemini

- afirmar `response_format` com `type=text`, MIME JSON e schema;
- simular `Interaction(output_text=<JSON>, status=completed)`;
- simular JSON inválido apesar do modo nativo;
- simular failed/incomplete/budget_exceeded e errors;
- preservar usage e payload multimodal;
- testar modelo/capability unknown caindo no parser forte atual.

### Anthropic

- afirmar `output_config.format` com schema;
- simular `ParsedTextBlock.parsed_output`;
- simular `stop_reason=refusal`, `max_tokens` e context window;
- validar concatenação/seleção correta de blocos;
- testar `strict` tool apenas se uma feature de tool use for criada;
- preservar usage, retry e payload multimodal.

### Testes comuns

- equivalência schema ↔ dataclasses;
- conversão nativa → `StructuredResult`;
- passagem obrigatória pela validação semântica;
- fallback por provider/modelo;
- ausência de fallback heurístico por conteúdo;
- zero chamadas reais na suíte offline.

## Riscos de regressão

| Risco | Nível | Mitigação |
|---|---|---|
| Quebrar `expect_outputs=False` e respostas textuais | alto | branch explícito e testes de compatibilidade |
| Assumir capability para modelo/alias desconhecido | alto | capability por provider+modelo, default unknown |
| Diferenças de dialeto/subconjunto do schema | alto | schema canônico conservador + adapters |
| Refusal/incomplete tratado como output válido | alto | inspeção explícita de blocos/status/stop_reason |
| Quebrar multimodal ao trocar método/payload | alto | manter API atual e testar texto/imagem |
| Migrar Gemini de Interactions para generate_content | alto | não fazer na primeira etapa |
| Alterar usage accounting | médio | testes com usage em sucesso/falha |
| Retry duplicar geração/custo | alto | sem fallback automático após chamada sem política |
| SDK atualizar assinatura/transformação | médio | versões mínimas, testes de contrato e revisão |
| Pydantic duplicar/divergir dos dataclasses | médio | adiar ou definir fonte única |
| Parser legado deixar de funcionar | médio | mantê-lo e preservar suíte atual |
| Aliases `claude`/`google` perderem routing | baixo | testes de routing/capability |
| Validation/planning/exporters serem contornados | alto | conversão única para domínio e pipeline obrigatório |

## Plano incremental recomendado

1. **Verificação externa prévia:** confirmar na documentação oficial atual a
   compatibilidade de cada modelo default com structured output, multimodal,
   refusals e subconjuntos de schema.
2. **Schema canônico:** definir uma função/constante de schema conservador e
   testes de equivalência com as dataclasses/validation, sem ligar provider.
3. **Capability model:** representar provider + modelo + API com
   supported/unsupported/unknown e fallback explícito.
4. **OpenAI primeiro:** é a superfície mais direta no caminho já usado,
   suporta schema manual e parsing tipado, e distingue refusal/incomplete.
5. **Anthropic segundo:** Messages atual já possui output_config/parse; testar
   cuidadosamente o transformador de schema e stop reasons.
6. **Gemini terceiro:** manter Interactions, enviar response_format e decodificar
   output_text; não migrar para generate_content neste checkpoint.
7. **Integração de fallback:** ligar apenas quando `expect_outputs=True` e a
   capability estiver confirmada; preservar prompt/parser forte em unknown.
8. **Regressão offline:** payloads, retornos, erros, usage, retry, aliases,
   multimodal, parser, validation e planning.
9. **Smokes controlados por provider/modelo:** texto structured primeiro,
   depois multimodal, fora da coleta padrão e com custo explícito.
10. **Reavaliar Pydantic:** somente após os três adapters funcionarem com schema
    manual e houver evidência de que parsing tipado reduz manutenção.

## Conclusão

**É tecnicamente viável implementar structured output nativo nos três
providers usando as APIs já adotadas pelo projeto.** Não é seguro fazer um
big-bang nem enviar exatamente o mesmo envelope/schema irrestrito a todos.

Recomendação final:

- implementar provider por provider;
- manter dataclasses e validation/planning/actions/exporters;
- criar schema canônico conservador e adapters específicos;
- começar por OpenAI, seguir com Anthropic e depois Gemini Interactions;
- manter `parse_structured_result()` como fallback e compatibilidade;
- ativar por capability de provider+modelo, nunca por heurística textual;
- verificar documentação oficial e executar smokes controlados antes de
  declarar suporte de um modelo.

Nenhuma implementação deve começar sem a verificação documental externa dos
modelos e limites atuais do serviço, porque o SDK instalado prova a superfície
do cliente, mas não a disponibilidade ou o comportamento remoto.
