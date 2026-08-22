# Arquitetura do ambiente completo

Este documento registra a arquitetura atual do ambiente `C:\IA` como um
sistema completo. Ele complementa, sem substituir:

- `PROJECT_STATE.md`, que registra o estado operacional conhecido do projeto
  `ai-engine`;
- `ARCHITECTURE.md`, que descreve tecnicamente os módulos existentes em
  `src/ai_engine`.

O escopo aqui é a relação entre a aplicação interativa, a biblioteca, os
scripts auxiliares e as áreas de entrada, saída, prompts e dados. O documento
não registra conteúdo pessoal, valores de usage, credenciais ou secrets.

## Visão geral

O ambiente está organizado em duas partes executáveis principais:

- `C:\IA\0_Scripts\ia_interativa.py` é a aplicação/interface principal atual.
  Ela recebe comandos do usuário e coordena documentos, sessões, preflight,
  providers, usage e criação de arquivos.
- `C:\IA\api` contém o projeto `ai-engine`, uma biblioteca Python reutilizável
  responsável por leitura de documentos, workflows, conversa, providers,
  respostas estruturadas, actions, exporters, limites e persistência.

Os demais diretórios de `C:\IA` armazenam documentos do usuário, entradas,
saídas, templates e estado operacional, ou reservam espaço para usos futuros.

## Mapa dos diretórios principais

```text
C:\IA
├── 0_Scripts\       aplicação atual, ferramentas e scripts manuais
├── 1_Projetos\      documentos organizados por projeto ou domínio
├── 2_Entrada\       arquivos selecionados para processamento
├── 3_Saída\         arquivos produzidos pela aplicação e por scripts
├── 4_Prompts\       templates de prompt reutilizáveis
├── 5_Modelos\       área reservada, atualmente vazia
├── 6_Dados\         sessões persistidas e registros de usage
├── 7_Temporario\    estrutura temporária reservada, atualmente vazia
└── api\              biblioteca Python ai-engine, documentação e testes
```

### `0_Scripts`

Contém a interface interativa atual e executáveis auxiliares. Não é parte do
pacote `ai_engine`; seus arquivos são consumidores externos da biblioteca.

`ia_interativa.py` é o ponto de entrada operacional principal. Os outros
scripts são ferramentas, protótipos, testes manuais ou implementações antigas.

### `1_Projetos`

Área documental organizada por domínios como projetos pessoais e de trabalho.
Na arquitetura auditada, não existe referência direta a essa pasta no engine
ou na interface principal. Um documento daqui só participa do fluxo se for
fornecido explicitamente como caminho de entrada ou copiado/selecionado por
outro processo externo.

Não é armazenamento interno do engine.

### `2_Entrada`

Área convencional de entrada. Contém exemplos de documentos, planilhas,
imagens e PDFs compatíveis com os readers do engine.

O default atual de `ia_interativa.py` é
`C:\IA\2_Entrada\batch_teste`, mas a interface permite que o usuário informe
outro arquivo ou diretório. O engine recebe um caminho e não depende
diretamente do nome `2_Entrada`.

### `3_Saída`

Destino convencional dos arquivos gerados. `ia_interativa.py` envia para essa
pasta os outputs descritos por respostas estruturadas. Alguns scripts manuais
usam subdiretórios próprios, como `actions_teste` e `teste_exporters`.

O engine não fixa `3_Saída`: actions e exporters recebem o diretório ou caminho
de destino do chamador. O conhecimento desse diretório pertence atualmente à
camada de aplicação e aos scripts externos.

### `4_Prompts`

Contém templates Markdown reutilizáveis para análise, comparação e resumo. O
módulo `ai_engine.prompts` procura templates nessa pasta por default, e os
workflows podem combiná-los com uma instrução específica do usuário.

A conversa normal de `ia_interativa.py` não seleciona esses templates. Ela usa
a mensagem livre do usuário, o contexto da sessão e as instruções estruturadas
internas do engine. Portanto, `4_Prompts` participa apenas de fluxos que pedem
explicitamente um `prompt_template`, inclusive alguns scripts manuais.

### `5_Modelos`

Área atualmente vazia e sem referências no código auditado. Os modelos de
Gemini, OpenAI e Anthropic usados pelos adapters são serviços remotos
configurados fora dessa pasta; não existem modelos locais integrados ao fluxo
atual.

### `6_Dados`

Armazena estado operacional local:

- `sessions\`: arquivos JSON com nome, provider, caminho de entrada, memória
  resumida, parâmetros de memória, mensagens recentes e mensagens pendentes de
  compactação;
- `usage\`: CSV append-only com telemetria reportada pelos providers.

Sessões não armazenam os documentos originais. Elas persistem `input_path`, e
a interface precisa reler os documentos ao restaurar uma conversa. Se o
caminho deixar de existir, `ia_interativa.py` pede uma nova localização.

### `7_Temporario`

Possui diretórios reservados para bancos, cache, configurações e índices, mas
não contém arquivos e não participa do fluxo auditado.

### `api`

É o projeto da biblioteca `ai-engine`. `src/ai_engine` contém o código
reutilizável e `tests` contém a suíte offline e os smoke tests reais separados.
O repositório não contém atualmente uma CLI empacotada; a aplicação principal
permanece em `0_Scripts`.

## Separação de responsabilidades

| Área | Responsabilidade atual | Localização principal |
|---|---|---|
| Aplicação/interface | Menus, input humano, confirmação, coordenação de sessão, tratamento de erros e escolha de destinos | `0_Scripts\ia_interativa.py` |
| Biblioteca/engine | Modelos documentais, readers, batch, workflows, chat, providers, parsing, actions, exporters e persistência | `api\src\ai_engine` |
| Entrada | Documentos selecionados para processamento | `2_Entrada` ou qualquer caminho fornecido pelo usuário |
| Saída | Resultados gerados e artefatos de testes manuais | `3_Saída` |
| Prompts | Templates editáveis e instruções internas de sistema | `4_Prompts` e módulos de prompt do engine |
| Dados operacionais | Sessões e telemetria de uso | `6_Dados` |
| Dados do usuário | Documentos e materiais organizados por projeto | `1_Projetos` e arquivos fornecidos como entrada |
| Desenvolvimento | Scripts manuais, suíte offline e smoke tests isolados | `0_Scripts\testar_*`, `api\tests` |

## Fluxo completo do sistema

```text
Usuário
  |
  v
0_Scripts\ia_interativa.py
  |-- escolhe provider e caminho de entrada
  |-- carrega ou restaura uma sessão
  |-- coordena preflight e confirmação humana
  |-- mede usage antes/depois das operações
  |-- coordena compactação explícita da memória
  |
  +--> 2_Entrada ou outro caminho
  |      |
  |      v
  |    ai_engine.workflow/readers
  |      |
  |      v
  |    DocumentContent[]
  |
  v
ai_engine.chat/workflow
  |-- contexto da sessão
  |-- instrução livre
  |-- template opcional de 4_Prompts
  |-- modo individual ou consolidado
  |
  +-- caminho documental/multimodal
  |     workflows/documentos
  |       |
  |       v
  |     ask_document()
  |       |
  |       v
  |     multimodal.py
  |       |
  |       v
  |     adaptador do provider
  |
  +-- caminho textual, por exemplo compactação da memória
        ask_ai()
          |
          v
        router.py
          |
          v
        adaptador do provider
          |
          v
providers: Gemini | OpenAI | Anthropic
  |                         |
  |                         +--> 6_Dados\usage\api_usage.csv
  v
resposta textual ou StructuredResult
  |                         |
  |                         +--> estado textual da conversa
  |                               |
  |                               v
  |                          6_Dados\sessions\*.json
  |
  +--> mensagem exibida ao usuário
  |
  +--> ai_engine.actions/exporters
          |
          v
        3_Saída\*
```

O caminho textual usado na compactação chama `ask_ai()`, que passa por
`router.py`. O caminho documental usa os workflows estruturados,
`ask_document()` e `multimodal.py`. Em ambos os casos, os adapters de provider
são stateless; a continuidade da conversa existe porque o contexto local é
reconstruído e reenviado.

## Papel atual de `ia_interativa.py`

`ia_interativa.py` é a camada de aplicação. Ela implementa:

- criação, seleção, restauração, salvamento e exclusão de sessões;
- escolha e troca de provider;
- seleção de arquivo ou diretório de entrada;
- recuperação de caminhos de sessão que foram movidos;
- carregamento dos documentos por meio do engine;
- preflight obrigatório antes da requisição principal;
- confirmação separada antes da compactação de memória;
- comandos interativos `sair`, `limpar`, `uso`, `provider` e `salvar`;
- autosave depois de mudanças relevantes e turnos bem-sucedidos;
- apresentação da resposta;
- execução dos arquivos pedidos em respostas estruturadas;
- resumo do consumo registrado em cada operação;
- tratamento básico de falhas, incluindo identificação textual de erros de
  quota ou rate limit.

A interface não implementa readers, adapters de provider ou exporters. Ela os
coordena por meio de `ai_engine`.

## Fronteira entre a interface e o engine

A fronteira conceitual atual é:

```text
ia_interativa.py
  fornece: decisões do usuário, confirmação, paths e apresentação
  consome:  documentos, sessão, chat, preflight, usage e actions
                         |
                         v
ai_engine
  fornece:  operações reutilizáveis e objetos de domínio
  não deve decidir: menus, confirmação automática, pasta de entrada ou destino
```

Na implementação atual, a fronteira pública ainda não está completa.
`ia_interativa.py` usa tanto símbolos reexportados por `ai_engine.__init__`
quanto módulos internos:

- `ai_engine.actions`;
- `ai_engine.chat`;
- `ai_engine.limits`;
- `ai_engine.usage`;
- `ai_engine.workflow`.

Isso não impede o funcionamento atual, mas acopla a aplicação à organização
interna do pacote. O preflight permanecer na interface é uma decisão coerente:
o engine calcula o relatório, enquanto a camada humana decide se autoriza a
chamada.

## Inventário resumido de `0_Scripts`

### Interface atual

- `ia_interativa.py`: aplicação principal multi-provider, com documentos,
  sessões, memória, preflight, usage e criação de outputs.

### Ferramentas úteis

- `ver_uso_api.py`: visualização manual de usage agrupado por provider. Lê
  diretamente o mesmo CSV usado pelo engine.

### Desenvolvimento e testes manuais

- `testar_actions.py`: workflow estruturado e geração de arquivos;
- `testar_batch.py`: processamento individual/consolidado e template salvo;
- `testar_docx_reader.py`: inspeção do reader DOCX;
- `testar_exporters.py`: geração manual dos formatos suportados;
- `testar_image_reader.py`: inspeção do reader de imagem;
- `testar_multimodal.py`: chamada multimodal real;
- `testar_pdf_reader.py`: inspeção do reader PDF;
- `testar_preflight.py`: relatório e confirmação manual de preflight;
- `testar_reader.py`: dispatch entre formatos;
- `testar_sessao.py`: persistência e restauração manual de sessão;
- `testar_xlsx_reader.py`: inspeção do reader XLSX.

Esses scripts são harnesses manuais. Eles não substituem a suíte padrão de
testes offline do projeto. Alguns fariam chamadas reais ou gravariam arquivos
se fossem executados.

### Legado

- `testar_chat.py`: interface de chat anterior e mais simples, parcialmente
  substituída por `ia_interativa.py`;
- `teste_ia.py`: smoke test antigo de acesso ao Gemini;
- `resumir_docx.py` e `resumir_texto.py`: fluxos diretos de
  reader -> prompt inline -> provider -> DOCX;
- `Criar_relatorio.py`, `Fazer_docx_ai.py` e `Fazer_docx_python.py`: três
  cópias idênticas de um gerador DOCX simples. Apesar do nome,
  `Fazer_docx_ai.py` não chama um provider.

A classificação registra a função aparente atual. Não implica exclusão nem
autoriza mudança nesses arquivos.

## Dependências de paths

### Defaults absolutos no engine

| Módulo | Default atual |
|---|---|
| `ai_engine.prompts` | `C:\IA\4_Prompts` |
| `ai_engine.sessions` | `C:\IA\6_Dados\sessions` |
| `ai_engine.usage` | `C:\IA\6_Dados\usage` |

Esses defaults tornam a biblioteca funcional no ambiente atual, mas ligam seu
comportamento padrão à estrutura Windows de `C:\IA`.

### Paths da aplicação e scripts

- `ia_interativa.py` define `C:\IA` como raiz, usa
  `2_Entrada\batch_teste` como entrada default e `3_Saída` como destino;
- os scripts de resumo apontam para arquivos específicos em `2_Entrada` e
  destinos específicos em `3_Saída`;
- os scripts `testar_*` usam fixtures específicas em `2_Entrada` e, quando
  escrevem, subdiretórios de `3_Saída`;
- os três geradores DOCX apontam diretamente para `C:\IA\3_Saída`;
- `ver_uso_api.py` aponta diretamente para o CSV de `6_Dados\usage`;
- sessões persistidas dependem do `input_path` salvo continuar acessível.

Não há dependência de código identificada para `1_Projetos`, `5_Modelos` ou
`7_Temporario`.

## Duplicações e dívidas técnicas principais

### Duplicações

- três scripts são cópias idênticas do mesmo gerador DOCX;
- `testar_batch.py` e `testar_preflight.py` repetem a lista de extensões e a
  coleta já existente em `ai_engine.workflow`;
- `ver_uso_api.py` reimplementa parte da leitura e agregação de usage, embora
  acrescente o agrupamento por provider;
- os scripts de resumo montam manualmente um fluxo já representado pelos
  readers, workflows e exporters do engine;
- `testar_chat.py` sobrepõe parte da responsabilidade da interface principal.

### Dívidas técnicas e acoplamentos

- paths absolutos específicos de `C:\IA` aparecem no engine e na maioria dos
  scripts externos;
- a interface principal concentra menus, coordenação, persistência,
  telemetria, tratamento de erros e actions em um único arquivo;
- a interface importa módulos internos em vez de depender apenas de uma API
  pública estável;
- vários scripts executam trabalho no topo do módulo e não são componentes
  seguros para importação como biblioteca;
- sessões não têm versionamento de schema e dependem de caminhos externos;
- usage é append-only e não possui locking ou tolerância ampla a CSV inválido;
- o preflight é aproximado e coordenado externamente, não integrado aos
  workflows de alto nível;
- prompts e configurações estão distribuídos entre Markdown, constantes
  Python, variáveis de ambiente e literais nos scripts;
- o modo pelo qual scripts fora de `api` tornam `ai_engine` importável é uma
  dependência operacional que deve permanecer documentada.

Esses itens descrevem o estado existente. Preferências de nomes ou de
organização visual, isoladamente, não são bugs.

## Áreas atualmente fora do fluxo

- `1_Projetos`: repositório documental do usuário, sem integração direta;
- `5_Modelos`: vazio e sem integração com modelos locais;
- `7_Temporario`: diretórios vazios e sem consumidores identificados.

Essas áreas não devem ser movidas ou redefinidas antes de haver um caso de uso
e um contrato explícito com a aplicação.

## Estratégia de evolução segura

Nenhum arquivo precisa ser movido para iniciar a evolução arquitetural. A
ordem segura é:

1. preservar como baseline a suíte offline existente e o comportamento de
   `ia_interativa.py`;
2. documentar o comando e o ambiente usados para tornar `ai_engine` importável
   pelos scripts externos;
3. reconhecer formalmente `ia_interativa.py` como aplicação e `api` como
   biblioteca, sem reorganização física imediata;
4. criar futuramente uma configuração central de paths, mantendo inicialmente
   os mesmos defaults de `C:\IA`;
5. estabilizar uma API pública que cubra os serviços usados pela interface,
   reduzindo imports de módulos internos;
6. separar gradualmente as responsabilidades internas da interface, mantendo
   seu ponto de entrada e comportamento observável;
7. permitir configuração compatível de prompts, sessions e usage antes de
   considerar qualquer mudança de diretório;
8. tratar scripts manuais e legados somente depois da estabilização da
   aplicação principal, decidindo quais serão exemplos, ferramentas ou
   artefatos históricos;
9. abordar `1_Projetos`, `5_Modelos` e `7_Temporario` por último, pois não
   participam do fluxo atual;
10. revisar separadamente a política de armazenamento de configurações,
    secrets e dados pessoais, sem incorporar seus valores à documentação.

Essa sequência mantém a estrutura atual válida enquanto reduz o acoplamento
antes de qualquer movimentação física de arquivos.
