# Roblox Account Manager Linux

Gerenciador de contas Roblox para Linux, com suporte ao [Sober](https://sober.vinegarhq.org/) e ao Mocktail. Interface gráfica em Qt, cofre criptografado para as senhas, perfis separados por conta e importação/exportação no formato `usuario:senha`.

Projeto independente, sem relação com a Roblox Corporation, com o Sober ou com o Mocktail.

## Requisitos

- Linux
- Python 3.10 ou superior
- Sober (Flatpak `org.vinegarhq.Sober`) ou Mocktail

## Instalação

```sh
git clone https://github.com/SEU_USUARIO/RobloxAccountManagerLinux.git
cd RobloxAccountManagerLinux
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Uso

```sh
.venv/bin/python main.py
```

Na primeira execução o programa pede uma senha mestra e cria o cofre. A senha mestra não é guardada em lugar nenhum: se for perdida, o cofre não pode ser recuperado.

Também há comandos para o terminal:

```sh
.venv/bin/python main.py list
.venv/bin/python main.py add NomeDaConta
.venv/bin/python main.py remove NomeDaConta
.venv/bin/python main.py import contas.txt
.venv/bin/python main.py export contas.txt
.venv/bin/python main.py launch NomeDaConta --place 123456
.venv/bin/python main.py version
```

## Como funciona

Cada conta tem um perfil isolado (pastas XDG próprias). Você faz o login uma vez com "Abrir para login" e depois entra no jogo com várias contas ao mesmo tempo, informando o ID do jogo.

Em Configurações é possível desligar os perfis separados. Nesse modo o programa troca a sessão do Sober: guarda a sessão da conta ativa, restaura a da conta escolhida e abre o cliente. As sessões ficam criptografadas com a chave do cofre. Nesse modo só uma conta fica aberta por vez e o Sober precisa estar fechado.

Os arquivos de sessão considerados ficam em `SESSION_FILES`, em `src/config.py`, relativos a `~/.var/app/org.vinegarhq.Sober`.

## Importar e exportar

Uma conta por linha:

```
usuario1:senha1
usuario2:senha2
usuario3:
```

- Contas sem senha (`usuario3:`) são aceitas.
- A senha pode conter `:`; só o primeiro separa o usuário.
- Linhas em branco e o cabeçalho `Usuario:Senha` são ignorados.
- Linhas inválidas são ignoradas e aparecem no terminal com o número da linha.
- Contas que já existem são mantidas, a menos que você escolha substituir. Contas existentes sem senha recebem a senha do arquivo.
- Usuários aceitos: 3 a 20 caracteres, letras, números e `_`.

Na interface: Arquivo > Importar contas de um arquivo, Importar colando texto e Exportar. A exportação pede a senha mestra de novo e grava o arquivo com permissão `600`. Ele contém as senhas em texto puro; apague-o depois de usar.

## Mensagens

Tudo o que acontece (cofre desbloqueado, importação, perfil aberto, erros) aparece no painel da janela, no terminal e em `app.log`. Senhas nunca são registradas.

## Onde ficam os dados

`~/.config/gerenciador-contas-roblox/` (ou o caminho absoluto definido em `GCR_DIR`):

| Item | Conteúdo |
| --- | --- |
| `cofre.json` | contas e senhas, criptografadas |
| `config.json` | tema, idioma, cliente e demais preferências |
| `perfis/` | uma pasta por conta |
| `sessoes/` | sessões criptografadas (modo sem perfis separados) |
| `exportacoes/` | exportações padrão |
| `app.log` | registro de eventos |

Nada fica dentro da pasta do projeto, então não há risco de enviar dados pessoais ao repositório.

Se existir um `contas.json` da versão anterior, as contas são migradas para o cofre na criação dele, mantendo os perfis já logados.

## Segurança

- Cofre em Fernet (AES-128-CBC com HMAC-SHA256), chave derivada da senha mestra com scrypt. Trocar a senha mestra reembrulha a chave sem recriptografar os dados.
- Espera crescente após três senhas erradas e bloqueio automático por inatividade.
- Arquivos gravados de forma atômica com permissão `600`; pastas com `700`.
- O programa se recusa a rodar como root.
- Nenhum comando passa por shell. Comandos personalizados ficam desligados por padrão e interpretadores e shells são recusados.
- Tudo o que é lido do disco é validado; o comando dos clientes predefinidos nunca vem do arquivo de configuração.
- Identificadores de conta e do jogo são validados antes de virarem caminhos ou links. Links simbólicos na pasta do Sober são recusados.
- A senha copiada é apagada da área de transferência após 30 segundos.
- Importação limitada a 1 MB e 10.000 linhas.
- Não usa a internet.

Os logins dos perfis separados ficam nas pastas do próprio cliente e não são criptografados por este programa. Use criptografia de disco para protegê-los.

Vulnerabilidades podem ser reportadas abrindo uma issue sem detalhes sensíveis ou contatando o autor diretamente.

## Idiomas

Português, inglês, espanhol, francês e alemão. Para adicionar outro, copie um bloco em `src/idiomas.py` e registre o código em `LANG_NAMES`; os testes conferem se todas as chaves existem.

## Atualização

```sh
./update.sh
```

## Testes

```sh
python3 -m unittest discover -s tests -t .
```

## Licença

MIT. Veja o arquivo `LICENSE`.
