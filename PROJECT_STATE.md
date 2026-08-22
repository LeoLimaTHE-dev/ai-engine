# Estado do projeto

> Instrução para futuros agentes: leia este arquivo **e confira o código real e os testes atuais antes de fazer qualquer alteração**. Este documento é um mapa operacional, não substitui a implementação. Atualize-o quando o estado do projeto mudar.

## Escopo deste documento

Este estado foi verificado diretamente apenas no repositório `C:\IA\api`. O ambiente completo também possui scripts e dados externos, especialmente em `C:\IA\0_Scripts`, `C:\IA\4_Prompts` e `C:\IA\6_Dados`; funcionalidades orquestradas por esses componentes, como `C:\IA\0_Scripts\ia_interativa.py`, não foram inspecionadas nesta revisão.

## Objetivo atual

O `ai-engine` é uma biblioteca Python local para ler documentos, enviá-los a Gemini, OpenAI ou Claude, manter conversas com contexto e transformar respostas em arquivos locais. O próximo ciclo deve priorizar robustez e organização, sem ampliar recursos antes de estabilizar o que já existe.

## Implementado

- Modelo comum de documento com texto, tabelas, imagens e metadados (`DocumentContent`, `DocumentTable` e `DocumentImage`).
- Readers para TXT, Markdown, CSV, DOCX, PDF, XLSX/XLSM e imagens PNG, JPEG, WebP, BMP, GIF e TIFF.
- Extração de texto, tabelas e imagens conforme o formato; páginas de PDF com menos de 30 caracteres são também renderizadas como PNG.
- Integrações textuais e multimodais com Gemini, OpenAI e Anthropic/Claude, selecionadas por nome ou alias.
- Normalização de imagens para JPEG ou PNG antes do envio multimodal.
- Processamento de vários documentos em modo individual ou consolidado; modo `auto` escolhe individual para um documento e consolidado para dois ou mais.
- Workflows com instrução livre e template opcional carregado de `.md` ou `.txt`.
- Respostas estruturadas em JSON, parsing com fallback para texto, descrição de arquivos solicitados e execução separada dessas saídas.
- Exportação para TXT, Markdown, DOCX, PDF e XLSX; XLSX aceita conteúdo linear ou tabelas em planilhas.
- Análise preflight local de volume estimado, com avisos, limites configuráveis por ambiente e confirmação interativa.
- Registro CSV de uso real informado pelos providers e funções de totalização/diferença.
- Conversa contínua baseada em prompt reconstruído, histórico recente, fila de mensagens antigas e resumo compacto produzido por uma chamada separada.
- Troca de provider com preservação opcional de histórico e normalização de aliases.
- Persistência JSON de sessões, listagem, remoção, leitura e restauração com documentos recarregados externamente.
- Primeira base automatizada de testes offline com pytest para regressões pontuais do modelo documental, reader XLSX e provider OpenAI multimodal.

## Validação existente

- Os 45 arquivos Python atuais de `src/` e `tests/` foram analisados pelo parser AST em 22/08/2026 sem erro de sintaxe.
- Os quatro testes offline atuais passam com pytest:
  - `test_to_text_includes_each_table_row_once`: serialização textual inclui cada linha de tabela uma única vez;
  - `test_read_xlsx_produces_one_table_per_worksheet`: XLSX produz exatamente uma tabela por worksheet com conteúdo;
  - `test_read_xlsx_represents_empty_worksheet_with_empty_table`: worksheet vazia é representada por uma tabela com `rows=[]`;
  - `test_ask_openai_document_returns_output_text_without_usage`: o caminho multimodal OpenAI retorna `response.output_text` quando `usage` é `None`, usando mock e sem chamada real à API.
- `tests/test_openai.py`, `tests/test_gemini.py` e `tests/test_anthropic.py` são scripts manuais de smoke test que fazem chamadas reais e imprimem a resposta. Não possuem assertions, mocks ou isolamento.
- `tests/Providertest.py` contém uma chamada manual a `ask_ai`, mas não importa esse símbolo e não constitui teste executável isoladamente.
- Nesta revisão, os smoke tests externos não foram executados para não consumir APIs. A cobertura automatizada atual limita-se à serialização textual de tabela, leitura XLSX por worksheet e worksheet vazia, e retorno do provider OpenAI multimodal sem usage. Os demais readers, providers e fluxos de batch, workflow, outputs, limites, usage, chat e sessões ainda não possuem cobertura automatizada demonstrada no repositório.

Assim, salvo pelos quatro comportamentos listados acima, “implementado” significa presente no código e inspecionado, não coberto por testes automatizados. O histórico Git registra checkpoints do projeto, mas commits não substituem testes reproduzíveis.

## Limitações e pendências conhecidas

- Preflight e confirmação existem, mas não são chamados pelos workflows nem pelo chat; a exigência de confirmação depende de uma interface externa.
- Outputs estruturados são orientados apenas por prompt e `json.loads`; não há schema imposto ao provider, validação forte, remoção de cercas Markdown ou garantia de campos obrigatórios. A criação de arquivos exige chamada explícita a `execute_structured_result()`.
- O caminho padrão de prompts, sessões e usage é absoluto e específico de Windows (`C:\IA\...`).
- O carregamento de `.env` ocorre ao importar `router`, não de forma uniforme em todos os módulos chamados diretamente.
- Modelos e `max_tokens` variam entre operações textuais e documentais; os defaults podem não existir na conta/API usada e não há camada comum de configuração.
- Batch individual é sequencial e usa o nome do arquivo como chave; nomes repetidos sobrescrevem resultados.
- `collect_files()` não é recursivo.
- PDF não executa OCR local: páginas consideradas escaneadas são renderizadas e delegadas ao provider multimodal. Imagens incorporadas podem repetir recursos por `xref`.
- A estimativa preflight usa caracteres/4 e bytes brutos; não modela custo de imagem ou limites específicos de cada provider.
- Usage é append-only, não tem locking, tolerância a CSV inválido ou detalhamento de tokens cached/thought para todos os providers.
- O chat reenvia documentos e todo o contexto textual reconstruído a cada turno. A mensagem do assistente só entra no histórico quando `StructuredResult.message` não está vazio; outputs não são memorizados diretamente.
- A compactação não é automática em `chat()`: `summarize_session()` precisa ser coordenado externamente e gera uma chamada adicional. Até isso ocorrer, mensagens antigas ficam em `pending_summary` e não entram no prompt conversacional.
- Sessões persistem `input_path`, mensagens e resumo, mas não o conteúdo dos documentos; a restauração requer que o chamador recarregue e forneça os documentos. Não há versionamento/migração do JSON nem API única de “carregar sessão completa”.
- A troca de provider preserva contexto porque o contexto é texto local reenviado, não porque IDs/estado remoto sejam migrados.
- Dentro do repositório `C:\IA\api`, não há CLI ou aplicação empacotada, tratamento transversal de retry/timeout/rate limit, cobertura automatizada ampla ou documentação de uso no `README.md` (atualmente vazio). Esta constatação não abrange possíveis interfaces ou orquestrações existentes no restante do ambiente `C:\IA`.

## Decisões arquiteturais importantes

- `DocumentContent` é a representação canônica entre readers, batch e providers.
- Providers são adaptadores diretos e stateless; contexto conversacional e persistência ficam locais.
- Tabelas viram texto via `to_text()` para o modelo; imagens permanecem binárias e são enviadas como partes multimodais.
- O batch consolidado cria um documento virtual; o individual faz uma chamada por documento.
- Resposta estruturada descreve intenção de saída. Parsing e escrita em disco são etapas separadas, e filenames são reduzidos ao basename antes da escrita.
- Memória usa duas camadas: resumo de mensagens antigas e janela recente literal. A compactação é uma ação explícita e contabilizada como chamada de API.
- Limites são guardrails locais configuráveis, não limites descobertos dinamicamente nos providers.

## Próxima etapa: robustez e organização

1. Expandir a suíte unitária offline com fixtures e mocks para os demais readers, serialização multimodal, roteamento, batch, structured outputs, exporters, preflight, usage, chat e sessões.
2. Organizar os testes manuais de provider para que não sejam coletados acidentalmente como testes automatizados nem façam chamadas externas sem intenção explícita.
3. Integrar preflight de modo explícito aos fluxos de alto nível, mantendo confirmação na camada de interface.
4. Centralizar configuração, caminhos, modelos e parâmetros de provider; remover defaults dependentes da máquina.
5. Definir contratos e validação mais fortes para respostas estruturadas e sessões persistidas.
6. Documentar uma API pública estável e exemplos no `README.md` antes de adicionar novas funcionalidades.
