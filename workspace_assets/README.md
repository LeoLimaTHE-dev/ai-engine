# Assets operacionais versionados

## Finalidade

Esta pasta guarda cópias versionadas dos assets operacionais externos ao
repositório principal. Ela representa os assets da release e permite reconstruir
o workspace futuramente.

Versão operacional, usada no cotidiano:

```text
C:\IA\Iniciar IA.bat
C:\IA\4_Prompts
```

Snapshot versionado:

```text
C:\IA\api\workspace_assets
```

## Importante

- O engine não deve usar `workspace_assets\prompts` automaticamente.
- Não altere paths de produção para apontar para esta pasta.
- `workspace_assets` não é a pasta operacional do sistema.
- A cópia existe somente para versionamento e reconstrução.
- Antes de uma release, sincronize conscientemente mudanças feitas nos assets
  operacionais com este snapshot.
- Não copie `.env`, `Key.txt`, API keys, sessões, usage, outputs, arquivos de
  entrada, temporários ou `.venv` para esta pasta.

## Restauração conceitual

Em uma reconstrução futura do workspace, os arquivos podem ser copiados assim:

```text
workspace_assets\Iniciar IA.bat
-> C:\IA\Iniciar IA.bat

workspace_assets\prompts\*
-> C:\IA\4_Prompts\
```

Esta seção é somente documentação. Não existe script automático de restauração
nesta pasta.
