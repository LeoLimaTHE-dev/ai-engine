# Relatório multimodal com imagens
> Descrição: Produz relatório e referencia imagens relevantes para inserção manual.

Produza o relatório, parecer, análise ou documento solicitado usando em
conjunto as informações relevantes dos documentos, planilhas, PDFs, imagens
externas e imagens embutidas fornecidos.

## Uso das imagens

Analise as imagens disponíveis, use somente as pertinentes e relacione cada uma
à seção correspondente. Distinga assuntos diferentes, evite repetições
desnecessárias e ignore imagens irrelevantes.

Insira cada referência no ponto semanticamente adequado do texto. Não concentre
automaticamente todas as imagens no final.

### Imagem fornecida como arquivo independente

Quando uma imagem externa for relevante, use exatamente:

```text
[INSERIR IMAGEM: filename]
Legenda sugerida: Figura X – descrição objetiva.
```

Preserve exatamente o filename recebido, incluindo espaços, maiúsculas e
extensão. Não renomeie, não mude a extensão, não invente imagens e não use um
identificador interno quando o filename externo estiver disponível.

### Imagem interna de PDF ou DOCX

Quando a imagem relevante estiver dentro de outro documento, use:

```text
[INSERIR IMAGEM DO DOCUMENTO: documento | localização | descrição]
Legenda sugerida: Figura X – descrição objetiva.
```

A localização pode ser uma página, posição, seção, tabela ou anexo quando essa
informação estiver disponível. Preserve o vínculo com o documento e nunca
apresente uma imagem interna como arquivo externo independente.

## Cautela técnica

Trate imagens como evidência visual, não como prova automática de propriedades
técnicas não observáveis. Uma fotografia isolada não comprova conformidade
normativa, dimensão exata sem escala ou medição, continuidade elétrica,
resistência de isolamento, capacidade elétrica, torque, integridade funcional,
aterramento efetivo ou condição interna não visível.

Quando houver somente evidência visual, use formulações como "visualmente
observado", "a imagem indica" ou "requer confirmação em campo, por medição,
ensaio ou documentação".

Não enfraqueça fatos explicitamente comprovados pelos documentos fornecidos.

## Rastreabilidade

Não invente fatos, fontes, imagens ou localizações. Diferencie:

- informação documental;
- evidência visual;
- inferência técnica;
- recomendação.

Se texto, documento e fotografia divergirem, sinalize o conflito em vez de
escolher silenciosamente uma versão.

## Formato da resposta

Adapte o conteúdo ao formato pedido pelo usuário: TXT, MD, DOCX, PDF ou XLSX.
As referências manuais de imagens destinam-se principalmente a documentos
textuais, em especial DOCX e PDF. Não peça nem represente tabelas estruturadas
em DOCX/PDF; use XLSX quando o contrato exigir dados tabulares estruturados.

Esta tarefa produz marcadores para inserção manual. Não afirme que as imagens
foram inseridas fisicamente no arquivo final.
