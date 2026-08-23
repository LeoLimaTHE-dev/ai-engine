# Estado do projeto

> Checkpoint documental de 23/08/2026. Futuros agentes devem conferir este
> arquivo, o código e os testes atuais antes de alterar o projeto.

## Resumo operacional

O núcleo necessário para uma primeira versão local utilizável está
majoritariamente implementado. O `ai-engine` lê documentos, conversa com
Gemini, OpenAI ou Anthropic/Claude, mantém contexto local e gera arquivos por
um contrato estruturado. Structured outputs funcionam end-to-end nos cinco
formatos atualmente suportados: TXT, MD, DOCX, PDF e XLSX.

O estado deste checkpoint foi comparado com a implementação e validado por
`uv run pytest -q`: **706 testes automatizados offline passaram, 0 falharam**.
Houve 1 `DeprecationWarning` originado em `google-genai`; ele não representa
falha da suíte. Os testes manuais descritos abaixo são evidência separada e não
estão incluídos nesses 706 testes.

## Implementado no projeto

- Modelo comum de documentos com texto, tabelas, imagens e metadados.
- Readers para TXT, Markdown, CSV, DOCX, PDF, XLSX/XLSM e formatos comuns de
  imagem.
- Integrações textuais e multimodais com Gemini, OpenAI e Anthropic/Claude.
- Batch individual ou consolidado, workflows com prompt livre e template
  opcional, preflight local, registro de usage e conversa com memória local.
- Persistência de sessões e troca de provider com preservação opcional do
  histórico.
- Contrato comum para erros de provider e retry controlado pelo engine em
  OpenAI/Anthropic; Gemini continua com o retry nativo do SDK.
- Aplicação interativa oficial em `application/ia_interativa.py` e API pública
  consumida pela raiz de `ai_engine`.
- Pipeline de structured outputs com parsing em dois modos, validação,
  planning completo anterior à escrita, execução e exporters.

## Pipeline de structured outputs

O fluxo conceitual implementado é:

```text
provider
  -> resposta
  -> parse_structured_result()
  -> validação
  -> planning
  -> execute_structured_result()
  -> exporter
  -> arquivo
```

Parsing e escrita são etapas separadas. `parse_structured_result()` produz um
`StructuredResult`; os arquivos só são criados quando o chamador invoca
`execute_structured_result()`.

### Dois modos do parser

`expect_outputs=False` é o default compatível/legado. Nesse modo, texto comum,
JSON inválido ou uma raiz JSON que não seja objeto podem virar um
`StructuredResult` apenas textual. APIs antigas foram preservadas quando
possível.

`expect_outputs=True` é o modo forte. Ele exige uma resposta JSON pura com
raiz objeto e valida o contrato construído. JSON inválido, JSON cercado por
fences, texto antes/depois do JSON ou uma resposta textual comum causam
`StructuredParseError`; não há fallback silencioso para texto.

O modo forte não é ativado por heurística textual. `expect_outputs=False`
continua sendo o default em `parse_structured_result()`, workflows e `chat()`.

### Decisão explícita na CLI

A aplicação pergunta, para cada mensagem normal:

```text
Espera arquivos nesta resposta? [s/N]:
```

Ela aceita `s`, `sim`, `y` e `yes` como respostas afirmativas e encaminha essa
decisão explicitamente para `chat(expect_outputs=...)`. Qualquer outra entrada,
inclusive Enter, resulta em `False`.

Não existe heurística que procure palavras como “PDF”, “DOCX” ou “arquivo” na
mensagem para decidir o modo do parser.

### Validação antes da escrita

`validate_structured_result()` rejeita dados incompatíveis antes que exporters
sejam chamados. Entre os problemas detectados estão:

- formato ausente ou não suportado;
- filename vazio ou inválido;
- campos e coleções com tipos incompatíveis;
- tabelas com headers, rows, células ou larguras inconsistentes;
- `tables` em TXT, MD, DOCX ou PDF, que não oferecem suporte a tabelas
  estruturadas nesse contrato.

### Planning antes da primeira escrita

`execute_structured_result()` chama `plan_structured_outputs()` antes de
percorrer os outputs. O planning resolve e verifica:

- basename, filename/path final e extensão coerente com o formato;
- caracteres, comprimento e nomes reservados de Windows;
- colisões entre outputs, inclusive sem diferença de maiúsculas/minúsculas;
- política `overwrite` e existência prévia quando `overwrite=False`;
- nomes de sheets XLSX, caracteres inválidos, limite de 31 caracteres e
  deduplicação determinística.

Consequência garantida: se houver erro de validação ou planning em qualquer
output, nenhuma escrita começa. Isso elimina o comportamento histórico no qual
um output anterior podia ser criado antes da descoberta de um erro estrutural
em um output posterior.

### Erros estruturados

- `StructuredParseError`: a resposta não pôde ser interpretada como o
  structured output esperado.
- `OutputValidationError`: o contrato foi interpretado, mas possui dados
  inválidos, seja na validação inicial ou no planning.
- `OutputExecutionError`: o planning passou, mas ocorreu uma falha real no
  exporter ou filesystem durante a escrita.

Um `OutputExecutionError` pode ocorrer depois que outputs anteriores já foram
escritos. Não existe rollback transacional atualmente.

### Compatibilidade

O novo pipeline preserva os caminhos antigos quando possível:

- `expect_outputs=False` permanece o default;
- `execute_output()` chamado diretamente mantém o comportamento histórico de
  sanitização, extensão e dispatch;
- `execute_structured_result()` usa validação e planning prévios e é o caminho
  forte para executar um resultado completo.

## Instruções enviadas ao modelo

`STRUCTURED_OUTPUT_INSTRUCTIONS` está alinhado ao runtime. Quando structured
output é esperado, o modelo é instruído a:

- retornar exatamente um objeto JSON puro;
- não usar fenced JSON nem texto antes/depois;
- usar somente TXT, MD, DOCX, PDF ou XLSX;
- usar filenames simples, seguros, distintos e com extensão coerente;
- não prometer tabelas estruturadas em DOCX/PDF;
- usar XLSX para dados tabulares estruturados.

As instruções também distinguem XLSX linear de XLSX tabular e deixam claro que
Markdown é conteúdo textual, não um mecanismo de renderização em DOCX/PDF.

## Formatos de saída suportados

### TXT — suportado e validado manualmente end-to-end

O campo textual `content` é gravado como UTF-8 em arquivo `.txt`.

### Markdown — suportado e validado manualmente end-to-end

O contrato usa `format = "md"`; `markdown` não é um formato aceito. O conteúdo
Markdown é texto gravado diretamente em `.md`. Isso não implica renderização
Markdown avançada em DOCX ou PDF.

### XLSX linear — suportado e validado manualmente end-to-end

Sem tabelas, o exporter cria a sheet `Resultado`, escreve o título em A1 e
começa as linhas do conteúdo em A3. Como evidência do smoke manual realizado,
o arquivo inspecionado continha:

```text
sheet: Resultado
A1 = Teste Linear
A2 = vazio
A3 = Primeira linha
A4 = Segunda linha
A5 = Terceira linha
```

Esses valores documentam o caso testado; não são conteúdo fixo nem requisito
geral do produto.

### XLSX tabular — suportado e validado manualmente end-to-end

Cada tabela planejada vira uma sheet com headers e rows. Como evidência do
smoke manual, a sheet `Dados` continha:

```text
A1 = Nome       B1 = Empresa
A2 = Almir      B2 = CONSERT
A3 = Cristiano  B3 = CONSERT
```

Esses valores são apenas a fixture inspecionada no teste manual.

### DOCX — suportado e validado manualmente end-to-end

O smoke manual confirmou dois parágrafos: P1 com `Teste DOCX` e P2 com o
conteúdo textual, incluindo uma quebra de linha interna preservada.

Limitações atuais do contrato DOCX:

- título e texto;
- sem tabelas estruturadas;
- sem imagens estruturadas;
- sem renderização Markdown avançada.

### PDF — suportado e validado manualmente end-to-end

O smoke manual confirmou um PDF de uma página com o título `Teste PDF`,
conteúdo textual presente e quebra de linha preservada.

Limitações atuais do contrato PDF:

- título e texto;
- sem tabelas estruturadas;
- sem imagens estruturadas;
- sem renderização Markdown avançada.

CSV, HTML e outros formatos não integram o contrato atual de structured
outputs.

## Testes automatizados offline

Baseline de 23/08/2026:

```text
706 passed, 0 failed, 1 warning
```

A coleta padrão do pytest usa os testes offline e cobre, entre outras áreas:

- models, readers, batch, workflows e prompts;
- parser nos modos legado e forte;
- validação, planning, actions e exporters;
- garantia de zero escrita em erro estrutural;
- integração explícita de `expect_outputs` entre CLI, chat e workflow;
- limits/preflight, usage, paths, API pública, conversa e sessões;
- routing, multimodal, imagens, adapters e erros dos providers com mocks.

São testes locais com fixtures, fakes, mocks e arquivos temporários. Eles não
validam credenciais, rede, disponibilidade dos serviços ou comportamento real
dos modelos.

## Smoke/manual verification end-to-end

Os testes abaixo exercitaram geração real de arquivo e o conteúdo foi aberto e
inspecionado, não apenas a existência do path:

```text
TXT            PASS
Markdown       PASS
XLSX linear    PASS
XLSX tabular   PASS
DOCX           PASS
PDF            PASS
```

- TXT/MD: leitura do conteúdo gravado;
- XLSX: inspeção de sheets e células com `openpyxl`;
- DOCX: inspeção de parágrafos com `python-docx`;
- PDF: contagem de páginas e extração textual com PyMuPDF.

O fluxo TXT foi testado manualmente com os três providers configurados:
OpenAI, Anthropic/Claude e Gemini. Isso não significa que todos os cinco
formatos tenham sido testados manualmente nos três providers; os demais smokes
de formato podem ter usado somente um provider.

Esses smokes manuais não fazem parte da contagem de 706 testes do pytest. Não
foram executados novos smoke tests externos neste checkpoint documental.

## Limitações e pendências conhecidas

- A CLI lê a mensagem com uma única chamada a `input("Você: ")`; portanto, a
  entrada atual é de uma linha. Prompts multilinha colados diretamente podem
  ser interpretados como múltiplas entradas/respostas. Por enquanto, prompts
  complexos devem ser enviados em uma única linha, descrevendo explicitamente
  as quebras desejadas. Entrada multilinha adequada é uma melhoria futura de
  UX.
- O contrato estruturado é imposto localmente por prompt, parsing e validação;
  ainda não usa structured output/schema nativo dos providers.
- DOCX/PDF estruturados aceitam apenas título e texto, sem tabelas, imagens ou
  renderização Markdown avançada.
- Não há rollback quando uma falha de execução ocorre após escritas anteriores.
- `overwrite=True` é o default de `execute_structured_result()`; a política e a
  UX de overwrite ainda precisam de decisão final.
- Preflight é coordenado pela aplicação, não chamado automaticamente pelo chat
  ou pelos workflows.
- Batch individual é sequencial, `collect_files()` não é recursivo e nomes de
  arquivo repetidos podem colidir no resultado intermediário.
- PDF não faz OCR local; páginas escaneadas são encaminhadas como imagem ao
  provider multimodal.
- Sessões não persistem o conteúdo dos documentos e não têm migração/versionamento
  de schema; a restauração exige reler o caminho de entrada.
- O chat reenvia contexto local e documentos; compactação de memória é
  explícita e exige chamada adicional.
- `README.md` continua vazio; instalação e uso ainda precisam de documentação
  final.

## Decisões arquiteturais que devem ser preservadas

- `DocumentContent` é a representação canônica entre readers, batch e
  providers.
- Providers são adapters stateless; conversa e persistência permanecem locais.
- A aplicação decide interação humana, preflight, paths e apresentação; o
  engine fornece operações reutilizáveis.
- A decisão de esperar arquivos é explícita e não baseada no texto da mensagem.
- Parsing, validação/planning e escrita são fronteiras distintas.
- Falha estrutural deve ser descoberta antes da primeira escrita.
- Structured output nativo do provider pode ser avaliado, mas não é requisito
  obrigatório para considerar a primeira versão local utilizável.

## Próximos passos e ponto de retomada

Retomar pelo endurecimento operacional do fluxo já existente, sem ampliar
formatos antes de estabilizá-lo:

1. Criar testes controlados para falhas reais durante exporter/filesystem,
   verificando partial writes e mensagens de `OutputExecutionError`.
2. Decidir se haverá suporte futuro a tabelas e imagens estruturadas em
   DOCX/PDF e, se houver, definir contrato antes da implementação.
3. Avaliar structured output/schema nativo dos providers como melhoria de
   robustez, sem tratá-lo como bloqueador da primeira versão utilizável.
4. Melhorar a UX da CLI para entrada multilinha real.
5. Definir política e UX de overwrite, inclusive confirmação ou escolha de
   destino quando o arquivo já existir.
6. Fazer a revisão final da documentação e preencher o `README.md` com
   instalação, execução e exemplos da API/CLI.
7. Executar uma rodada final de regressão offline e smoke manual controlado.
8. Depois disso, priorizar melhorias de v2, configuração uniforme, migração de
   sessões e redução de dívidas dos scripts legados.
