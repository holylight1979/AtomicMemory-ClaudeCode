<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment | lastmod: 2026-10-06 | section: Agent SDK / Deployment -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment（官方 zh-TW，lastmod 2026-10-06）｜分類：Agent SDK › Deployment｜EN 摘要：A guide to securing Claude Code and Agent SDK deployments with isolation, credential management, and network controls

# 安全部署 AI 代理

> 一份關於使用隔離、認證管理和網路控制來保護 Claude Code 和 Agent SDK 部署的指南

Claude Code 和 Agent SDK 可以代表您執行程式碼、存取檔案，並與外部服務互動。

與遵循預定程式碼路徑的傳統軟體不同，這些工具根據上下文和目標動態生成其操作。這種靈活性是它們有用的原因，但這也意味著它們的行為可能受到它們處理的內容的影響：檔案、網頁或使用者輸入。這有時被稱為提示注入。例如，如果儲存庫的 README 包含不尋常的指令，Claude Code 可能會以操作員未預期的方式將這些指令納入其操作中。本指南涵蓋了減少此風險的實用方法。

並非每個部署都需要最大安全性。在筆記型電腦上執行 Claude Code 的開發人員的要求與在多租戶環境中處理客戶資料的公司不同。本指南提供了從 Claude Code 的內建安全功能到強化生產架構的選項，因此您可以選擇適合您情況的選項。

## 威脅模型

代理可能因提示注入（嵌入在它們處理的內容中的指令）或模型錯誤而採取意外操作。Claude 模型旨在抵抗這種情況；請參閱[模型概述](https://platform.claude.com/docs/zh-TW/about-claude/models/overview)和您部署的模型的系統卡以了解評估詳情。

不過，深度防禦仍然是很好的做法。例如，如果代理處理一個惡意檔案，該檔案指示它將客戶資料發送到外部伺服器，網路控制可以完全阻止該請求。

## 內建安全功能

Claude Code 包含多項安全功能，可解決常見問題。有關完整詳情，請參閱[安全文件](https://code.claude.com/docs/zh-TW/security.md)。

* **權限系統**：每個工具和 bash 命令都可以配置為允許、阻止或提示使用者批准。使用 glob 模式建立規則，例如「允許所有 npm 命令」或「阻止任何包含 sudo 的命令」。組織可以設定適用於所有使用者的政策。請參閱[權限](https://code.claude.com/docs/zh-TW/permissions.md)。
* **用於權限的命令解析**：在執行 bash 命令之前，Claude Code 將其解析為 AST 並將結果與您的權限規則進行比對。無法乾淨解析或不符合允許規則的命令需要明確批准。一小組構造（例如 `eval`）無論允許規則如何都始終需要批准。這是一個權限閘道，而不是沙箱；除了內建安全檢查（例如 `rm` 和 `rmdir` 上的[關鍵路徑檢查](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)和[受保護路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)清單）外，它不會根據其目標路徑或效果推斷命令是否危險。
* **Web 搜尋摘要**：搜尋結果被摘要化，而不是將原始內容直接傳遞到上下文中，降低了來自惡意 Web 內容的提示注入風險。
* **Sandbox 模式**：Bash 命令可以在限制檔案系統和網路存取的沙箱環境中執行。有關詳情，請參閱[沙箱文件](https://code.claude.com/docs/zh-TW/sandboxing.md)。

## 安全原則

對於需要超越 Claude Code 預設值進行額外強化的部署，這些原則指導可用選項。

### 安全邊界

安全邊界將具有不同信任級別的元件分開。對於高安全性部署，您可以將敏感資源（如認證）放在包含代理的邊界之外。如果代理環境中出現問題，該邊界外的資源仍然受到保護。

例如，與其直接給予代理 API 金鑰的存取權，您可以在代理環境外執行代理，將金鑰注入到請求中。代理可以進行 API 呼叫，但它永遠看不到認證本身。此模式對於多租戶部署或處理不受信任的內容時很有用。

### 最小權限

在需要時，您可以限制代理僅具有其特定任務所需的功能：

| 資源 | 限制選項 |
| - | - |
| 檔案系統 | 僅掛載所需目錄，偏好唯讀 |
| 網路 | 透過代理限制到特定端點 |
| 認證 | 透過代理注入而不是直接公開 |
| 系統功能 | 在容器中刪除 Linux 功能 |

### 深度防禦

對於高安全性環境，分層多個控制提供額外保護。選項包括：

* 容器隔離
* 網路限制
* 檔案系統控制
* 代理處的請求驗證

正確的組合取決於您的威脅模型和操作要求。

## 隔離技術

不同的隔離技術在安全強度、效能和操作複雜性之間提供不同的權衡。

> [!NOTE]
>
> 在所有這些配置中，Claude Code（或您的 Agent SDK 應用程式）在隔離邊界內執行（沙箱、容器或 VM）。下面描述的安全控制限制了代理可以從該邊界內存取的內容。

| 技術 | 隔離強度 | 效能開銷 | 複雜性 |
| - | - | - | - |
| Sandbox runtime | 良好（安全預設值） | 非常低 | 低 |
| 容器 (Docker) | 取決於設定 | 低 | 中等 |
| gVisor | 優秀（設定正確時） | 中等/高 | 中等 |
| VM (Firecracker, QEMU) | 優秀（設定正確時） | 高 | 中等/高 |

### Sandbox runtime

對於無需容器的輕量級隔離，[sandbox-runtime](https://github.com/anthropics/sandbox-runtime) 在 OS 級別強制執行檔案系統和網路限制。

主要優點是簡單性：不需要 Docker 配置、容器映像或網路設定。代理和檔案系統限制是內建的。

**工作原理：**

* **檔案系統**：使用 OS 原語（Linux 上的 `bubblewrap`、macOS 上的 `sandbox-exec`）限制對配置路徑的讀/寫存取
* **網路**：移除網路命名空間 (Linux) 或使用 Seatbelt 設定檔 (macOS) 透過內建代理路由網路流量
* **配置**：基於 JSON 的網域和檔案系統路徑允許清單

**設定：**

```bash theme={null}
npm install @anthropic-ai/sandbox-runtime
```

然後建立一個設定檔，指定允許的路徑和網域。

**安全考量：**

1. **同主機核心**：與 VM 不同，沙箱化程序共享主機核心。核心漏洞理論上可能導致逃逸。對於某些威脅模型，這是可以接受的，但如果您需要核心級隔離，請使用 gVisor 或單獨的 VM。

2. **無 TLS 檢查**：代理根據用戶端提供的主機名稱允許清單網域，不會終止或檢查加密流量。在沙箱內執行的程式碼可能會使用[網域前置](https://en.wikipedia.org/wiki/Domain_fronting)或類似技術來到達允許清單外的主機。如果您的威脅模型需要更強的保證，請配置[TLS 終止代理](#traffic-forwarding)。有關更多詳情，請參閱[沙箱安全限制](https://code.claude.com/docs/zh-TW/sandboxing.md#security-limitations)。另外，如果代理對允許的網域具有寬鬆認證，請確保它無法使用該網域觸發其他網路請求或洩露資料。

對於許多單開發人員和 CI/CD 用例，sandbox-runtime 以最少的設定顯著提高了標準。下面的部分涵蓋了需要更強隔離的部署的容器和 VM。

### 容器

容器透過 Linux 命名空間提供隔離。每個容器都有自己的檔案系統、程序樹和網路堆棧視圖，同時共享主機核心。

安全強化的容器配置可能如下所示：

```bash theme={null}
docker run \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --security-opt seccomp=/path/to/seccomp-profile.json \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=100m \
  --tmpfs /home/agent:rw,noexec,nosuid,size=500m \
  --network none \
  --memory 2g \
  --cpus 2 \
  --pids-limit 100 \
  --user 1000:1000 \
  -v /path/to/code:/workspace:ro \
  -v /var/run/proxy.sock:/var/run/proxy.sock:ro \
  agent-image
```

以下是每個選項的作用：

| 選項 | 目的 |
| - | - |
| `--cap-drop ALL` | 移除 Linux 功能，例如可能導致權限提升的 `NET_ADMIN` 和 `SYS_ADMIN` |
| `--security-opt no-new-privileges` | 防止程序透過 setuid 二進位檔案獲得權限 |
| `--security-opt seccomp=...` | 限制可用的系統呼叫；Docker 的預設值阻止約 44 個，自訂設定檔可以阻止更多 |
| `--read-only` | 使容器的根檔案系統不可變，防止代理持久化更改 |
| `--tmpfs /tmp:...` | 提供一個可寫的臨時目錄，在容器停止時清除 |
| `--network none` | 移除所有網路介面；代理透過下面掛載的 Unix 套接字進行通訊 |
| `--memory 2g` | 將記憶體使用限制為 2GB，以防止資源耗盡 |
| `--pids-limit 100` | 限制程序計數以防止 fork 炸彈 |
| `--user 1000:1000` | 以非 root 使用者身份執行 |
| `-v ...:/workspace:ro` | 以唯讀方式掛載程式碼，以便代理可以分析但不能修改它。**避免掛載敏感的主機目錄，例如 `~/.ssh`、`~/.aws` 或 `~/.config`** |
| `-v .../proxy.sock:...` | 掛載連接到在容器外執行的代理的 Unix 套接字（見下文） |

**Unix 套接字架構：**

使用 `--network none`，容器根本沒有網路介面。代理到達外部世界的唯一方式是透過掛載的 Unix 套接字，該套接字連接到在主機上執行的代理。此代理可以強制執行網域允許清單、注入認證並記錄所有流量。

這與 [sandbox-runtime](https://github.com/anthropics/sandbox-runtime) 使用的架構相同。即使 agent 透過提示詞注入而被入侵，它也無法將資料洩露到任意伺服器。它只能透過代理伺服器進行通訊，由代理伺服器控制哪些網域可到達。有關更多詳情，請參閱 [Claude Code 沙箱機制部落格文章](https://www.anthropic.com/engineering/claude-code-sandboxing)。

**額外強化選項：**

| 選項 | 目的 |
| - | - |
| `--userns-remap` | 將容器 root 對應到無特權主機使用者；需要守護程序配置，但限制容器逃逸造成的損害 |
| `--ipc private` | 隔離程序間通訊以防止跨容器攻擊 |

### gVisor

標準容器共享主機核心：當容器內的程式碼進行系統呼叫時，它直接進入執行主機的同一核心。這意味著核心漏洞可能允許容器逃逸。gVisor 透過在使用者空間中攔截系統呼叫，在它們到達主機核心之前，實現自己的相容性層來處理大多數系統呼叫，而無需涉及真實核心，從而解決了這個問題。

如果代理執行惡意程式碼（可能由於提示注入），該程式碼在容器中執行，可能會嘗試核心漏洞利用。使用 gVisor，攻擊面要小得多：惡意程式碼首先需要利用 gVisor 的使用者空間實現，並且對真實核心的存取有限。

要將 gVisor 與 Docker 一起使用，請安裝 `runsc` 執行時並配置守護程序：

```json /etc/docker/daemon.json theme={null}
{
  "runtimes": {
    "runsc": {
      "path": "/usr/local/bin/runsc"
    }
  }
}
```

然後使用以下命令執行容器：

```bash theme={null}
docker run --runtime=runsc agent-image
```

**效能考量：**

| 工作負載 | 開銷 |
| - | - |
| CPU 密集型計算 | \~0%（無系統呼叫攔截） |
| 簡單系統呼叫 | \~2 倍慢 |
| 檔案 I/O 密集型 | 對於繁重的開啟/關閉模式，最多慢 10-200 倍 |

對於多租戶環境或處理不受信任的內容時，額外的隔離通常值得開銷。

### 虛擬機

VM 透過 CPU 虛擬化擴展提供硬體級隔離。每個 VM 執行自己的核心，建立強大的邊界。客體核心中的漏洞不會直接危害主機。但是，VM 不會自動比 gVisor 等替代方案「更安全」。VM 安全性在很大程度上取決於虛擬機管理程式和裝置模擬程式碼。

Firecracker 專為輕量級 microVM 隔離而設計。它可以在 125 毫秒內啟動 VM，記憶體開銷不到 5 MiB，去除不必要的裝置模擬以減少攻擊面。

使用此方法，代理 VM 沒有外部網路介面。相反，它透過 `vsock`（虛擬套接字）進行通訊。所有流量透過 vsock 路由到主機上的代理，該代理強制執行允許清單並在轉發請求之前注入認證。

### 雲部署

對於雲部署，您可以將上述任何隔離技術與雲原生網路控制相結合：

1. 在沒有網際網路閘道的私有子網中執行代理容器
2. 配置雲防火牆規則（AWS 安全群組、GCP VPC 防火牆）以阻止除代理外的所有出站流量
3. 執行代理（例如 [Envoy](https://www.envoyproxy.io/)，其 `credential_injector` 篩選器）來驗證請求、強制執行網域允許清單、注入認證並轉發到外部 API
4. 為代理的服務帳戶分配最小 IAM 權限，盡可能透過代理路由敏感存取
5. 在代理處記錄所有流量以進行審計

## 認證管理

代理通常需要認證來呼叫 API、存取儲存庫或與雲服務互動。挑戰是提供此存取權，而不公開認證本身。

### 代理模式

建議的方法是在代理的安全邊界外執行代理，將認證注入到傳出請求中。代理發送沒有認證的請求，代理添加它們，並將請求轉發到其目的地。

此模式有幾個好處：

1. 代理永遠看不到實際認證
2. 代理可以強制執行允許的端點允許清單
3. 代理可以記錄所有請求以進行審計
4. 認證存儲在一個安全位置，而不是分散到每個代理

### 配置 Claude Code 以使用代理

Claude Code 支援兩種方法來透過代理路由採樣請求：

**選項 1：ANTHROPIC\_BASE\_URL（簡單，但僅適用於採樣 API 請求）**

```bash theme={null}
export ANTHROPIC_BASE_URL="http://localhost:8080"
```

這告訴 Claude Code 和 Agent SDK 將採樣請求發送到您的代理，而不是直接發送到 Claude API。您的代理接收純文字 HTTP 請求，可以檢查和修改它們（包括注入認證），然後轉發到真實 API。

**選項 2：HTTP\_PROXY / HTTPS\_PROXY（系統範圍）**

```bash theme={null}
export HTTP_PROXY="http://localhost:8080"
export HTTPS_PROXY="http://localhost:8080"
```

Claude Code 和 Agent SDK 尊重這些標準環境變數，透過代理路由所有 HTTP 流量。對於 HTTPS，代理建立加密的 CONNECT 隧道：它無法在沒有 TLS 檢查的情況下看到或修改請求內容。

### 實現代理

您可以建立自己的代理或使用現有的代理：

* [Envoy Proxy](https://www.envoyproxy.io/)：生產級代理，具有 `credential_injector` 篩選器用於添加身份驗證標頭
* [mitmproxy](https://mitmproxy.org/)：TLS 終止代理，用於檢查和修改 HTTPS 流量
* [Squid](http://www.squid-cache.org/)：具有存取控制清單的快取代理
* [LiteLLM](https://github.com/BerriAI/litellm)：LLM 閘道，具有認證注入和速率限制

### 其他服務的認證

除了從 Claude API 採樣外，代理通常需要對其他服務的身份驗證存取，例如 git 儲存庫、資料庫和內部 API。有兩種主要方法：

#### 自訂工具

透過 MCP 伺服器或自訂工具提供存取，該工具將請求路由到在代理安全邊界外執行的服務。代理呼叫工具，但實際的身份驗證請求發生在外部。工具呼叫代理，代理注入認證。

例如，git MCP 伺服器可以接受來自代理的命令，但將它們轉發到在主機上執行的 git 代理，該代理在聯絡遠端儲存庫之前添加身份驗證。代理永遠看不到認證。

優點：

* **無 TLS 檢查**：外部服務直接進行身份驗證請求
* **認證保持在外部**：代理只看到工具介面，而不是基礎認證

#### 流量轉發

對於 Claude API 呼叫，`ANTHROPIC_BASE_URL` 允許您將請求路由到可以以純文字檢查和修改它們的代理。但對於其他 HTTPS 服務（GitHub、npm 登錄檔、內部 API），流量通常是端到端加密的。即使您透過 `HTTP_PROXY` 透過代理路由它，代理也只看到不透明的 TLS 隧道，無法注入認證。

要修改任意服務的 HTTPS 流量，而不使用自訂工具，您需要一個 TLS 終止代理，該代理解密流量、檢查或修改它，然後在轉發之前重新加密它。這需要：

1. 在代理的容器外執行代理
2. 在代理的信任存儲中安裝代理的 CA 憑證（以便代理信任代理的憑證）
3. 配置 `HTTP_PROXY`/`HTTPS_PROXY` 透過代理路由流量

此方法處理任何基於 HTTP 的服務，而無需編寫自訂工具，但增加了圍繞憑證管理的複雜性。

請注意，並非所有程式都會遵循 `HTTP_PROXY`/`HTTPS_PROXY`。大多數工具（curl、pip、npm、git）都會遵循，但有些可能會略過這些變數而直接連線。例如，Node.js `fetch()` 預設會忽略這些變數；在 Node 24+ 中，您可以設定 `NODE_USE_ENV_PROXY=1` 以啟用支援。若要涵蓋會忽略這些變數的工具，您可以使用 [proxychains](https://github.com/haad/proxychains) 來攔截網路呼叫，或設定 iptables 將傳出流量重新導向到透明代理伺服器。

> [!NOTE]
>
> **透明代理**在網路級別攔截流量，因此用戶端不需要配置為使用它。常規代理要求用戶端明確連接並說 HTTP CONNECT 或 SOCKS。透明代理（如 Squid 或 mitmproxy 透明模式）可以處理原始重定向的 TCP 連接。

兩種方法仍然需要 TLS 終止代理和受信任的 CA 憑證。它們只是確保流量實際到達代理。

## 檔案系統配置

檔案系統控制決定代理可以讀取和寫入的檔案。

### 唯讀程式碼掛載

當代理需要分析程式碼但不修改它時，以唯讀方式掛載目錄：

```bash theme={null}
docker run -v /path/to/code:/workspace:ro agent-image
```

> [!WARNING]
>
> 即使對程式碼目錄的唯讀存取也可能公開認證。掛載前要排除或清理的常見檔案：
>
> | 檔案 | 風險 |
> | - | - |
> | `.env`, `.env.local` | API 金鑰、資料庫密碼、機密 |
> | `~/.git-credentials` | Git 密碼/令牌（純文字） |
> | `~/.aws/credentials` | AWS 存取金鑰 |
> | `~/.config/gcloud/application_default_credentials.json` | Google Cloud ADC 令牌 |
> | `~/.azure/` | Azure CLI 認證 |
> | `~/.docker/config.json` | Docker 登錄檔身份驗證令牌 |
> | `~/.kube/config` | Kubernetes 叢集認證 |
> | `.npmrc`, `.pypirc` | 套件登錄檔令牌 |
> | `*-service-account.json` | GCP 服務帳戶金鑰 |
> | `*.pem`, `*.key` | 私密金鑰 |
>
> 考慮僅複製所需的原始檔案，或使用 `.dockerignore` 樣式篩選。

### 可寫位置

如果代理需要寫入檔案，您有幾個選項，取決於您是否希望更改持久化：

對於容器中的臨時工作區，使用僅存在於記憶體中的 `tmpfs` 掛載，在容器停止時清除：

```bash theme={null}
docker run \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=100m \
  --tmpfs /workspace:rw,noexec,size=500m \
  agent-image
```

如果您想在持久化更改之前檢查它們，覆蓋檔案系統允許代理寫入而不修改基礎檔案。更改存儲在單獨的層中，您可以檢查、應用或丟棄。對於完全持久的輸出，掛載專用磁碟區，但將其與敏感目錄分開。

## 進一步閱讀

* [Claude Code 安全文件](https://code.claude.com/docs/zh-TW/security.md)
* [託管 Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/hosting.md)
* [處理權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)
* [Sandbox runtime](https://github.com/anthropics/sandbox-runtime)
* [The Lethal Trifecta for AI Agents](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)
* [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
* [Docker Security Best Practices](https://docs.docker.com/engine/security/)
* [gVisor Documentation](https://gvisor.dev/docs/)
* [Firecracker Documentation](https://firecracker-microvm.github.io/)
