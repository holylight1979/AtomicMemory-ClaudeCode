<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/desktop-linux | lastmod: 2026-10-21 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/desktop-linux（官方 zh-TW，lastmod 2026-10-21）｜分類：Getting started › Platforms and integrations｜EN 摘要：Install and update the Claude desktop app on Ubuntu and Debian

# Linux 上的 Claude Desktop（測試版）

> 在 Ubuntu 和 Debian 上安裝和更新 Claude 桌面應用程式

> [!NOTE]
>
> Linux 上的 Claude 桌面應用程式處於測試版。

Linux 上的桌面應用程式提供與 macOS 和 Windows 相同的 Chat、Cowork 和 Claude Code 體驗：平行工作階段、視覺化差異檢視、整合式終端機和編輯器，以及即時應用程式預覽。請參閱[使用 Claude Code Desktop](https://code.claude.com/docs/zh-TW/desktop.md)以取得功能參考。

## 需求

* Debian 衍生發行版本：Ubuntu 22.04 或更新版本，或 Debian 12 或更新版本
* x86\_64 或 arm64

其他符合這些需求的 Debian 衍生發行版本可能可以運作，但未經官方測試。在非 Debian 衍生的發行版本上，例如 Fedora 或 Arch，請改為執行 [CLI](https://code.claude.com/docs/zh-TW/setup.md#system-requirements)。如果您在 Windows 上使用 WSL 2，請安裝 Windows 桌面應用程式並在您的發行版本內執行工作階段；請參閱 [Claude Code Desktop in WSL](https://code.claude.com/docs/zh-TW/desktop-wsl.md)。

### Cowork 需求

Cowork 是桌面應用程式中用於 [Dispatch 和更長時間代理工作](https://claude.com/docs/cowork/overview) 的部分。在 Linux 上，Cowork 在桌面應用程式使用 QEMU 和 KVM 託管的虛擬機器中執行這些工作。若要使用 Cowork，您的機器需要：

* **硬體虛擬化**：在您的韌體設定中開啟。沒有它，Cowork 會報告「Cowork requires hardware virtualization (KVM)」。
* **QEMU 和 UEFI 韌體**：x86\_64 上的 `qemu-system-x86`、`ovmf` 和 `virtiofsd`，或 arm64 上的 `qemu-system-arm`、`qemu-efi-aarch64` 和 `virtiofsd`。`apt install claude-desktop` 預設會將它們安裝為建議的套件。如果您使用 `--no-install-recommends` 安裝，或您的系統是跳過建議套件的最小映像，Cowork 會報告「Cowork requires QEMU」並顯示要執行的 `apt install` 命令。Ubuntu 22.04 沒有 `virtiofsd` 套件；應用程式在那裡使用捆綁的副本。
* **存取 `/dev/kvm`**：使用 `sudo usermod -aG kvm $USER` 將您的使用者新增到 `kvm` 群組，然後登出並重新登入。某些桌面環境會授予已登入的使用者存取 `/dev/kvm` 的權限而不需要群組，但 Cowork 也需要 `/dev/vhost-vsock`，只有 `kvm` 群組成員可以開啟。即使 `/dev/kvm` 已經對您有效，也要加入群組。

應用程式在啟動時檢查這些需求一次：安裝套件後重新啟動它，加入群組後登出並重新登入。如果 `/dev/vhost-vsock` 遺失且您執行的核心在 `/lib/modules` 下沒有模組目錄，Cowork 會報告核心不包含 Cowork 需要的虛擬化支援，且無法手動新增。這種組合在 ChromeOS 和基於容器的 Linux 環境中很常見。

## 安裝

從 Anthropic 的 apt 儲存庫安裝，以便更新透過您系統的定期套件更新到達。開啟終端機並執行每個步驟中的命令。

**1. 新增 Anthropic 的 apt 儲存庫**

此步驟使用 `curl` 下載簽署金鑰，並使用 `gpg` 驗證它，新鮮的 Debian 和 Ubuntu 安裝可能不包含這些工具。如果任一命令報告 `command not found`，請先安裝兩者：

```bash theme={null}
sudo apt install curl gnupg
```

下載 Anthropic 的簽署金鑰：

```bash theme={null}
sudo curl -fsSLo /usr/share/keyrings/claude-desktop-archive-keyring.asc https://downloads.claude.ai/claude-desktop/key.asc
```

命令成功時不列印任何內容，失敗時列印 `curl:` 錯誤。遺失或錯誤的金鑰會導致 `apt update` 稍後失敗並顯示 `NO_PUBKEY BAA929FF1A7ECACE`，因此請在繼續之前確認金鑰已下載且屬於 Anthropic：

```bash theme={null}
gpg --show-keys /usr/share/keyrings/claude-desktop-archive-keyring.asc
```

gpg 列印的指紋應為 `31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE`。如果 gpg 報告無法開啟檔案或包含無效的 OpenPGP 資料，表示下載失敗或傳回了錯誤的內容：確認您的網路可以到達 `downloads.claude.ai`，然後重新執行下載命令。

註冊儲存庫：

```bash theme={null}
echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/claude-desktop-archive-keyring.asc] https://downloads.claude.ai/claude-desktop/apt/stable stable main" | sudo tee /etc/apt/sources.list.d/claude-desktop.list
```

**2. 安裝套件**

```bash theme={null}
sudo apt update && sudo apt install claude-desktop
```

**3. 啟動並登入**

從您的應用程式啟動器啟動 **Claude**，或從終端機執行 `claude-desktop`，然後使用您的 Anthropic 帳戶登入。

Linux 應用程式的登入方式與 macOS 和 Windows 上相同：使用 claude.ai 訂閱，或透過您組織的 SSO。若要使用 API 金鑰身分驗證，請使用 [CLI](https://code.claude.com/docs/zh-TW/quickstart.md)。若要改為搭配 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 LLM 閘道使用 Desktop，請參閱 [Claude Desktop on 3P](https://claude.com/docs/third-party/claude-desktop/overview)。關於這些部署中的代理伺服器和自訂憑證授權單位，請參閱 [網路設定](https://code.claude.com/docs/zh-TW/network-config.md)。

### 從下載的檔案安裝

如果您無法透過 apt 儲存庫安裝，請直接從儲存庫的套件池下載 `.deb` 套件。此命令在儲存庫索引中查詢您的架構的最新套件，然後將其下載到目前目錄：

```bash theme={null}
curl -fLO "https://downloads.claude.ai/claude-desktop/apt/stable/$(curl -s "https://downloads.claude.ai/claude-desktop/apt/stable/dists/stable/main/binary-$(dpkg --print-architecture)/Packages" | grep '^Filename: pool/main/c/claude-desktop/claude-desktop_' | sort -V | tail -n 1 | cut -d' ' -f2)"
```

如果命令失敗並顯示 `Remote file name has no length`，表示查詢未傳回套件路徑。這可能表示無法擷取儲存庫索引，例如當您的網路阻止 `downloads.claude.ai` 時，或該架構不存在套件。確認您的網路可以到達 `downloads.claude.ai`，且 `dpkg --print-architecture` 列印 `amd64` 或 `arm64`；儲存庫不會為其他架構發佈套件。

若要在不註冊 Anthropic 的 apt 儲存庫的情況下安裝，請先建立 `/etc/default/claude-desktop`，其中包含 `CLAUDE_DESKTOP_ADD_REPO="false"` 這一行。沒有儲存庫，apt 不會提供新版本；若要更新，請重新執行下載命令並重新安裝，或稍後 [註冊儲存庫](#install)。

然後使用您的軟體安裝程式（例如 GNOME Software）開啟下載的檔案，或從包含下載檔案的目錄使用 apt 安裝它：

```bash theme={null}
sudo apt install ./claude-desktop_*.deb
```

如果 apt 報告 `E: Unsupported file ./claude-desktop_*.deb given on commandline`，表示該模式與目前目錄中的 `.deb` 檔案不符。確認下載已完成，然後從包含該檔案的目錄再次執行命令。

`.deb` 包含 Anthropic 的簽署金鑰，並將其安裝至 `/usr/share/keyrings/claude-desktop-archive-keyring.asc`，因此您不需要自行下載金鑰。除非您已使用 `CLAUDE_DESKTOP_ADD_REPO` 關閉註冊，否則該套件也會在 `/etc/apt/sources.list.d/claude-desktop.list` 註冊 apt 儲存庫，因此未來的更新會透過您系統的 [定期套件更新](#update) 到達。

## 更新

桌面應用程式在 Linux 上不會自動更新。更新透過您系統的定期套件更新到達：

```bash theme={null}
sudo apt update && sudo apt upgrade
```

您的發行版本的圖形軟體更新程式也會取得新版本。

## 解除安裝

```bash theme={null}
sudo apt remove claude-desktop
```

解除安裝套件也會移除它所註冊的儲存庫項目和簽署金鑰。如果您在[新增 Anthropic 的 apt 儲存庫](#install)步驟中自行新增了儲存庫項目，也請將其移除：

```bash theme={null}
sudo rm /etc/apt/sources.list.d/claude-desktop.list
```

## 疑難排解

### 無法找到 claude-desktop 套件

如果 `sudo apt install claude-desktop` 失敗並顯示 `E: Unable to locate package claude-desktop`，表示 apt 找不到您新增的儲存庫。請檢查以下項目：

* 新增儲存庫後執行 `sudo apt update`。`apt install` 本身在您上次執行 `apt update` 之後新增的儲存庫中看不到。
* 確認儲存庫項目已寫入。`cat /etc/apt/sources.list.d/claude-desktop.list` 應該顯示來自[新增 Anthropic 的 apt 儲存庫](#install)步驟的 `deb` 行。如果檔案為空或遺失，請再次執行該步驟。
* 確認您的架構受支援。`dpkg --print-architecture` 應該列印 `amd64` 或 `arm64`。儲存庫不會為其他架構發佈套件。
* 再次執行 `sudo apt update` 並檢查其輸出中是否有與 `downloads.claude.ai` 相關的錯誤。該處的網路或金鑰錯誤表示儲存庫已新增但無法連線或驗證。

如果儲存庫已就位且可連線，但仍找不到套件，請改為[從下載的檔案安裝](#install-from-a-downloaded-file)。

### 未滿足的相依性

如果 `apt` 停止並顯示 `The following packages have unmet dependencies` 或 `Unsatisfied dependencies`，請閱讀它所列出的相依性：

* `libc6 (>= 2.34)`：您的發行版本比套件支援的版本更舊。Ubuntu 20.04 附帶 `libc6` 2.31。升級至 Ubuntu 22.04 或更新版本，或 Debian 12 或更新版本。
* 所有遺失的相依性都顯示 `not installable` 並帶有 `:amd64` 或 `:arm64` 後綴：您下載的 `.deb` 是針對與您機器不同的架構。執行 `dpkg --print-architecture` 並下載相符的 `.deb`，或[從 apt 儲存庫安裝](#install)，它會為您的架構選擇套件。

### 以 root 身份執行而不使用 `--no-sandbox` 不受支援

如果 `claude-desktop` 以此訊息結束，表示您以 root 身份啟動它。以一般使用者身份登入並從該處啟動它。

### 您的登入不會在此裝置上儲存

Claude Desktop 會將您的登入儲存在您桌面的鑰匙圈中，例如 GNOME Keyring 或 KDE Wallet。如果它無法連線到已解鎖的鑰匙圈，您的登入不會儲存，每次啟動應用程式時都會重新登入。選擇與您的系統相符的情況：

* **未安裝鑰匙圈，在 KDE Plasma 以外的桌面上**：如果您使用 `--no-install-recommends` 安裝，或在略過建議套件的最小映像上，apt 未安裝鑰匙圈。使用 `sudo apt install gnome-keyring` 安裝 GNOME Keyring。
* **KDE Plasma 且也安裝了 GNOME Keyring**：KDE Wallet 隨附於 Plasma 桌面。這兩個鑰匙圈會衝突，Claude Desktop 可能會顯示此通知，即使 KDE Wallet 有效。使用 `sudo apt remove gnome-keyring` 移除額外的鑰匙圈，然後重新啟動您的電腦。
* **鑰匙圈已安裝但已鎖定**：將其解鎖。

修正後，重新啟動應用程式並登入。然後結束並再次啟動它，以確認應用程式在您仍然登入的情況下開啟。

### Cowork 無法使用

如果 Cowork 顯示以下其中一則訊息，請修正它所列出的需求，然後重新啟動應用程式：

* **Cowork 需要 QEMU**：安裝訊息所列出的 [QEMU 和 UEFI 韌體套件](#cowork-requirements)。
* **Cowork 需要硬體虛擬化 (KVM)**：在您的韌體設定中開啟[硬體虛擬化](#cowork-requirements)。
* **Claude 沒有使用虛擬化的權限 (/dev/kvm)**：將您的使用者新增至 [`kvm` 群組](#cowork-requirements)，然後登出並重新登入。
* **Cowork 需要 `vhost_vsock` 核心模組**：執行 `sudo modprobe vhost_vsock`，然後重新啟動應用程式。這只會為目前的開機載入模組。若要在每次開機時載入它，請執行 `echo vhost_vsock | sudo tee /etc/modules-load.d/vhost_vsock.conf`。

## Linux 測試版中尚未提供的功能

* **Computer Use**：[應用程式和螢幕控制](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)在 Linux 上不可用。
* **Dictation**：語音輸入在 Linux 桌面應用程式中不可用。請改用 CLI 中的[語音聽寫](https://code.claude.com/docs/zh-TW/voice-dictation.md)。
* **Quick Entry 全域快捷鍵**：在 X11 上運作。在原生 Wayland 上，它需要您的桌面環境的 GlobalShortcuts 入口。
* **Fedora 和 RHEL**：目前僅支援 Debian 衍生發行版本。將來會支援其他發行版本。

對於桌面應用程式中尚未提供的任何功能，[CLI](https://code.claude.com/docs/zh-TW/quickstart.md) 執行相同的 Claude Code 引擎並支援更廣泛的 Linux 發行版本；請參閱[系統需求](https://code.claude.com/docs/zh-TW/setup.md#system-requirements)。
