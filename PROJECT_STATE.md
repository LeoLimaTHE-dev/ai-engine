# Estado do projeto

> Instrução para futuros agentes: leia este arquivo **e confira o código real e os testes atuais antes de fazer qualquer alteração**. Este documento é um mapa operacional, não substitui a implementação. Atualize-o quando o estado do projeto mudar.

## Escopo deste documento

Este estado cobre o engine e a implementação versionada da aplicação em
`C:\IA\api`. O ambiente completo também possui scripts e dados externos,
descritos em `SYSTEM_ARCHITECTURE.md`. O arquivo
`C:\IA\0_Scripts\ia_interativa.py` é atualmente apenas um launcher local para
a aplicação versionada.

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
- Configuração imutável de paths operacionais (`OperationalPaths`) derivados de
  uma única raiz; `IA_ROOT` pode substituir a raiz do processo e o fallback
  compatível permanece `C:\IA`.
- Prompts, sessões e usage resolvem seus defaults por meio de `get_paths()` no
  momento da chamada; argumentos explícitos continuam prevalecendo.
- Aplicação interativa oficial versionada em `application/ia_interativa.py`,
  com launcher local fino em `C:\IA\0_Scripts\ia_interativa.py`.
- Suíte automatizada offline com pytest cobrindo models/readers; batch/workflow/prompts; structured outputs/actions/exporters; limits/usage; chat/memória/sessões; e routing/multimodal/images/adapters de providers com clientes mockados.

## Validação existente

- Os arquivos Python de `src/` e `tests/` foram analisados pelo parser AST na revisão de 22/08/2026 sem erro de sintaxe.
- A coleta padrão do pytest está restrita por `pyproject.toml` a arquivos `test_*_offline.py`; `uv run pytest` executa atualmente os 210 testes da suíte offline, todos passando. A cobertura automatizada inclui:
  - models e readers, com fixtures locais para texto, formatos tabulares, DOCX, PDF e imagens;
  - batch, workflow e prompts;
  - structured outputs, actions e exporters;
  - limits/preflight e usage tracking;
  - chat, memória compactada e sessões persistentes;
  - configuração de paths, consumidores internos e defaults da aplicação;
  - routing, multimodal, normalização de imagens e adapters de OpenAI, Gemini e Anthropic com clientes mockados.
- Os quatro smoke tests reais foram movidos para `tests/smoke/` e usam nomes fora do padrão de coleta automática. Todos protegem a execução em `if __name__ == "__main__":`; importá-los não dispara chamadas de rede, e eles não são executados pela coleta padrão.
- `tests/smoke/smoke_ai_engine.py` cobre manualmente o caminho público `ai_engine.ask_ai()`; os outros módulos smoke exercitam diretamente OpenAI, Gemini e Anthropic.
- Os smoke tests reais de provider não fazem parte da suíte offline e não foram executados nesta revisão, para não consumir APIs. A cobertura dos adapters na suíte automatizada valida payloads, roteamento, usage e retornos com mocks; ela não valida credenciais, rede, disponibilidade, modelos ou comportamento real dos serviços externos.

Assim, “implementado” não implica cobertura integral: os 210 testes exercitam os contratos listados acima, mas não todos os caminhos possíveis do engine. O histórico Git registra checkpoints do projeto, mas commits não substituem testes reproduzíveis.

## Limitações e pendências conhecidas

- Preflight e confirmação existem, mas não são chamados pelos workflows nem pelo chat; a exigência de confirmação depende de uma interface externa.
- Outputs estruturados são orientados apenas por prompt e `json.loads`; não há schema imposto ao provider, validação forte, remoção de cercas Markdown ou garantia de campos obrigatórios. A criação de arquivos exige chamada explícita a `execute_structured_result()`.
- Scripts auxiliares e legados externos ainda possuem paths próprios e não
  foram todos migrados para `ai_engine.paths`.
- `IA_ROOT` é lida de `os.environ` por `ai_engine.paths`; esse módulo não carrega
  `.env`. O carregamento de `.env` continua sendo uma responsabilidade separada.
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
- Dentro do repositório existe uma aplicação versionada, mas ainda não há entry
  point de console empacotado, tratamento transversal de retry/timeout/rate
  limit, cobertura automatizada integral ou documentação de uso no `README.md`
  (atualmente vazio).

## Decisões arquiteturais importantes

- `DocumentContent` é a representação canônica entre readers, batch e providers.
- Providers são adaptadores diretos e stateless; contexto conversacional e persistência ficam locais.
- Tabelas viram texto via `to_text()` para o modelo; imagens permanecem binárias e são enviadas como partes multimodais.
- O batch consolidado cria um documento virtual; o individual faz uma chamada por documento.
- Resposta estruturada descreve intenção de saída. Parsing e escrita em disco são etapas separadas, e filenames são reduzidos ao basename antes da escrita.
- Memória usa duas camadas: resumo de mensagens antigas e janela recente literal. A compactação é uma ação explícita e contabilizada como chamada de API.
- Limites são guardrails locais configuráveis, não limites descobertos dinamicamente nos providers.
- Paths operacionais são separados da resolução do pacote Python:
  `ai_engine.paths` não manipula `sys.path`, `PYTHONPATH`, `.venv`, uv ou a
  localização de `api`.
- A implementação oficial da interface reside em `application/ia_interativa.py`;
  o script externo apenas delega sua execução com `runpy.run_path()`.

## Próxima etapa: robustez e organização

1. Organizar e continuar expandindo a suíte offline a partir dos 210 testes atuais, priorizando contratos ainda não cobertos e manutenção clara entre camadas.
2. Integrar preflight de modo explícito aos fluxos de alto nível, mantendo confirmação na camada de interface.
3. Migrar gradualmente scripts auxiliares/legados para a configuração central,
   sem mover dados e sem misturar paths operacionais com importação do pacote.
4. Definir contratos e validação mais fortes para respostas estruturadas e sessões persistidas.
5. Documentar uma API pública estável e exemplos no `README.md` antes de adicionar novas funcionalidades.
