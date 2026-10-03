<div align="center">

# Roblox Account Manager for Linux

**Run multiple Roblox accounts on Linux. Built for Sober and Mocktail.**<br>
**Várias contas Roblox no Linux ao mesmo tempo. Feito para Sober e Mocktail.**

<br>

[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f?style=for-the-badge)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Platform: Linux](https://img.shields.io/badge/platform-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![GUI: Qt](https://img.shields.io/badge/GUI-Qt-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Works with Sober and Mocktail](https://img.shields.io/badge/works%20with-Sober%20%7C%20Mocktail-6C5CE7?style=for-the-badge)
<br>
[![GitHub stars](https://img.shields.io/github/stars/Kerneluxx/Roblox-Account-Manager-Linux?style=for-the-badge&color=f5c542)](https://github.com/Kerneluxx/Roblox-Account-Manager-Linux/stargazers)
[![Last commit](https://img.shields.io/github/last-commit/Kerneluxx/Roblox-Account-Manager-Linux?style=for-the-badge)](https://github.com/Kerneluxx/Roblox-Account-Manager-Linux/commits/main)
[![Issues](https://img.shields.io/github/issues/Kerneluxx/Roblox-Account-Manager-Linux?style=for-the-badge)](https://github.com/Kerneluxx/Roblox-Account-Manager-Linux/issues)

<br>

[🇺🇸 English](#english) &nbsp;•&nbsp; [🇧🇷 Português](#portugues)

</div>

<br>

<!--
Add a screenshot: save it as docs/screenshot.png and uncomment the block below.
<p align="center">
  <img src="docs/screenshot.png" alt="Roblox Account Manager for Linux: main window listing several accounts with Sober" width="820">
</p>
-->

**Roblox Account Manager for Linux** is a free, open-source alt manager to store, organize, and launch **multiple Roblox accounts on Linux**, including several at the same time. It works with **[Sober](https://sober.vinegarhq.org/)**, the unofficial Roblox client for Linux, and with **Mocktail**. Every account gets its own isolated profile, and credentials stay in an encrypted vault. It is a Linux-native alternative to Windows-only Roblox account managers.

**Roblox Account Manager para Linux** é um gerenciador de contas gratuito e de código aberto para guardar, organizar e abrir **várias contas Roblox no Linux**, inclusive ao mesmo tempo. Funciona com o **[Sober](https://sober.vinegarhq.org/)**, o cliente não oficial do Roblox para Linux, e com o **Mocktail**. Cada conta tem um perfil isolado, e as credenciais ficam em um cofre criptografado. É uma alternativa nativa para Linux aos gerenciadores de contas Roblox feitos só para Windows.

## ✨ Highlights / Destaques

| | English | Português |
| :-: | --- | --- |
| 🔐 | Encrypted password vault | Cofre de senhas criptografado |
| 👥 | Isolated profile per account | Perfil isolado por conta |
| 🚀 | Multi-instance: several accounts at once | Multi-instância: várias contas ao mesmo tempo |
| 📥 | `username:password` import/export | Importação/exportação `usuario:senha` |
| 🖥️ | Qt interface and command line | Interface Qt e linha de comando |
| 🌍 | 5 languages | 5 idiomas |
| 🚫 | No network connections | Sem conexões de rede |

> [!NOTE]
> Independent project, not affiliated with Roblox Corporation, Sober, or Mocktail.
> Projeto independente, sem vínculo com a Roblox Corporation, o Sober ou o Mocktail.

<br>

---

<br>

<details open>
<summary><h2 id="english">🇺🇸 English</h2></summary>

### 🎯 What it is for

- Run **multiple Roblox accounts on Linux** at the same time, each in its own profile.
- Switch between your main and alt accounts without logging out and back in.
- Keep credentials in an encrypted vault instead of a text file or a browser.
- Import and export account lists in the `username:password` format.
- Launch a specific game (place ID) with a chosen account from the GUI or the terminal.

It is not tied to a specific distribution: it runs wherever Python 3.10+ and Sober (Flatpak) or Mocktail are available.

### 📋 Requirements

- Linux
- Python 3.10+
- Sober (Flatpak `org.vinegarhq.Sober`) or Mocktail

### 📦 Installation

```sh
git clone https://github.com/Kerneluxx/Roblox-Account-Manager-Linux.git
cd Roblox-Account-Manager-Linux
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 🚀 Usage

```sh
.venv/bin/python main.py
```

On first run you are asked for a master password, which is used to create the vault. It is not stored anywhere; if it is lost, the vault cannot be recovered.

#### Command line

```sh
main.py list                                  # list accounts
main.py add AccountName                       # add an account
main.py remove AccountName                    # remove an account
main.py import accounts.txt                   # import accounts
main.py export accounts.txt                   # export accounts
main.py launch AccountName --place 123456     # launch a game with an account
main.py version
```

### ⚙️ How it works

Each account has an isolated profile with its own XDG directories. You log in once with "Open for login", and can then join a game with several accounts at the same time by providing the place ID.

In Settings, separate profiles can be turned off. In that mode the program swaps the Sober session: it saves the active account's session, restores the selected account's session, and launches the client. Sessions are encrypted with the vault key. Only one account can be open at a time, and Sober must be closed when switching.

The session files in use are listed in `SESSION_FILES` (`src/config.py`), relative to `~/.var/app/org.vinegarhq.Sober`.

### 🔄 Import and export

One account per line:

```
username1:password1
username2:password2
username3:
```

- Accounts without a password (`username3:`) are accepted.
- The password may contain `:`; only the first one separates the username.
- Blank lines and the `Usuario:Senha` header are ignored.
- Invalid lines are skipped and reported in the terminal with the line number.
- Existing accounts are kept unless you choose to replace them. Existing accounts without a password receive the password from the file.
- Valid usernames: 3 to 20 characters, letters, numbers, and `_`.
- Limit of 1 MB and 10,000 lines per file.

In the interface: **File > Import accounts from file**, **Import by pasting text**, and **Export**. Exporting requires the master password and writes the file with `600` permissions. The file contains plain-text passwords and should be deleted after use.

### 🗂️ Data and logs

Data is stored in `~/.config/gerenciador-contas-roblox/`, or in the absolute path set in `GCR_DIR`. Nothing is written inside the project directory.

| Item | Contents |
| --- | --- |
| `cofre.json` | Accounts and passwords, encrypted |
| `config.json` | Theme, language, client, and other preferences |
| `perfis/` | One directory per account |
| `sessoes/` | Encrypted sessions (separate profiles disabled) |
| `exportacoes/` | Default export destination |
| `app.log` | Event log |

Events are also shown in the window panel and in the terminal. Passwords are never logged.

If a `contas.json` from a previous version exists, its accounts are migrated into the vault when it is created, preserving profiles that are already logged in.

### 🛡️ Security

- Vault uses Fernet (AES-128-CBC + HMAC-SHA256), with a key derived from the master password via scrypt. Changing the master password re-wraps the key without re-encrypting the data.
- Increasing delay after three wrong passwords and automatic lock on inactivity.
- Atomic file writes with `600` permissions; directories use `700`.
- Running as root is refused.
- No command is run through a shell. Custom commands are disabled by default, and interpreters and shells are rejected.
- All data read from disk is validated. The command for predefined clients never comes from the configuration file.
- Account and place identifiers are validated before being used in paths or links. Symbolic links in the Sober directory are rejected.
- A copied password is cleared from the clipboard after 30 seconds.
- Makes no network connections.

> [!WARNING]
> Logins in separate profiles are stored in the client's own directories and are not encrypted by this program. Full-disk encryption is recommended.

To report a vulnerability, open an issue without sensitive details or contact the author directly.

### 🌍 Languages

Portuguese, English, Spanish, French, and German. To add a language, copy a block in `src/idiomas.py` and register the code in `LANG_NAMES`. The tests check that all keys are present.

### 🔧 Updating

```sh
./update.sh
```

### 🧪 Tests

```sh
python3 -m unittest discover -s tests -t .
```

### ❓ FAQ

#### Can I run multiple Roblox accounts at the same time on Linux?

Yes. With separate profiles enabled (the default), each account has its own isolated profile, so several accounts can be open at once. With separate profiles disabled, the program swaps the Sober session and only one account is open at a time.

#### Does Roblox run on Linux?

Roblox has no official Linux client. [Sober](https://sober.vinegarhq.org/), distributed as the Flatpak `org.vinegarhq.Sober`, is an unofficial client that fills that gap. This project manages accounts and profiles on top of Sober or Mocktail.

#### Is this the same as Roblox Account Manager for Windows?

No. This is an independent project written for Linux. It has no code or affiliation with Windows-only account managers.

#### Are my passwords safe?

Passwords are kept in a Fernet-encrypted vault with a key derived from your master password via scrypt, and the program never uses the network. Logins stored inside separate profiles are kept by the client itself and are not encrypted by this program, so full-disk encryption is recommended.

#### Can I get banned for using it?

The project only manages accounts, profiles, and sessions, and launches the client. Third-party clients and tools are outside Roblox's official support, though, so use them at your own risk and follow the Roblox Terms of Use.

#### Does it work on Windows or macOS?

No. It is Linux only.

#### How do I move my accounts from a text file?

Use the `username:password` format described in [Import and export](#-import-and-export), through the GUI or `main.py import accounts.txt`.

### 🤝 Contributing

Issues and pull requests are welcome. Run the test suite before submitting changes. If the project is useful to you, a ⭐ on the repository helps other Linux users find it.

</details>

<br>

<details open>
<summary><h2 id="portugues">🇧🇷 Português</h2></summary>

### 🎯 Para que serve

- Abrir **várias contas Roblox no Linux** ao mesmo tempo, cada uma em seu próprio perfil.
- Alternar entre a conta principal e as secundárias sem sair e entrar de novo.
- Guardar as credenciais em um cofre criptografado, em vez de um arquivo de texto ou do navegador.
- Importar e exportar listas de contas no formato `usuario:senha`.
- Abrir um jogo específico (ID do jogo) com a conta escolhida, pela interface ou pelo terminal.

Não depende de uma distribuição específica: roda onde houver Python 3.10+ e o Sober (Flatpak) ou o Mocktail.

### 📋 Requisitos

- Linux
- Python 3.10+
- Sober (Flatpak `org.vinegarhq.Sober`) ou Mocktail

### 📦 Instalação

```sh
git clone https://github.com/Kerneluxx/Roblox-Account-Manager-Linux.git
cd Roblox-Account-Manager-Linux
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 🚀 Uso

```sh
.venv/bin/python main.py
```

Na primeira execução é solicitada uma senha mestra, usada para criar o cofre. Ela não é armazenada em nenhum lugar; se for perdida, o cofre não pode ser recuperado.

#### Linha de comando

```sh
main.py list                                  # lista as contas
main.py add NomeDaConta                       # adiciona uma conta
main.py remove NomeDaConta                    # remove uma conta
main.py import contas.txt                     # importa contas
main.py export contas.txt                     # exporta contas
main.py launch NomeDaConta --place 123456     # abre um jogo com a conta
main.py version
```

### ⚙️ Funcionamento

Cada conta possui um perfil isolado, com diretórios XDG próprios. O login é feito uma vez em "Abrir para login", e depois é possível entrar em um jogo com várias contas simultaneamente, informando o ID do jogo.

Em Configurações, os perfis separados podem ser desativados. Nesse modo, o programa alterna a sessão do Sober: salva a sessão da conta ativa, restaura a da conta selecionada e abre o cliente. As sessões são criptografadas com a chave do cofre. Apenas uma conta fica aberta por vez, e o Sober deve estar fechado ao trocar.

Os arquivos de sessão considerados estão em `SESSION_FILES` (`src/config.py`), relativos a `~/.var/app/org.vinegarhq.Sober`.

### 🔄 Importação e exportação

Uma conta por linha:

```
usuario1:senha1
usuario2:senha2
usuario3:
```

- Contas sem senha (`usuario3:`) são aceitas.
- A senha pode conter `:`; apenas o primeiro separa o usuário.
- Linhas em branco e o cabeçalho `Usuario:Senha` são ignorados.
- Linhas inválidas são ignoradas e reportadas no terminal com o número da linha.
- Contas existentes são mantidas, a menos que a substituição seja escolhida. Contas existentes sem senha recebem a senha do arquivo.
- Usuários válidos: 3 a 20 caracteres, entre letras, números e `_`.
- Limite de 1 MB e 10.000 linhas por arquivo.

Na interface: **Arquivo > Importar contas de um arquivo**, **Importar colando texto** e **Exportar**. A exportação exige a senha mestra e grava o arquivo com permissão `600`. O arquivo contém as senhas em texto puro e deve ser apagado após o uso.

### 🗂️ Dados e logs

Os dados ficam em `~/.config/gerenciador-contas-roblox/`, ou no caminho absoluto definido em `GCR_DIR`. Nada é gravado dentro do diretório do projeto.

| Item | Conteúdo |
| --- | --- |
| `cofre.json` | Contas e senhas, criptografadas |
| `config.json` | Tema, idioma, cliente e demais preferências |
| `perfis/` | Um diretório por conta |
| `sessoes/` | Sessões criptografadas (modo sem perfis separados) |
| `exportacoes/` | Destino padrão das exportações |
| `app.log` | Registro de eventos |

Os eventos também aparecem no painel da janela e no terminal. Senhas nunca são registradas.

Se houver um `contas.json` de versões anteriores, as contas são migradas para o cofre na criação dele, preservando os perfis já logados.

### 🛡️ Segurança

- Cofre em Fernet (AES-128-CBC + HMAC-SHA256), com chave derivada da senha mestra via scrypt. A troca da senha mestra reencapsula a chave sem recriptografar os dados.
- Atraso crescente após três senhas incorretas e bloqueio automático por inatividade.
- Gravação atômica de arquivos com permissão `600`; diretórios com `700`.
- Execução como root é recusada.
- Nenhum comando é executado por shell. Comandos personalizados vêm desativados, e interpretadores e shells são recusados.
- Todo dado lido do disco é validado. O comando dos clientes predefinidos nunca vem do arquivo de configuração.
- Identificadores de conta e de jogo são validados antes de serem usados em caminhos ou links. Links simbólicos no diretório do Sober são recusados.
- A senha copiada é removida da área de transferência após 30 segundos.
- Não realiza conexões de rede.

> [!WARNING]
> Os logins dos perfis separados ficam nos diretórios do próprio cliente e não são criptografados por este programa. Recomenda-se criptografia de disco.

Para reportar vulnerabilidades, abra uma issue sem detalhes sensíveis ou entre em contato diretamente com o autor.

### 🌍 Idiomas

Português, inglês, espanhol, francês e alemão. Para adicionar um idioma, copie um bloco em `src/idiomas.py` e registre o código em `LANG_NAMES`. Os testes verificam se todas as chaves estão presentes.

### 🔧 Atualização

```sh
./update.sh
```

### 🧪 Testes

```sh
python3 -m unittest discover -s tests -t .
```

### ❓ Perguntas frequentes

#### Dá para abrir várias contas Roblox ao mesmo tempo no Linux?

Sim. Com os perfis separados ativados (padrão), cada conta tem seu próprio perfil isolado, então várias contas podem ficar abertas juntas. Com os perfis separados desativados, o programa alterna a sessão do Sober e apenas uma conta fica aberta por vez.

#### O Roblox funciona no Linux?

O Roblox não tem cliente oficial para Linux. O [Sober](https://sober.vinegarhq.org/), distribuído como o Flatpak `org.vinegarhq.Sober`, é um cliente não oficial que preenche essa lacuna. Este projeto gerencia contas e perfis em cima do Sober ou do Mocktail.

#### É o mesmo que o Roblox Account Manager do Windows?

Não. Este é um projeto independente, escrito para Linux, sem código nem vínculo com gerenciadores de contas feitos só para Windows.

#### Minhas senhas ficam seguras?

As senhas ficam em um cofre criptografado com Fernet, com chave derivada da senha mestra via scrypt, e o programa nunca usa a rede. Os logins guardados dentro dos perfis separados ficam com o próprio cliente e não são criptografados por este programa, por isso recomenda-se criptografia de disco.

#### Posso ser banido por usar?

O projeto apenas gerencia contas, perfis e sessões e abre o cliente. Mesmo assim, clientes e ferramentas de terceiros estão fora do suporte oficial do Roblox, então use por sua conta e risco e siga os Termos de Uso do Roblox.

#### Funciona no Windows ou no macOS?

Não. É somente para Linux.

#### Como passo minhas contas de um arquivo de texto?

Use o formato `usuario:senha` descrito em [Importação e exportação](#-importação-e-exportação), pela interface ou com `main.py import contas.txt`.

### 🤝 Contribuindo

Issues e pull requests são bem-vindos. Rode os testes antes de enviar alterações. Se o projeto for útil para você, uma ⭐ no repositório ajuda outros usuários de Linux a encontrá-lo.

</details>

<br>

---

<div align="center">

**MIT License** • See / Consulte [`LICENSE`](LICENSE)

<sub>Roblox account manager Linux · Roblox multi-instance Linux · Roblox alt manager · multiple Roblox accounts Linux · Sober multiple accounts · gerenciador de contas Roblox Linux · várias contas Roblox Linux</sub>

</div>
